"""
explainer.py — AI-Powered Anomaly Explanations
"""

import os
import requests
from typing import Dict
from dotenv import load_dotenv
from logger import get_logger
from config import config

load_dotenv()
logger = get_logger(__name__)


class AnomalyExplainer:
    """Generates AI-powered explanations for anomalies."""
    
    def __init__(self):
        """Initialize the explainer."""
        self.api_key = config.explainer.OPENROUTER_KEY
        self.api_url = config.explainer.OPENROUTER_URL
        self.model = config.explainer.MODEL
        self.timeout = config.explainer.TIMEOUT
        self.fallback_to_simple = config.explainer.FALLBACK_TO_SIMPLE
        
        self.api_calls_made = 0
        self.api_calls_failed = 0
    
    def _generate_simple_explanation(self, log_dict: Dict) -> str:
        """Generate a simple rule-based explanation."""
        cpu = log_dict.get("cpu_usage", 0)
        memory = log_dict.get("memory_usage", 0)
        rps = log_dict.get("requests_per_sec", 0)
        response_time = log_dict.get("response_time_ms", 0)
        mode = log_dict.get("mode", "normal")
        
        # Rule-based explanations
        if rps > 3000:
            reason = "High request rate detected"
        elif response_time > 4000:
            reason = "High response time indicating latency issues"
        elif cpu > 85:
            reason = "CPU utilization critically high"
        elif memory > 85:
            reason = "Memory usage critically high"
        else:
            reason = "Anomalous behavior detected"
        
        if mode != "normal":
            reason += f" (Mode: {mode})"
        
        return reason
    
    def _generate_ai_explanation(self, log_dict: Dict, severity_level: str) -> str:
        """
        Generate explanation using OpenRouter API.
        
        Args:
            log_dict: Log dictionary with metrics
            severity_level: Severity level of the anomaly
            
        Returns:
            Explanation string
        """
        try:
            cpu = log_dict.get("cpu_usage", 0)
            memory = log_dict.get("memory_usage", 0)
            rps = log_dict.get("requests_per_sec", 0)
            response_time = log_dict.get("response_time_ms", 0)
            mode = log_dict.get("mode", "normal")
            
            prompt = f"""You are an infrastructure monitoring AI. Analyze this anomaly and provide a brief, actionable explanation.

Anomaly Detected:
- Severity: {severity_level}
- CPU Usage: {cpu:.1f}%
- Memory Usage: {memory:.1f}%
- Response Time: {response_time}ms
- Requests/sec: {rps:.1f}
- Mode: {mode}

Provide a concise explanation (1-2 sentences) of what likely caused this anomaly and what action to take."""

            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "max_tokens": 100,
                },
                timeout=self.timeout,
            )
            
            self.api_calls_made += 1
            
            if response.status_code == 200:
                result = response.json()
                explanation = result["choices"][0]["message"]["content"].strip()
                logger.debug(f"AI explanation generated: {explanation}")
                return explanation
            else:
                logger.warning(f"OpenRouter API returned status {response.status_code}")
                self.api_calls_failed += 1
                raise Exception(f"API returned status {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning("OpenRouter API call timed out")
            self.api_calls_failed += 1
            return self._generate_simple_explanation(log_dict)
        except requests.exceptions.RequestException as e:
            logger.warning(f"OpenRouter API request failed: {e}")
            self.api_calls_failed += 1
            return self._generate_simple_explanation(log_dict)
        except (KeyError, IndexError) as e:
            logger.warning(f"Failed to parse OpenRouter response: {e}")
            self.api_calls_failed += 1
            return self._generate_simple_explanation(log_dict)
        except Exception as e:
            logger.error(f"Unexpected error in AI explanation: {e}")
            self.api_calls_failed += 1
            return self._generate_simple_explanation(log_dict)
    
    def explain(self, log_dict: Dict, severity_level: str) -> str:
        """
        Generate explanation for an anomaly.
        
        Args:
            log_dict: Log dictionary with metrics
            severity_level: Severity level of the anomaly
            
        Returns:
            Explanation string
        """
        # If API key not configured, use simple explanation
        if not self.api_key:
            logger.debug("OpenRouter API key not configured, using simple explanation")
            return self._generate_simple_explanation(log_dict)
        
        # Try AI explanation
        explanation = self._generate_ai_explanation(log_dict, severity_level)
        
        # If AI explanation failed and fallback enabled, use simple
        if not explanation and self.fallback_to_simple:
            logger.debug("AI explanation failed, falling back to simple explanation")
            explanation = self._generate_simple_explanation(log_dict)
        
        return explanation or "Anomaly detected"
    
    def get_stats(self) -> Dict:
        """Get explainer statistics."""
        return {
            "api_calls_made": self.api_calls_made,
            "api_calls_failed": self.api_calls_failed,
        }


# Global explainer instance
explainer = AnomalyExplainer()


def explain_anomaly(log_dict: Dict, severity_level: str) -> str:
    """Convenience function for backward compatibility."""
    return explainer.explain(log_dict, severity_level)