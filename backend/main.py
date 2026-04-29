"""
main.py — AnomalyGuard FastAPI Backend
Improved version with better error handling, logging, and state management.

Run: python main.py
Or:  uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from config import config
from logger import logger, get_logger
from core.detector import AnomalyDetector
from core.explainer import explain_anomaly
from core.severity import calculate_severity, get_severity_color, get_severity_penalty
from core.state import app_state
from core.alerter import alert_manager
import psutil

# Get module logger
module_logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# JSON Serialization Utilities
# ─────────────────────────────────────────────────────────────────────────────

def safe_json_default(obj: Any) -> Any:
    """Handle numpy types and other non-serializable objects during JSON encoding."""
    if hasattr(obj, 'item'):
        return obj.item()
    if hasattr(obj, 'tolist'):
        return obj.tolist()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    return str(obj)


def safe_json_dumps(data: Any) -> str:
    """Safely convert data to JSON string handling all types."""
    return json.dumps(data, default=safe_json_default)


def SafeJSONResponse(data: Any, status_code: int = 200) -> Response:
    """Return a Response with safe JSON encoding."""
    return Response(
        content=safe_json_dumps(data),
        media_type="application/json",
        status_code=status_code
    )


def get_health_label(score: int) -> str:
    """Get health status label based on score."""
    if score >= 80:
        return "HEALTHY"
    if score >= 60:
        return "DEGRADED"
    if score >= 40:
        return "WARNING"
    return "CRITICAL"


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI App Setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AnomalyGuard",
    version="2.0.0",
    description="Real-time anomaly detection system for infrastructure monitoring"
)

# CORS Middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.CORS_ORIGINS,
    allow_credentials=config.api.CORS_CREDENTIALS,
    allow_methods=config.api.CORS_METHODS,
    allow_headers=config.api.CORS_HEADERS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Request Models with Validation
# ─────────────────────────────────────────────────────────────────────────────

class LogPayload(BaseModel):
    """Schema for incoming log data."""
    timestamp: str
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(0, ge=0, le=100)
    network_sent: int = Field(0, ge=0)
    network_recv: int = Field(0, ge=0)
    battery_pct: float = Field(0, ge=0, le=100)
    response_time_ms: float = Field(..., ge=0)
    requests_per_sec: float = Field(..., ge=0)
    mode: str = Field(default="normal")
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError("Invalid timestamp format")
    
    class Config:
        schema_extra = {
            "example": {
                "timestamp": "2024-01-01T12:00:00Z",
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "disk_usage": 75.3,
                "network_sent": 123456,
                "network_recv": 789012,
                "battery_pct": 85.0,
                "response_time_ms": 150,
                "requests_per_sec": 44.6,
                "mode": "normal"
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# Global Application State
# ─────────────────────────────────────────────────────────────────────────────

detector = AnomalyDetector()
_recovery_task: Optional[asyncio.Task] = None
MODE_FILE = "logs/current_mode.txt"
VALID_MODES = {"normal", "ddos", "memory_leak", "cpu_spike"}


# ─────────────────────────────────────────────────────────────────────────────
# Startup and Shutdown
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global _recovery_task
    
    try:
        os.makedirs("logs", exist_ok=True)
        _recovery_task = asyncio.create_task(_health_recovery_loop())
        module_logger.info("AnomalyGuard backend started successfully")
        module_logger.info(f"Detector configuration: {detector.get_status()}")
        module_logger.info(f"CORS origins: {config.api.CORS_ORIGINS}")
    except Exception as e:
        module_logger.error(f"Startup failed: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _recovery_task
    
    try:
        if _recovery_task:
            _recovery_task.cancel()
        module_logger.info("AnomalyGuard backend shut down gracefully")
    except Exception as e:
        module_logger.error(f"Shutdown error: {e}", exc_info=True)


async def _health_recovery_loop():
    """Periodically recover health score when no anomalies detected."""
    try:
        while True:
            await asyncio.sleep(config.health.RECOVERY_INTERVAL)
            
            # Check if enough time has passed since last anomaly
            if app_state.last_anomaly_time is None:
                time_since_anomaly = config.health.ANOMALY_FREE_THRESHOLD + 1
            else:
                time_since_anomaly = time.time() - app_state.last_anomaly_time
            
            # Recover health if no recent anomalies
            if time_since_anomaly >= config.health.ANOMALY_FREE_THRESHOLD:
                current_score = app_state.health_score
                new_score = min(100, current_score + config.health.RECOVERY_RATE)
                app_state.update_health_score(new_score)
                
                if new_score > current_score:
                    module_logger.debug(f"Health recovered: {current_score} -> {new_score}")
    
    except asyncio.CancelledError:
        module_logger.debug("Health recovery loop cancelled")
    except Exception as e:
        module_logger.error(f"Health recovery loop error: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Management
# ─────────────────────────────────────────────────────────────────────────────

async def broadcast(payload: Dict[str, Any]) -> None:
    """
    Broadcast message to all connected WebSocket clients.
    
    Args:
        payload: Dictionary to send to all clients
    """
    message = safe_json_dumps(payload)
    clients = app_state.get_clients()
    
    dead_clients = []
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception as e:
            module_logger.debug(f"Failed to send WebSocket message: {e}")
            dead_clients.append(ws)
    
    # Remove dead clients
    for ws in dead_clients:
        app_state.remove_client(ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    try:
        await websocket.accept()
        app_state.add_client(websocket)
        module_logger.info(f"WebSocket client connected (total: {len(app_state.get_clients())})")
        
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            app_state.remove_client(websocket)
            module_logger.info(f"WebSocket client disconnected (total: {len(app_state.get_clients())})")
    
    except Exception as e:
        module_logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close(code=1000)
        except:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/ingest", tags=["Data Ingestion"])
async def ingest(payload: LogPayload):
    """
    Ingest metric data and perform anomaly detection.
    
    Args:
        payload: Log data with metrics
        
    Returns:
        Prediction results
    """
    try:
        log_dict = payload.model_dump()
        
        # Add log to state
        app_state.add_log(log_dict)
        
        # Perform anomaly detection
        detector.add_log(log_dict)
        result = detector.predict(log_dict)
        
        # Extract detection result
        is_anomaly = bool(result.get("is_anomaly", False))
        score = float(result.get("score", 0.0))
        
        # Prepare broadcast and response
        broadcast_data = {
            "timestamp": log_dict.get("timestamp", ""),
            "cpu_usage": log_dict.get("cpu_usage", 0),
            "memory_usage": log_dict.get("memory_usage", 0),
            "response_time_ms": log_dict.get("response_time_ms", 0),
            "requests_per_sec": log_dict.get("requests_per_sec", 0),
            "is_anomaly": is_anomaly,
            "severity_level": "NONE",
            "severity_color": get_severity_color("NONE"),
            "explanation": "",
            "health_score": app_state.health_score,
        }
        
        if is_anomaly:
            severity_level = calculate_severity(log_dict)
            explanation = str(explain_anomaly(log_dict, severity_level))
            severity_color = get_severity_color(severity_level)
            
            # Apply health penalty
            penalty = get_severity_penalty(severity_level)
            new_health = max(0, app_state.health_score - penalty)
            app_state.update_health_score(new_health)
            
            # Create anomaly record
            anomaly_record = {
                "timestamp": log_dict.get("timestamp", ""),
                "cpu_usage": log_dict.get("cpu_usage", 0),
                "memory_usage": log_dict.get("memory_usage", 0),
                "response_time_ms": log_dict.get("response_time_ms", 0),
                "requests_per_sec": log_dict.get("requests_per_sec", 0),
                "mode": log_dict.get("mode", "normal"),
                "is_anomaly": True,
                "severity_level": severity_level,
                "severity_color": severity_color,
                "explanation": explanation,
                "score": score,
                "reason": result.get("reason", "unknown"),
                "health_score": new_health,
            }
            
            app_state.add_anomaly(anomaly_record)
            
            # Send Slack alert if configured
            alert_manager.send_slack_alert(anomaly_record)
            
            # Update broadcast data
            broadcast_data.update({
                "is_anomaly": True,
                "severity_level": severity_level,
                "severity_color": severity_color,
                "explanation": explanation,
                "health_score": new_health,
            })
            
            module_logger.info(
                f"Anomaly detected - {severity_level} | "
                f"CPU={log_dict.get('cpu_usage', 0):.1f}% "
                f"MEM={log_dict.get('memory_usage', 0):.1f}% | "
                f"{explanation}"
            )
        
        # Broadcast to WebSocket clients
        await broadcast(broadcast_data)
        
        return SafeJSONResponse({
            "is_anomaly": is_anomaly,
            "severity": broadcast_data["severity_level"],
            "explanation": broadcast_data["explanation"],
            "score": score,
            "health_score": app_state.health_score,
        })
    
    except Exception as e:
        module_logger.error(f"Ingest error: {e}", exc_info=True)
        return SafeJSONResponse(
            {"error": "Internal server error", "detail": str(e)},
            status_code=500
        )


@app.get("/logs", tags=["Data"])
async def get_logs(limit: int = 100):
    """
    Get recent logs.
    
    Args:
        limit: Maximum number of logs to return
        
    Returns:
        List of logs
    """
    try:
        logs = app_state.logs[-limit:] if limit > 0 else app_state.logs
        return SafeJSONResponse({
            "logs": logs,
            "total": len(app_state.logs),
            "returned": len(logs)
        })
    except Exception as e:
        module_logger.error(f"Get logs error: {e}", exc_info=True)
        return SafeJSONResponse({"logs": [], "total": 0}, status_code=500)


@app.get("/anomalies", tags=["Data"])
async def get_anomalies(limit: int = 100):
    """
    Get recent anomalies.
    
    Args:
        limit: Maximum number of anomalies to return
        
    Returns:
        List of anomalies
    """
    try:
        anomalies = app_state.get_anomalies(limit)
        return SafeJSONResponse({
            "anomalies": anomalies,
            "total": len(app_state.anomalies),
            "returned": len(anomalies)
        })
    except Exception as e:
        module_logger.error(f"Get anomalies error: {e}", exc_info=True)
        return SafeJSONResponse({"anomalies": [], "total": 0}, status_code=500)


@app.get("/health", tags=["Monitoring"])
async def get_health():
    """
    Get system health status.
    
    Returns:
        Health score and status
    """
    try:
        # System specs
        cpu_count = psutil.cpu_count()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SafeJSONResponse({
            "score": app_state.health_score,
            "status": get_health_label(app_state.health_score),
            "connected_clients": len(app_state.get_clients()),
            "detector_trained": detector.is_trained,
            "system_info": {
                "cpu_cores": cpu_count,
                "memory_total_gb": round(mem.total / (1024**3), 1),
                "memory_used_gb": round(mem.used / (1024**3), 1),
                "disk_total_gb": round(disk.total / (1024**3), 1),
                "disk_used_gb": round(disk.used / (1024**3), 1),
                "disk_usage_pct": round((disk.used / disk.total) * 100, 1)
            }
        })
    except Exception as e:
        module_logger.error(f"Get health error: {e}", exc_info=True)
        return SafeJSONResponse(
            {"score": 100, "status": "HEALTHY"},
            status_code=500
        )


@app.get("/system", tags=["Monitoring"])
async def get_system_info():
    """
    Get raw system information snapshot.
    
    Returns:
        Detailed laptop/desktop system stats
    """
    try:
        cpu_count = psutil.cpu_count()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()
        battery = psutil.sensors_battery()
        
        return SafeJSONResponse({
            "cpu": {
                "cores": cpu_count,
                "usage_percent": psutil.cpu_percent(interval=0.1)
            },
            "memory": {
                "total_gb": round(mem.total / (1024**3), 1),
                "used_gb": round(mem.used / (1024**3), 1),
                "available_gb": round(mem.available / (1024**3), 1),
                "usage_percent": mem.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "free_gb": round(disk.free / (1024**3), 1),
                "usage_percent": round((disk.used / disk.total) * 100, 1)
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "sent_mb": round(net_io.bytes_sent / (1024**2), 1),
                "recv_mb": round(net_io.bytes_recv / (1024**2), 1)
            },
            "battery": {
                "percent": battery.percent if battery else None,
                "charging": battery.power_plugged if battery else None,
                "seconds_left": battery.secsleft if battery and battery.secsleft > 0 else None
            } if battery else None
        })
    except Exception as e:
        module_logger.error(f"System info error: {e}", exc_info=True)
        return SafeJSONResponse({"error": "Failed to get system info"}, status_code=500)


@app.get("/stats", tags=["Monitoring"])
async def get_stats():
    """
    Get application statistics.
    
    Returns:
        Statistics dictionary
    """
    try:
        stats = app_state.get_stats()
        stats["detector_status"] = detector.get_status()
        stats["alert_stats"] = alert_manager.get_stats()
        
        return SafeJSONResponse(stats)
    except Exception as e:
        module_logger.error(f"Get stats error: {e}", exc_info=True)
        return SafeJSONResponse({"error": str(e)}, status_code=500)


@app.post("/simulate/{mode}", tags=["Simulation"])
async def simulate_mode(mode: str):
    """
    Set simulation mode for testing.
    
    Args:
        mode: One of "normal", "ddos", "memory_leak", "cpu_spike"
        
    Returns:
        Status message
    """
    if mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Valid modes: {sorted(VALID_MODES)}"
        )
    
    try:
        os.makedirs("logs", exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write(mode)
        
        module_logger.info(f"Simulation mode set to: {mode}")
        asyncio.create_task(_auto_reset_mode(delay=30))
        
        return SafeJSONResponse({
            "mode": mode,
            "auto_reset_seconds": 30,
            "message": f"Simulator switched to '{mode}' mode"
        })
    
    except Exception as e:
        module_logger.error(f"Simulation mode error: {e}", exc_info=True)
        return SafeJSONResponse(
            {"error": "Failed to set simulation mode"},
            status_code=500
        )


async def _auto_reset_mode(delay: int = 30):
    """Auto-reset simulation mode after delay."""
    try:
        await asyncio.sleep(delay)
        os.makedirs("logs", exist_ok=True)
        with open(MODE_FILE, "w") as f:
            f.write("normal")
        module_logger.info("Simulation mode auto-reset to 'normal'")
    except Exception as e:
        module_logger.error(f"Auto-reset error: {e}", exc_info=True)


@app.get("/detector/status", tags=["Monitoring"])
async def get_detector_status():
    """Get detector training status and statistics."""
    try:
        return SafeJSONResponse(detector.get_status())
    except Exception as e:
        module_logger.error(f"Get detector status error: {e}", exc_info=True)
        return SafeJSONResponse({"error": str(e)}, status_code=500)


@app.get("/", tags=["Info"])
async def root():
    """Get API information."""
    return SafeJSONResponse({
        "name": "AnomalyGuard",
        "version": "2.0.0",
        "status": "running",
        "health_score": app_state.health_score,
        "detector_trained": detector.is_trained,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.server.HOST,
        port=config.server.PORT,
        reload=config.server.RELOAD,
        log_level=config.logging.LOG_LEVEL.lower()
    )
