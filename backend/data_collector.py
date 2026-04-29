"""
data_collector.py — Live System Metrics Collector for AnomalyGuard
Collects CPU, memory, response time, and request metrics from the system
and sends them to the backend's /ingest endpoint.

Run: python data_collector.py
"""

import psutil
import requests
import time
import random
import logging
from datetime import datetime
import os
from typing import Dict, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/ingest")
COLLECTION_INTERVAL = int(os.getenv("COLLECTION_INTERVAL", "2"))  # Seconds
MODE_FILE = "logs/current_mode.txt"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
REQUEST_TIMEOUT = 5  # seconds

# Current mode
current_mode = "normal"
mode_change_count = 0


# ─────────────────────────────────────────────────────────────────────────────
# Metrics Collection
# ─────────────────────────────────────────────────────────────────────────────

def get_cpu_usage() -> float:
    """
    Get CPU usage percentage.
    
    Returns:
        CPU usage as percentage (0-100)
    """
    try:
        return psutil.cpu_percent(interval=0.5)
    except Exception as e:
        logger.warning(f"Failed to get CPU usage: {e}")
        return 0.0


def get_memory_usage() -> float:
    """
    Get memory usage percentage.
    
    Returns:
        Memory usage as percentage (0-100)
    """
    try:
        return psutil.virtual_memory().percent
    except Exception as e:
        logger.warning(f"Failed to get memory usage: {e}")
        return 0.0


def get_disk_usage() -> float:
    """
    Get disk usage percentage.
    
    Returns:
        Disk usage as percentage (0-100)
    """
    try:
        usage = psutil.disk_usage('/')
        return (usage.used / usage.total) * 100
    except Exception as e:
        logger.debug(f"Failed to get disk usage: {e}")
        return 0.0


def get_network_io() -> tuple:
    """
    Get network sent/received bytes per second.
    
    Returns:
        Tuple of (bytes_sent_per_sec, bytes_recv_per_sec)
    """
    try:
        counters = psutil.net_io_counters()
        return counters.bytes_sent, counters.bytes_recv
    except Exception as e:
        logger.debug(f"Failed to get network IO: {e}")
        return 0, 0


def get_battery_pct() -> float:
    """
    Get battery percentage for laptops (0 if desktop).
    
    Returns:
        Battery percentage (0-100) or 0
    """
    try:
        battery = psutil.sensors_battery()
        return battery.percent if battery else 0.0
    except Exception as e:
        logger.debug(f"Failed to get battery: {e}")
        return 0.0


def get_response_time_ms(mode: str) -> float:
    """
    Simulate response time based on mode.
    
    Args:
        mode: Current simulation mode
        
    Returns:
        Response time in milliseconds
    """
    base_time = 100
    
    if mode == "normal":
        return base_time + random.uniform(-20, 50)
    elif mode == "ddos":
        return random.uniform(500, 5000)
    elif mode == "memory_leak":
        return base_time + random.uniform(100, 700)
    elif mode == "cpu_spike":
        return random.uniform(150, 2000)
    else:
        return base_time + random.uniform(-20, 50)


def get_requests_per_sec(mode: str) -> float:
    """
    Simulate requests per second based on mode.
    
    Args:
        mode: Current simulation mode
        
    Returns:
        Requests per second
    """
    base_rps = 50
    
    if mode == "normal":
        return base_rps + random.uniform(-10, 10)
    elif mode == "ddos":
        return random.uniform(1000, 5000)
    elif mode == "memory_leak":
        return base_rps - random.uniform(0, 30)
    elif mode == "cpu_spike":
        return random.uniform(30, 200)
    else:
        return base_rps + random.uniform(-10, 10)


def read_current_mode() -> str:
    """
    Read current mode from mode file (set by backend /simulate endpoint).
    
    Returns:
        Current simulation mode
    """
    try:
        if os.path.exists(MODE_FILE):
            with open(MODE_FILE, "r") as f:
                mode = f.read().strip()
                if mode in ["normal", "ddos", "memory_leak", "cpu_spike"]:
                    return mode
    except Exception as e:
        logger.debug(f"Could not read mode file: {e}")
    
    return "normal"


# ─────────────────────────────────────────────────────────────────────────────
# Data Ingestion with Retry Logic
# ─────────────────────────────────────────────────────────────────────────────

def send_metric_with_retry(
    cpu: float,
    memory: float,
    disk: float,
    net_sent: int,
    net_recv: int,
    battery: float,
    response_time: float,
    rps: float,
    mode: str
) -> Tuple[bool, str]:
    """
    Send metric to backend with retry logic.
    
    Args:
        cpu: CPU usage percentage
        memory: Memory usage percentage
        disk: Disk usage percentage
        net_sent: Network bytes sent
        net_recv: Network bytes received
        battery: Battery percentage
        response_time: Response time in milliseconds
        rps: Requests per second
        mode: Current simulation mode
        
    Returns:
        Tuple of (success: bool, severity: str)
    """
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cpu_usage": cpu,
        "memory_usage": memory,
        "disk_usage": disk,
        "network_sent": net_sent,
        "network_recv": net_recv,
        "battery_pct": battery,
        "response_time_ms": response_time,
        "requests_per_sec": rps,
        "mode": mode,
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                BACKEND_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    return (
                        result.get("is_anomaly", False),
                        result.get("severity", "NONE")
                    )
                except Exception as e:
                    logger.error(f"Failed to parse response: {e}")
                    return False, "NONE"
            
            elif response.status_code == 422:
                logger.error(f"Validation error: {response.text}")
                return False, "NONE"
            
            else:
                logger.warning(f"Backend returned status {response.status_code}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return False, "NONE"
        
        except requests.exceptions.ConnectionError:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Connection failed (attempt {attempt + 1}/{MAX_RETRIES}), retrying...")
                time.sleep(RETRY_DELAY)
                continue
            else:
                logger.error(f"Cannot connect to backend at {BACKEND_URL} after {MAX_RETRIES} attempts")
                return False, "ERROR"
        
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{MAX_RETRIES}), retrying...")
                time.sleep(RETRY_DELAY)
                continue
            else:
                logger.error("Backend request timed out after retries")
                return False, "TIMEOUT"
        
        except Exception as e:
            logger.error(f"Unexpected error sending metric: {e}")
            return False, "NONE"
    
    return False, "NONE"


def format_metric_line(
    cpu: float, memory: float, disk: float, net_sent: int, net_recv: int,
    battery: float, response_time: float, rps: float,
    mode: str, is_anomaly: bool, severity: str
) -> str:
    """
    Format metric data for display.
    """
    status = "🚨" if is_anomaly else "✅"
    severity_color = {
        "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢",
        "NONE": "⚪", "ERROR": "❌", "TIMEOUT": "⏱️"
    }.get(severity, "❓")
    
    net_mb = (net_sent + net_recv) / (1024*1024)  # Total MB
    batt_str = f"{battery:.0f}%" if battery > 0 else "---"
    
    return (
        f"[{datetime.now().strftime('%H:%M:%S')}] {status} {severity_color} | "
        f"CPU={cpu:4.1f}% MEM={memory:4.1f}% DSK={disk:4.1f}% | "
        f"NET={net_mb:5.1f}MB BATT={batt_str} | "
        f"RT={response_time:4.0f} RPS={rps:4.0f} | "
        f"{mode[:8]} | {severity}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main Loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Main data collection loop."""
    global current_mode, mode_change_count
    
    print("=" * 120)
    print("AnomalyGuard — Live System Metrics Collector (Improved)")
    print("=" * 120)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Collection interval: {COLLECTION_INTERVAL}s")
    print(f"Request timeout: {REQUEST_TIMEOUT}s")
    print(f"Max retries: {MAX_RETRIES}")
    print()
    print("To trigger anomalies from the frontend:")
    print("  1. Go to http://localhost:3000 or http://localhost:3001 (frontend)")
    print("  2. Click 'SIMULATE' buttons (DDoS, Memory Leak, CPU Spike)")
    print("  3. Watch anomalies appear below!")
    print()
    print("=" * 120)
    print()
    
    logger.info("Data collector started")
    failed_attempts = 0
    
    try:
        while True:
            # Check for mode changes
            new_mode = read_current_mode()
            if new_mode != current_mode:
                current_mode = new_mode
                mode_change_count += 1
                logger.info(f"Mode changed to: {current_mode} (change #{mode_change_count})")
                print()
            
            # Collect metrics
            try:
                cpu = get_cpu_usage()
                memory = get_memory_usage()
                disk = get_disk_usage()
                net_sent, net_recv = get_network_io()
                battery = get_battery_pct()
                response_time = get_response_time_ms(current_mode)
                rps = get_requests_per_sec(current_mode)
                
                # Send to backend with retries
                is_anomaly, severity = send_metric_with_retry(
                    cpu, memory, disk, net_sent, net_recv, battery, response_time, rps, current_mode
                )
                
                # Display result
                output = format_metric_line(
                    cpu, memory, disk, net_sent, net_recv, battery,
                    response_time, rps, current_mode, is_anomaly, severity
                )
                print(output)
                
                # Reset failed attempts on success
                if severity != "ERROR" and severity != "TIMEOUT":
                    failed_attempts = 0
                else:
                    failed_attempts += 1
                    if failed_attempts >= 5:
                        logger.warning("Multiple consecutive failures detected")
                
            except Exception as e:
                logger.error(f"Error in collection loop: {e}", exc_info=True)
            
            # Wait before next collection
            time.sleep(COLLECTION_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n")
        logger.info("Data collector stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Data collector exited")


if __name__ == "__main__":
    main()
