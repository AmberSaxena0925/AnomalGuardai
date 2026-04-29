"""
severity.py — Severity Calculation and Classification
"""

from config import config
from logger import get_logger

logger = get_logger(__name__)


def calculate_severity(log_dict: dict) -> str:
    """
    Calculate anomaly severity based on metric values.
    
    Args:
        log_dict: Dictionary with metrics (cpu_usage, memory_usage, etc.)
        
    Returns:
        Severity level: "CRITICAL", "HIGH", "MEDIUM", or "LOW"
    """
    cpu = log_dict.get("cpu_usage", 0)
    memory = log_dict.get("memory_usage", 0)
    disk = log_dict.get("disk_usage", 0)
    net_sent = log_dict.get("network_sent", 0)
    net_recv = log_dict.get("network_recv", 0)
    battery = log_dict.get("battery_pct", 100)  # assume 100 if not present
    rps = log_dict.get("requests_per_sec", 0)
    rt = log_dict.get("response_time_ms", 0)
    
    # Check critical thresholds
    critical_thresholds = config.severity.CRITICAL_THRESHOLDS
    if (cpu > critical_thresholds["cpu_usage"] or 
        memory > critical_thresholds["memory_usage"] or 
        disk > critical_thresholds["disk_usage"] or
        net_sent > critical_thresholds["network_sent"] or
        net_recv > critical_thresholds["network_recv"] or
        battery < critical_thresholds["battery_pct"] or
        rps > critical_thresholds["requests_per_sec"] or 
        rt > critical_thresholds["response_time_ms"]):
        return "CRITICAL"
    
    # Check high thresholds
    high_thresholds = config.severity.HIGH_THRESHOLDS
    if (cpu > high_thresholds["cpu_usage"] or 
        memory > high_thresholds["memory_usage"] or 
        disk > high_thresholds["disk_usage"] or
        net_sent > high_thresholds["network_sent"] or
        net_recv > high_thresholds["network_recv"] or
        battery < high_thresholds["battery_pct"] or
        rps > high_thresholds["requests_per_sec"]):
        return "HIGH"
    
    # Check medium thresholds
    medium_thresholds = config.severity.MEDIUM_THRESHOLDS
    if (cpu > medium_thresholds["cpu_usage"] or 
        memory > medium_thresholds["memory_usage"] or
        disk > medium_thresholds["disk_usage"] or
        net_sent > medium_thresholds["network_sent"] or
        net_recv > medium_thresholds["network_recv"] or
        battery < medium_thresholds["battery_pct"]):
        return "MEDIUM"
    
    return "LOW"


def get_severity_color(severity_level: str) -> str:
    """Get color code for severity level."""
    return config.severity.SEVERITY_COLOR.get(severity_level, "#FF0000")


def get_severity_penalty(severity_level: str) -> int:
    """Get health score penalty for severity level."""
    return config.severity.SEVERITY_PENALTY.get(severity_level, 5)