"""
alerter.py — Alert Management and Notifications
"""

import requests
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self, slack_webhook: Optional[str] = None):
        """
        Initialize alert manager.
        
        Args:
            slack_webhook: Slack webhook URL for notifications
        """
        self.slack_webhook = slack_webhook or os.getenv("SLACK_WEBHOOK", "")
        self.alerts_sent = 0
        self.alerts_failed = 0
    
    def send_slack_alert(self, anomaly: Dict[str, Any]) -> bool:
        """
        Send Slack notification for anomaly.
        
        Args:
            anomaly: Anomaly record dictionary
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.slack_webhook:
            logger.debug("Slack webhook not configured, skipping alert")
            return False
        
        try:
            severity = anomaly.get("severity_level", "UNKNOWN")
            emoji = self._get_emoji_for_severity(severity)
            
            message = {
                "text": f"{emoji} AnomalyGuard Alert: {severity}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} {severity} Anomaly Detected",
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*CPU Usage:*\n{anomaly.get('cpu_usage', 'N/A'):.1f}%"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Memory Usage:*\n{anomaly.get('memory_usage', 'N/A'):.1f}%"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Response Time:*\n{anomaly.get('response_time_ms', 'N/A'):.0f}ms"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*RPS:*\n{anomaly.get('requests_per_sec', 'N/A'):.1f}"
                            },
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Explanation:*\n{anomaly.get('explanation', 'No explanation available')}"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Timestamp: {anomaly.get('timestamp', 'N/A')} | Health Score: {anomaly.get('health_score', 'N/A')}"
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                self.slack_webhook,
                json=message,
                timeout=5
            )
            response.raise_for_status()
            
            self.alerts_sent += 1
            logger.info(f"Slack alert sent for {severity} anomaly")
            return True
            
        except requests.exceptions.RequestException as e:
            self.alerts_failed += 1
            logger.warning(f"Failed to send Slack alert: {e}")
            return False
        except Exception as e:
            self.alerts_failed += 1
            logger.error(f"Unexpected error sending Slack alert: {e}")
            return False
    
    @staticmethod
    def _get_emoji_for_severity(severity: str) -> str:
        """Get emoji for severity level."""
        emojis = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "⚡",
            "LOW": "ℹ️",
        }
        return emojis.get(severity, "📊")
    
    def get_stats(self) -> Dict[str, int]:
        """Get alert statistics."""
        return {
            "alerts_sent": self.alerts_sent,
            "alerts_failed": self.alerts_failed,
        }


# Global alert manager instance
alert_manager = AlertManager()
