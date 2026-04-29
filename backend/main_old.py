"""
main.py — AnomalyGuard FastAPI Backend
Run: uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.detector import AnomalyDetector
from core.explainer import explain_anomaly
from core.severity import calculate_severity


# ─────────────────────────────────────────────────────────────────────────────
# Safe JSON that handles ALL numpy types
# ─────────────────────────────────────────────────────────────────────────────

def safe_json_default(obj):
    """Handle any numpy type during JSON encoding."""
    if hasattr(obj, 'item'):
        return obj.item()
    if hasattr(obj, 'tolist'):
        return obj.tolist()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    return str(obj)


def safe_json_dumps(data):
    """Convert any data to JSON string, handling all numpy types."""
    return json.dumps(data, default=safe_json_default)


def SafeJSONResponse(data):
    """Return a Response with safe JSON encoding."""
    return Response(
        content=safe_json_dumps(data),
        media_type="application/json"
    )


def _health_label(score):
    if score >= 80:
        return "HEALTHY"
    if score >= 60:
        return "DEGRADED"
    if score >= 40:
        return "WARNING"
    return "CRITICAL"


def to_python(val):
    """Convert a single value to native Python type."""
    if hasattr(val, 'item'):
        return val.item()
    if hasattr(val, 'tolist'):
        return val.tolist()
    return val


# ─────────────────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="AnomalyGuard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Global state
# ─────────────────────────────────────────────────────────────────────────────

detector = AnomalyDetector()

logs = []
anomalies = []

connected_clients = set()

START_TIME = time.time()
health_score = 100
last_anomaly_time = None
_recovery_task = None

MODE_FILE = "logs/current_mode.txt"

SEVERITY_PENALTY = {
    "CRITICAL": 20,
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 2,
}
SEVERITY_COLOR = {
    "CRITICAL": "#FF0000",
    "HIGH": "#FF6600",
    "MEDIUM": "#FFB300",
    "LOW": "#00C853",
    "NONE": "#4CAF50",
}

# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    global _recovery_task
    os.makedirs("logs", exist_ok=True)
    _recovery_task = asyncio.create_task(_health_recovery_loop())
    print("[AnomalyGuard] Server started. Detector ready.")


async def _health_recovery_loop():
    global health_score, last_anomaly_time
    while True:
        await asyncio.sleep(60)
        if last_anomaly_time is None or (time.time() - last_anomaly_time) >= 60:
            health_score = min(100, health_score + 1)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

async def broadcast(payload):
    dead = set()
    message = safe_json_dumps(payload)
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[WS] Client connected. Total: {len(connected_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        print(f"[WS] Client disconnected. Total: {len(connected_clients)}")


# ─────────────────────────────────────────────────────────────────────────────
# POST /ingest
# ─────────────────────────────────────────────────────────────────────────────

class LogPayload(BaseModel):
    timestamp: str
    cpu_usage: float
    memory_usage: float
    response_time_ms: float
    requests_per_sec: float
    mode: str = "normal"


@app.post("/ingest")
async def ingest(payload: LogPayload):
    global health_score, last_anomaly_time

    log_dict = payload.model_dump()

    # Anomaly detection
    detector.add_log(log_dict)
    result = detector.predict(log_dict)

    # Convert numpy types immediately
    is_anomaly = bool(to_python(result.get("is_anomaly", False)))
    score = float(to_python(result.get("score", 0.0)))

    severity_level = "NONE"
    explanation = ""
    severity_color = SEVERITY_COLOR["NONE"]

    ts = str(log_dict.get("timestamp", ""))
    cpu = float(log_dict.get("cpu_usage", 0))
    mem = float(log_dict.get("memory_usage", 0))
    rt = float(log_dict.get("response_time_ms", 0))
    rps = float(log_dict.get("requests_per_sec", 0))
    mode = str(log_dict.get("mode", "normal"))

    if is_anomaly:
        severity_level = str(calculate_severity(log_dict))
        explanation = str(explain_anomaly(log_dict, severity_level))
        severity_color = str(SEVERITY_COLOR.get(severity_level, "#FF0000"))

        penalty = SEVERITY_PENALTY.get(severity_level, 5)
        health_score = max(0, health_score - penalty)
        last_anomaly_time = time.time()

        anomalies.append({
            "timestamp": ts,
            "cpu_usage": cpu,
            "memory_usage": mem,
            "response_time_ms": rt,
            "requests_per_sec": rps,
            "mode": mode,
            "is_anomaly": True,
            "severity_level": severity_level,
            "severity_color": severity_color,
            "explanation": explanation,
            "score": score,
            "reason": str(to_python(result.get("reason", ""))),
            "health_score": int(health_score),
        })

        await broadcast({
            "timestamp": ts,
            "cpu_usage": cpu,
            "memory_usage": mem,
            "response_time_ms": rt,
            "requests_per_sec": rps,
            "is_anomaly": True,
            "severity_level": severity_level,
            "severity_color": severity_color,
            "explanation": explanation,
            "health_score": int(health_score),
        })

        print(
            f"[ANOMALY] {severity_level} | CPU={cpu:.1f}% "
            f"MEM={mem:.1f}% "
            f"RT={rt:.0f}ms | {explanation}"
        )
    else:
        await broadcast({
            "timestamp": ts,
            "cpu_usage": cpu,
            "memory_usage": mem,
            "response_time_ms": rt,
            "requests_per_sec": rps,
            "is_anomaly": False,
            "severity_level": "NONE",
            "severity_color": SEVERITY_COLOR["NONE"],
            "explanation": "",
            "health_score": int(health_score),
        })

    # Append to rolling log (cap 500)
    logs.append({
        "timestamp": ts,
        "cpu_usage": cpu,
        "memory_usage": mem,
        "response_time_ms": rt,
        "requests_per_sec": rps,
        "mode": mode,
        "is_anomaly": is_anomaly,
        "severity_level": severity_level,
    })
    if len(logs) > 500:
        logs.pop(0)

    return SafeJSONResponse({
        "is_anomaly": is_anomaly,
        "severity": severity_level,
        "explanation": explanation,
        "score": score,
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /logs
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/logs")
async def get_logs():
    try:
        return SafeJSONResponse({"logs": logs[-100:], "total": len(logs)})
    except Exception as e:
        print(f"[ERROR] /logs failed: {e}")
        return SafeJSONResponse({"logs": [], "total": 0})


# ─────────────────────────────────────────────────────────────────────────────
# GET /anomalies
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/anomalies")
async def get_anomalies():
    try:
        return SafeJSONResponse({"anomalies": anomalies, "total": len(anomalies)})
    except Exception as e:
        print(f"[ERROR] /anomalies failed: {e}")
        return SafeJSONResponse({"anomalies": [], "total": 0})


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def get_health():
    try:
        return SafeJSONResponse({
            "score": int(health_score),
            "status": _health_label(health_score),
            "connected_clients": len(connected_clients),
        })
    except Exception as e:
        print(f"[ERROR] /health failed: {e}")
        return SafeJSONResponse({"score": 100, "status": "HEALTHY"})


# ─────────────────────────────────────────────────────────────────────────────
# GET /stats
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/stats")
async def get_stats():
    try:
        total_logs_count = len(logs)
        total_anomalies_count = len(anomalies)
        detection_rate = round((total_anomalies_count / total_logs_count * 100), 2) if total_logs_count else 0.0
        uptime_seconds = int(time.time() - START_TIME)
        return SafeJSONResponse({
            "total_logs": total_logs_count,
            "total_anomalies": total_anomalies_count,
            "detection_rate_percent": detection_rate,
            "uptime_seconds": uptime_seconds,
            "health_score": int(health_score),
        })
    except Exception as e:
        print(f"[ERROR] /stats failed: {e}")
        return SafeJSONResponse({"total_logs": 0, "total_anomalies": 0, "detection_rate_percent": 0})


# ─────────────────────────────────────────────────────────────────────────────
# POST /simulate/{mode}
# ─────────────────────────────────────────────────────────────────────────────

VALID_MODES = {"normal", "ddos", "memory_leak", "cpu_spike"}


@app.post("/simulate/{mode}")
async def simulate_mode(mode: str):
    if mode not in VALID_MODES:
        return SafeJSONResponse({"error": f"Unknown mode '{mode}'. Valid: {sorted(VALID_MODES)}"})

    os.makedirs("logs", exist_ok=True)
    with open(MODE_FILE, "w") as f:
        f.write(mode)

    print(f"[SIM] Mode set to '{mode}'. Auto-reset to 'normal' in 30s.")
    asyncio.create_task(_auto_reset_mode(delay=30))

    return SafeJSONResponse({"mode": mode, "auto_reset_seconds": 30, "message": f"Simulator switched to '{mode}'"})


async def _auto_reset_mode(delay: int = 30):
    await asyncio.sleep(delay)
    try:
        with open(MODE_FILE, "w") as f:
            f.write("normal")
        print("[SIM] Mode auto-reset to 'normal'.")
    except Exception as exc:
        print(f"[SIM] Auto-reset failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)