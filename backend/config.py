"""
config.py — Centralized Configuration for AnomalyGuard Backend
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ServerConfig:
    """Server configuration settings."""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    RELOAD: bool = True


@dataclass
class DetectorConfig:
    """Anomaly detector configuration."""
    ISOLATION_FOREST_CONTAMINATION: float = 0.1
    INITIAL_TRAINING_SIZE: int = 50
    RETRAINING_INTERVAL: int = 200
    BUFFER_SIZE: int = 200
    RANDOM_STATE: int = 42
    
    # Hard thresholds for anomaly detection
    THRESHOLDS: dict = None
    
    def __post_init__(self):
        if self.THRESHOLDS is None:
            self.THRESHOLDS = {
                "cpu_usage": 85.0,
                "memory_usage": 85.0,
                "disk_usage": 90.0,
                "network_sent": 10000000.0,  # 10MB
                "network_recv": 10000000.0,  # 10MB
                "battery_pct": 20.0,  # low battery
                "response_time_ms": 4000.0,
                "requests_per_sec": 2500.0,
            }
    
    THRESHOLD_TRIGGER_COUNT: int = 2


@dataclass
class SeverityConfig:
    """Severity calculation configuration."""
    SEVERITY_PENALTY: dict = None
    SEVERITY_COLOR: dict = None
    
    # Thresholds for severity levels
    CRITICAL_THRESHOLDS: dict = None
    HIGH_THRESHOLDS: dict = None
    MEDIUM_THRESHOLDS: dict = None
    
    def __post_init__(self):
        if self.SEVERITY_PENALTY is None:
            self.SEVERITY_PENALTY = {
                "CRITICAL": 20,
                "HIGH": 10,
                "MEDIUM": 5,
                "LOW": 2,
            }
        
        if self.SEVERITY_COLOR is None:
            self.SEVERITY_COLOR = {
                "CRITICAL": "#FF0000",
                "HIGH": "#FF6600",
                "MEDIUM": "#FFB300",
                "LOW": "#00C853",
                "NONE": "#4CAF50",
            }
        
        if self.CRITICAL_THRESHOLDS is None:
            self.CRITICAL_THRESHOLDS = {
                "cpu_usage": 95,
                "memory_usage": 95,
                "disk_usage": 98,
                "network_sent": 50000000,  # 50MB
                "network_recv": 50000000,  # 50MB
                "battery_pct": 10,  # low battery
                "requests_per_sec": 4500,
                "response_time_ms": 8000,
            }
        
        if self.HIGH_THRESHOLDS is None:
            self.HIGH_THRESHOLDS = {
                "cpu_usage": 85,
                "memory_usage": 85,
                "disk_usage": 95,
                "network_sent": 20000000,  # 20MB
                "network_recv": 20000000,  # 20MB
                "battery_pct": 20,  # low battery
                "requests_per_sec": 3000,
            }
        
        if self.MEDIUM_THRESHOLDS is None:
            self.MEDIUM_THRESHOLDS = {
                "cpu_usage": 75,
                "memory_usage": 75,
                "disk_usage": 90,
                "network_sent": 10000000,  # 10MB
                "network_recv": 10000000,  # 10MB
                "battery_pct": 30,  # low battery
            }


@dataclass
class HealthConfig:
    """Health monitoring configuration."""
    RECOVERY_INTERVAL: int = 60  # seconds
    RECOVERY_RATE: int = 1  # points per interval
    ANOMALY_FREE_THRESHOLD: int = 60  # seconds without anomalies to recover
    INITIAL_HEALTH: int = 100


@dataclass
class APIConfig:
    """API configuration."""
    CORS_ORIGINS: list = None
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list = None
    CORS_HEADERS: list = None
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Request validation
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    def __post_init__(self):
        if self.CORS_ORIGINS is None:
            # Restrict to localhost in production
            self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
        
        if self.CORS_METHODS is None:
            self.CORS_METHODS = ["GET", "POST", "OPTIONS", "DELETE", "PUT"]
        
        if self.CORS_HEADERS is None:
            self.CORS_HEADERS = ["*"]


@dataclass
class ExplainerConfig:
    """AI explainer configuration."""
    OPENROUTER_KEY: str = os.getenv("OPENROUTER_KEY", "")
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    MODEL: str = "openai/gpt-3.5-turbo"
    TIMEOUT: int = 5  # seconds
    FALLBACK_TO_SIMPLE: bool = True  # Use simple explanation if API fails


@dataclass
class DatabaseConfig:
    """Database configuration."""
    DB_PATH: str = "logs/anomalyguard.db"
    ENABLE_PERSISTENCE: bool = True
    BATCH_SIZE: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration."""
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "logs/backend.log"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ENABLE_FILE_LOGGING: bool = True
    ENABLE_CONSOLE_LOGGING: bool = True


@dataclass
class AppConfig:
    """Main application configuration."""
    server: ServerConfig = None
    detector: DetectorConfig = None
    severity: SeverityConfig = None
    health: HealthConfig = None
    api: APIConfig = None
    explainer: ExplainerConfig = None
    database: DatabaseConfig = None
    logging: LoggingConfig = None
    
    def __post_init__(self):
        self.server = self.server or ServerConfig()
        self.detector = self.detector or DetectorConfig()
        self.severity = self.severity or SeverityConfig()
        self.health = self.health or HealthConfig()
        self.api = self.api or APIConfig()
        self.explainer = self.explainer or ExplainerConfig()
        self.database = self.database or DatabaseConfig()
        self.logging = self.logging or LoggingConfig()


# Global config instance
config = AppConfig()
