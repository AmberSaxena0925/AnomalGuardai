import json
import os
import random
import time
from datetime import datetime, timezone
import traceback
import requests


# ── FIXED BASE PATH LOGIC ───────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "logs")

MODE_FILE  = os.path.join(LOGS_DIR, "current_mode.txt")
JSONL_FILE = os.path.join(LOGS_DIR, "latest.jsonl")

INGEST_URL = "http://localhost:8000/ingest"


# ── stateful counters for anomaly modes ─────────────────────────────────

_memory_leak_pct  = 40.0
_cpu_spike_count  = 0


def read_mode() -> str:
    """Return current mode string, defaulting to 'normal' if file is missing."""
    try:
        print(f"[DEBUG] os.getcwd(): {os.getcwd()}")
        print(f"[DEBUG] MODE_FILE absolute path: {MODE_FILE}")

        if not os.path.exists(MODE_FILE):
            print(f"[DEBUG] Mode file not found, defaulting to 'normal'")
            return "normal"

        with open(MODE_FILE, "r", encoding="utf-8-sig") as f:
            raw = f.read()

        print(f"[DEBUG] Raw file contents: {repr(raw)}")

        mode = raw.strip().lower()
        print(f"[DEBUG] Parsed mode string: {repr(mode)}")

        if not mode:
            return "normal"

        if mode not in ("normal", "ddos", "memory_leak", "cpu_spike"):
            print(f"[WARN] Unknown mode '{mode}' — defaulting to 'normal'")
            return "normal"

        return mode

    except Exception as exc:
        print("[ERROR] Exception inside read_mode():", exc)
        traceback.print_exc()
        return "normal"


def generate_log(mode: str) -> dict:
    global _memory_leak_pct, _cpu_spike_count

    ts = datetime.now(timezone.utc).isoformat()

    if mode == "normal":
        if random.random() < 0.90:
            cpu = random.uniform(10, 65)
            memory = random.uniform(20, 70)
            response = random.uniform(100, 800)
            rps = random.uniform(10, 500)
        else:
            cpu = random.uniform(70, 100)
            memory = random.uniform(75, 95)
            response = random.uniform(1000, 4000)
            rps = random.uniform(500, 2000)

    elif mode == "ddos":
        cpu = random.uniform(85, 100)
        memory = random.uniform(88, 100)
        response = random.uniform(5000, 9000)
        rps = random.uniform(3000, 5000)

    elif mode == "memory_leak":
        _memory_leak_pct = min(_memory_leak_pct + 2.0, 97.0)
        cpu = random.uniform(10, 65)
        memory = _memory_leak_pct + random.uniform(-0.5, 0.5)
        response = random.uniform(100, 800)
        rps = random.uniform(10, 500)

    elif mode == "cpu_spike":
        _cpu_spike_count += 1
        if _cpu_spike_count <= 10:
            cpu = random.uniform(90, 98)
        else:
            cpu = random.uniform(10, 65)
            if _cpu_spike_count >= 20:
                _cpu_spike_count = 0
        memory = random.uniform(20, 70)
        response = random.uniform(100, 800)
        rps = random.uniform(10, 500)

    else:
        cpu = memory = response = rps = 0.0

    return {
        "timestamp": ts,
        "cpu_usage": round(cpu, 2),
        "memory_usage": round(memory, 2),
        "response_time_ms": round(response, 2),
        "requests_per_sec": round(rps, 2),
        "mode": mode,
    }


def post_log(log: dict) -> bool:
    try:
        resp = requests.post(INGEST_URL, json=log, timeout=3)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[POST FAILED] {exc}")
        return False


def append_to_file(log: dict) -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(JSONL_FILE, "a") as f:
        f.write(json.dumps(log) + "\n")


def main() -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)

    print("═" * 60)
    print("AnomalyGuard — Log Simulator")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Mode file path: {MODE_FILE}")
    print("═" * 60)

    while True:
        mode = read_mode()
        log = generate_log(mode)

        status_icon = {
            "normal": "✅",
            "ddos": "🚨",
            "memory_leak": "🧠",
            "cpu_spike": "🔥"
        }.get(mode, "❓")

        print(
            f"{status_icon} [{log['timestamp']}] MODE={mode:<12} "
            f"CPU={log['cpu_usage']:>6.2f}% "
            f"MEM={log['memory_usage']:>6.2f}% "
            f"RT={log['response_time_ms']:>8.1f}ms "
            f"RPS={log['requests_per_sec']:>8.1f}"
        )

        ok = post_log(log)
        if not ok:
            print(f"[FALLBACK] {json.dumps(log)}")

        append_to_file(log)
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("[FATAL] Unhandled exception:", exc)
        traceback.print_exc()

        