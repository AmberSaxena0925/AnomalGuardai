"""
state.py — Global Application State Management
"""

import time
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnomalyRecord:
    """A single anomaly record."""
    timestamp: str
    cpu_usage: float
    memory_usage: float
    response_time_ms: float
    requests_per_sec: float
    mode: str
    severity_level: str
    severity_color: str
    explanation: str
    score: float
    reason: str
    health_score: int


class AppState:
    """Thread-safe application state management."""
    
    def __init__(self):
        """Initialize application state."""
        self._lock = threading.RLock()
        
        # Core state
        self.detector_trained = False
        self.health_score = 100
        self.last_anomaly_time: Optional[float] = None
        self.start_time = time.time()
        
        # Storage
        self.logs: List[Dict[str, Any]] = []
        self.anomalies: List[Dict[str, Any]] = []
        
        # WebSocket clients
        self.connected_clients = set()
        
        # Statistics
        self.total_logs_processed = 0
        self.total_anomalies_detected = 0
        self.anomalies_by_severity: Dict[str, int] = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
        }
        
        logger.info("AppState initialized")
    
    def add_log(self, log_dict: Dict[str, Any]) -> None:
        """Add a log entry."""
        with self._lock:
            self.logs.append(log_dict)
            self.total_logs_processed += 1
            
            # Keep only recent logs (last 10000)
            if len(self.logs) > 10000:
                self.logs = self.logs[-10000:]
    
    def add_anomaly(self, anomaly: Dict[str, Any]) -> None:
        """Add an anomaly record."""
        with self._lock:
            self.anomalies.append(anomaly)
            self.total_anomalies_detected += 1
            
            severity = anomaly.get("severity_level", "NONE")
            if severity in self.anomalies_by_severity:
                self.anomalies_by_severity[severity] += 1
            
            self.last_anomaly_time = time.time()
            
            # Keep only recent anomalies (last 1000)
            if len(self.anomalies) > 1000:
                self.anomalies = self.anomalies[-1000:]
    
    def get_anomalies(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent anomalies."""
        with self._lock:
            return self.anomalies[-limit:] if limit > 0 else list(self.anomalies)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get application statistics."""
        with self._lock:
            uptime = time.time() - self.start_time
            return {
                "uptime_seconds": int(uptime),
                "total_logs_processed": self.total_logs_processed,
                "total_anomalies_detected": self.total_anomalies_detected,
                "anomalies_by_severity": dict(self.anomalies_by_severity),
                "health_score": self.health_score,
                "detector_trained": self.detector_trained,
                "connected_clients": len(self.connected_clients),
                "recent_anomalies": len(self.anomalies),
            }
    
    def update_health_score(self, new_score: int) -> None:
        """Update health score."""
        with self._lock:
            self.health_score = max(0, min(100, new_score))
    
    def add_client(self, client) -> None:
        """Add connected WebSocket client."""
        with self._lock:
            self.connected_clients.add(client)
            logger.debug(f"Client added. Total: {len(self.connected_clients)}")
    
    def remove_client(self, client) -> None:
        """Remove disconnected WebSocket client."""
        with self._lock:
            self.connected_clients.discard(client)
            logger.debug(f"Client removed. Total: {len(self.connected_clients)}")
    
    def get_clients(self) -> List:
        """Get list of connected clients."""
        with self._lock:
            return list(self.connected_clients)
    
    def set_detector_trained(self, trained: bool) -> None:
        """Set detector training status."""
        with self._lock:
            self.detector_trained = trained


# Global app state instance
app_state = AppState()
