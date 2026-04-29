"""
detector.py — Hybrid Anomaly Detection
Uses Isolation Forest with hard-threshold backup for robust anomaly detection.
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from config import config
from logger import get_logger

logger = get_logger(__name__)

FEATURES = ["cpu_usage", "memory_usage", "response_time_ms", "requests_per_sec"]


class AnomalyDetector:
    """
    Hybrid anomaly detector combining machine learning and hard thresholds.
    
    Uses Isolation Forest for pattern-based detection and hard thresholds
    as a backup for obvious anomalies (e.g., DDoS attacks).
    """
    
    def __init__(self) -> None:
        """Initialize the detector."""
        detector_cfg = config.detector
        
        self.model = IsolationForest(
            contamination=detector_cfg.ISOLATION_FOREST_CONTAMINATION,
            random_state=detector_cfg.RANDOM_STATE
        )
        self.thresholds = detector_cfg.THRESHOLDS
        self.threshold_trigger_count = detector_cfg.THRESHOLD_TRIGGER_COUNT
        self.initial_training_size = detector_cfg.INITIAL_TRAINING_SIZE
        self.retraining_interval = detector_cfg.RETRAINING_INTERVAL
        self.buffer_size = detector_cfg.BUFFER_SIZE
        
        self.buffer: list[list[float]] = []
        self.is_trained: bool = False
        self.log_count: int = 0
    
    def _extract_features(self, log_dict: dict) -> list[float]:
        """Extract feature values from log dictionary."""
        try:
            return [float(log_dict.get(f, 0.0)) for f in FEATURES]
        except (ValueError, TypeError) as e:
            logger.error(f"Error extracting features: {e}")
            return [0.0] * len(FEATURES)
    
    def _count_threshold_flags(self, log_dict: dict) -> int:
        """
        Count how many hard thresholds are exceeded.
        
        Returns:
            Number of thresholds exceeded
        """
        count = 0
        for feat, limit in self.thresholds.items():
            try:
                value = float(log_dict.get(feat, 0))
                if value > limit:
                    count += 1
            except (ValueError, TypeError):
                pass
        return count
    
    def add_log(self, log_dict: dict) -> None:
        """
        Add a log entry and trigger training if needed.
        
        Args:
            log_dict: Log dictionary with metrics
        """
        features = self._extract_features(log_dict)
        self.buffer.append(features)
        self.log_count += 1
        
        # Initial training trigger
        if self.log_count == self.initial_training_size:
            logger.info(f"Initial training triggered at {self.log_count} logs")
            self.train()
        
        # Periodic retraining
        elif self.is_trained and self.log_count % self.retraining_interval == 0:
            # Keep only recent logs
            self.buffer = self.buffer[-self.buffer_size:]
            logger.info(f"Retraining triggered at {self.log_count} logs")
            self.train()
    
    def train(self) -> None:
        """Train the Isolation Forest model."""
        try:
            if len(self.buffer) < 10:
                logger.warning("Not enough samples for training")
                return
            
            X = np.array(self.buffer)
            self.model.fit(X)
            self.is_trained = True
            logger.info(f"Model trained on {len(self.buffer)} samples")
        except Exception as e:
            logger.error(f"Training failed: {e}")
            self.is_trained = False
    
    def predict(self, log_dict: dict) -> dict:
        """
        Predict if a log entry is anomalous.
        
        Uses hybrid approach:
        1. Hard-threshold check (catches obvious anomalies)
        2. Isolation Forest (catches pattern-based anomalies)
        
        Args:
            log_dict: Log dictionary with metrics
            
        Returns:
            Dictionary with prediction results
        """
        # Hard-threshold check
        flags = self._count_threshold_flags(log_dict)
        threshold_anomaly = flags >= self.threshold_trigger_count
        
        if not self.is_trained:
            logger.debug("Model not trained, using threshold detection only")
            return {
                "is_anomaly": threshold_anomaly,
                "score": 0.0,
                "trained": False,
                "reason": "threshold" if threshold_anomaly else "none",
                "threshold_flags": flags,
            }
        
        # Isolation Forest check
        try:
            features = self._extract_features(log_dict)
            X = np.array([features])
            
            model_label = self.model.predict(X)[0]  # 1=normal, -1=anomaly
            score = float(self.model.decision_function(X)[0])  # lower=more anomalous
            model_anomaly = model_label == -1
            
            # Combine results
            is_anomaly = model_anomaly or threshold_anomaly
            
            if threshold_anomaly and model_anomaly:
                reason = "both"
            elif threshold_anomaly:
                reason = "threshold"
            elif model_anomaly:
                reason = "isolation_forest"
            else:
                reason = "none"
            
            return {
                "is_anomaly": is_anomaly,
                "score": round(score, 6),
                "trained": True,
                "reason": reason,
                "threshold_flags": flags,
            }
        
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {
                "is_anomaly": threshold_anomaly,
                "score": 0.0,
                "trained": False,
                "reason": "error",
                "threshold_flags": flags,
            }
    
    def get_status(self) -> dict:
        """
        Get detector status and statistics.
        
        Returns:
            Status dictionary
        """
        logs_until = max(0, self.initial_training_size - self.log_count) if not self.is_trained else 0
        
        return {
            "is_trained": self.is_trained,
            "log_count": self.log_count,
            "buffer_size": len(self.buffer),
            "logs_until_training": logs_until,
            "thresholds": self.thresholds,
            "threshold_trigger_count": self.threshold_trigger_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for __main__ test block
# ─────────────────────────────────────────────────────────────────────────────

def _make_normal() -> dict:
    return {
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "cpu_usage":        random.uniform(10, 65),
        "memory_usage":     random.uniform(20, 70),
        "response_time_ms": random.uniform(100, 800),
        "requests_per_sec": random.uniform(10, 500),
        "mode":             "normal",
    }


def _make_anomaly() -> dict:
    """Simulate a DDoS-style anomaly."""
    return {
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "cpu_usage":        random.uniform(85, 100),
        "memory_usage":     random.uniform(88, 100),
        "response_time_ms": random.uniform(5000, 9000),
        "requests_per_sec": random.uniform(3000, 5000),
        "mode":             "ddos",
    }


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 72)
    print("  AnomalyGuard — detector.py self-test")
    print("  60 normal logs → train → 5 forced anomalies")
    print("═" * 72)

    detector = AnomalyDetector()

    # ── Phase 1: feed 60 normal logs ─────────────────────────────────────────
    print("\n── Feeding 60 normal logs …\n")
    for i in range(1, 61):
        log = _make_normal()
        detector.add_log(log)
        result = detector.predict(log)

        tag = "🚨 ANOMALY" if result["is_anomaly"] else "✅ normal "
        print(
            f"  [{i:>2}] {tag}  "
            f"CPU={log['cpu_usage']:>5.1f}%  MEM={log['memory_usage']:>5.1f}%  "
            f"RT={log['response_time_ms']:>7.1f}ms  RPS={log['requests_per_sec']:>6.1f}  "
            f"score={result['score']:>8.5f}  trained={result['trained']}  reason={result['reason']}"
        )

    # ── Status after training ─────────────────────────────────────────────────
    print(f"\n── Detector status: {detector.get_status()}\n")

    # ── Phase 2: 5 forced anomalies ───────────────────────────────────────────
    print("── Sending 5 forced DDoS-style anomalies …\n")
    for i in range(1, 6):
        log = _make_anomaly()
        detector.add_log(log)
        result = detector.predict(log)

        tag = "🚨 ANOMALY" if result["is_anomaly"] else "✅ normal "
        print(
            f"  [A{i}] {tag}  "
            f"CPU={log['cpu_usage']:>5.1f}%  MEM={log['memory_usage']:>5.1f}%  "
            f"RT={log['response_time_ms']:>7.1f}ms  RPS={log['requests_per_sec']:>6.1f}  "
            f"score={result['score']:>8.5f}  flags={result['threshold_flags']}  reason={result['reason']}"
        )

    print("\n" + "═" * 72)
    print(f"  Final status: {detector.get_status()}")
    print("═" * 72)