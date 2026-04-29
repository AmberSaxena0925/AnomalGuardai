# AnomalyGuard — Evaluation Q&A

This document contains comprehensive questions and answers about the AnomalyGuard project for the evaluation phase.

---

## 1. Project Overview

### Q1.1: What is AnomalyGuard?
**A:** AnomalyGuard is a real-time anomaly detection system for infrastructure monitoring. It uses machine learning to detect anomalies in system performance metrics such as CPU usage, memory consumption, response times, and request rates. The system provides real-time monitoring, anomaly detection, alerting, and visualization through a web dashboard.

### Q1.2: What are the main components of AnomalyGuard?
**A:** The system consists of three main components:
- **Backend API** (Python/FastAPI): Handles data ingestion, anomaly detection, and alerting
- **Data Collector** (Python): Collects system metrics and sends them to the backend
- **Frontend Dashboard** (React): Real-time visualization and control interface

### Q1.3: What technologies are used?
**A:**
- Backend: Python, FastAPI, scikit-learn (Isolation Forest), psutil
- Frontend: React, Recharts, Tailwind CSS
- ML: Isolation Forest algorithm from scikit-learn
- Optional: OpenRouter API for AI explanations, Slack for alerts

---

## 2. Architecture & Data Flow

### Q2.1: How does data flow through the system?
**A:**
1. **Data Collector** collects system metrics (CPU, memory, disk, network, battery) every 2 seconds
2. Metrics are sent to the **Backend API** via POST to `/ingest` endpoint
3. Backend performs anomaly detection using Hybrid detection (Isolation Forest + hard thresholds)
4. If anomaly is detected, severity is calculated and explanation is generated
5. Results are stored in **AppState** and broadcast to connected clients via WebSocket
6. Optionally, **Slack alerts** are sent for critical anomalies

### Q2.2: What is the directory structure?
```
anomalyguard/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── data_collector.py   # Metrics collector
│   ├── config.py          # Configuration
│   ├── logger.py         # Logging
│   ├── core/
│   │   ├── detector.py   # ML anomaly detection
│   │   ├── explainer.py # AI explanations
│   │   ├── severity.py  # Severity classification
│   │   ├── state.py    # State management
│   │   ├── alerter.py # Slack alerting
│   │   └── ...
│   └── logs/
└── frontend/
    ├── src/
    │   └── App.js      # React dashboard
    └── package.json
```

---

## 3. Anomaly Detection Algorithm

### Q3.1: What detection algorithm is used?
**A:** AnomalyGuard uses a **Hybrid Anomaly Detection** approach combining:
1. **Isolation Forest** (machine learning): Catches pattern-based anomalies
2. **Hard Thresholds** (rule-based): Catches obvious anomalies like DDoS attacks

### Q3.2: How does Isolation Forest work?
**A:** Isolation Forest is an unsupervised ML algorithm that:
- Works by randomly selecting a feature and split value
- Anomalies are easier to "isolate" (require fewer splits)
- Returns an anomaly score (more negative = more anomalous)
- Lower contamination = stricter detection

### Q3.3: What features are used for detection?
**A:** Four main features:
- `cpu_usage` (0-100%)
- `memory_usage` (0-100%)
- `response_time_ms` (milliseconds)
- `requests_per_sec` (requests per second)

### Q3.4: When does the model train?
**A:**
- **Initial training**: After collecting 50 logs (`INITIAL_TRAINING_SIZE`)
- **Retraining**: Every 200 logs (`RETRAINING_INTERVAL`)
- Uses sliding buffer of last 200 logs (`BUFFER_SIZE`)

### Q3.5: What are the hard thresholds?
**A:**
| Metric | Threshold |
|--------|-----------|
| cpu_usage | 85% |
| memory_usage | 85% |
| disk_usage | 90% |
| network_sent | 10MB |
| network_recv | 10MB |
| battery_pct | 20% |
| response_time_ms | 4000ms |
| requests_per_sec | 2500 |

An anomaly is flagged when 2+ thresholds are exceeded (`THRESHOLD_TRIGGER_COUNT`).

---

## 4. Severity Classification

### Q4.1: What severity levels exist?
**A:** Four levels:
- **CRITICAL**: Immediate attention required
- **HIGH**: High priority issue
- **MEDIUM**: Moderate issue
- **LOW**: Minor issue

### Q4.2: How is severity calculated?
**A:** Based on threshold comparisons:

**CRITICAL thresholds:**
- CPU > 95%, Memory > 95%, Disk > 98%
- Network > 50MB, Battery < 10%
- Response time > 8000ms, Requests/sec > 4500

**HIGH thresholds:**
- CPU > 85%, Memory > 85%, Disk > 95%
- Network > 20MB, Battery < 20%
- Requests/sec > 3000

**MEDIUM thresholds:**
- CPU > 75%, Memory > 75%, Disk > 90%
- Network > 10MB, Battery < 30%

### Q4.3: What penalties are applied to health score?
**A:**
| Severity | Penalty |
|----------|--------|
| CRITICAL | -20 |
| HIGH | -10 |
| MEDIUM | -5 |
| LOW | -2 |

### Q4.4: What colors represent each severity?
**A:**
| Severity | Color |
|----------|-------|
| CRITICAL | #FF0000 (Red) |
| HIGH | #FF6600 (Orange) |
| MEDIUM | #FFB300 (Yellow) |
| LOW | #00C853 (Green) |
| NONE | #4CAF50 (Green) |

---

## 5. API Endpoints

### Q5.1: What are the main endpoints?
**A:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest` | POST | Submit metric data for detection |
| `/logs` | GET | Get recent logs |
| `/anomalies` | GET | Get detected anomalies |
| `/health` | GET | Get system health score |
| `/system` | GET | Get raw system info |
| `/stats` | GET | Get detection statistics |
| `/detector/status` | GET | Get detector status |
| `/simulate/{mode}` | POST | Trigger simulation |
| `/ws` | WebSocket | Real-time updates |
| `/` | GET | API info |

### Q5.2: What is the `/ingest` payload format?
**A:**
```json
{
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
```

### Q5.3: What does `/ingest` return?
**A:**
```json
{
  "is_anomaly": true,
  "severity": "HIGH",
  "explanation": "High response time indicating latency issues",
  "score": -0.15,
  "health_score": 90
}
```

### Q5.4: What simulation modes are available?
**A:**
- `normal`: Baseline operation
- `ddos`: High request rates (1000-5000 RPS), high response time (500-5000ms)
- `memory_leak`: Gradually increasing memory, moderate response time
- `cpu_spike`: High CPU with variable response times

---

## 6. Health Score System

### Q6.1: How does health scoring work?
**A:**
- Starts at 100
- Decreases based on anomaly severity (see Q4.3)
- Recovers by +1 point every 60 seconds if no anomalies for 60 seconds
- Range: 0-100

### Q6.2: What do health labels mean?
**A:**
| Score | Label |
|-------|-------|
| 80-100 | HEALTHY |
| 60-79 | DEGRADED |
| 40-59 | WARNING |
| 0-39 | CRITICAL |

---

## 7. Frontend Features

### Q7.1: What does the dashboard show?
**A:**
- Real-time CPU, Memory, Disk usage
- Battery and Network stats
- Live metrics chart (last 60 seconds)
- Anomaly feed with explanations
- Simulation controls
- Health score display

### Q7.2: What analytics are available?
**A:**
- Total logs analyzed
- Total anomalies detected
- Detection accuracy
- Average response time
- Anomalies per hour chart
- Most common anomaly type

### Q7.3: How does simulation work?
**A:**
1. User clicks simulation button (e.g., "Simulate DDoS")
2. Frontend calls `/simulate/ddos` endpoint
3. Backend writes mode to `logs/current_mode.txt`
4. Data collector reads mode and generates simulated metrics
5. After 30 seconds (15 for CPU spike), mode auto-resets to "normal"

---

## 8. Alerting System

### Q8.1: What alerting is supported?
**A:**
- **Slack Webhooks**: Sends alerts to Slack channel
- **Sound Alerts**: Audio notification in dashboard for CRITICAL anomalies

### Q8.2: What triggers a Slack alert?
**A:** Any detected anomaly triggers a Slack alert if:
- Slack webhook URL is configured in `.env`
- `SLACK_WEBHOOK` environment variable is set

### Q8.3: What does a Slack alert contain?
**A:**
- Severity level and color
- Timestamp
- Key metrics (CPU, Memory, Response Time, RPS)
- Explanation
- Health score impact

---

## 9. AI Explanations

### Q9.1: How are anomaly explanations generated?
**A:** Two methods:
1. **AI Explanation**: Uses OpenRouter API (GPT-3.5) if API key configured
2. **Simple Explanation**: Rule-based fallback if API unavailable

### Q9.2: What is the simple explanation logic?
**A:**
- If RPS > 3000: "High request rate detected"
- If response time > 4000ms: "High response time indicating latency issues"
- If CPU > 85%: "CPU utilization critically high"
- If Memory > 85%: "Memory usage critically high"
- Otherwise: "Anomalous behavior detected"

---

## 10. Configuration

### Q10.1: What can be configured?
**A:** Via `config.py` or environment variables:
- Server host/port
- Detection thresholds
- Severity thresholds
- Health recovery settings
- CORS origins
- Rate limiting
- OpenRouter API key
- Slack webhook
- Logging level

### Q10.2: What environment variables are used?
**A:**
- `OPENROUTER_KEY`: API key for AI explanations
- `SLACK_WEBHOOK`: Slack webhook URL
- `BACKEND_URL`: Backend URL for data collector
- `COLLECTION_INTERVAL`: Metrics collection interval
- `LOG_LEVEL`: Logging level

---

## 11. WebSocket Real-time Updates

### Q11.1: How does WebSocket work?
**A:**
1. Frontend connects to `ws://localhost:8000/ws`
2. Backend broadcasts every detection result to all connected clients
3. Frontend updates dashboard in real-time without polling

### Q11.2: What is broadcasted?
**A:**
```json
{
  "timestamp": "...",
  "cpu_usage": 45.2,
  "memory_usage": 67.8,
  "response_time_ms": 150,
  "requests_per_sec": 44.6,
  "is_anomaly": true,
  "severity_level": "HIGH",
  "severity_color": "#FF6600",
  "explanation": "High response time...",
  "health_score": 90
}
```

---

## 12. State Management

### Q12.1: How is state managed?
**A:** Uses `AppState` class with:
- Thread-safe locking (`threading.RLock`)
- In-memory storage for logs and anomalies
- WebSocket client tracking
- Statistics counters

### Q12.2: What limits exist?
**A:**
- Maximum 10,000 logs stored
- Maximum 1,000 anomalies stored
- Older data is discarded (FIFO)

---

## 13. Setup & Installation

### Q13.1: How to run the backend?
```bash
cd backend
python main.py
# Or: uvicorn main:app --reload --port 8000
```

### Q13.2: How to run the frontend?
```bash
cd frontend
npm start
```

### Q13.3: How to run the data collector?
```bash
cd backend
python data_collector.py
```

### Q13.4: What are the prerequisites?
**A:**
- Python 3.8+ with pip
- Node.js 16+ with npm
- Git

### Q13.5: Required Python packages?
```
fastapi, uvicorn, scikit-learn, numpy, psutil,
requests, python-dotenv, pydantic
```

---

## 14. Technical Details

### Q14.1: What is the detection accuracy?
**A:** The system reports ~93.2% detection accuracy based on simulation testing.

### Q14.2: How does retraining work?
**A:**
- Model retrains every 200 logs
- Uses sliding buffer of last 200 logs
- Updates Isolation Forest with new normal patterns

### Q14.3: What happens during startup?
**A:**
1. FastAPI server starts on configured port
2. CORS middleware configured
3. Health recovery loop starts (every 60 seconds)
4. Detector waits for initial training (50 logs)
5. WebSocket endpoint ready for connections

### Q14.4: How is JSON serialization handled?
**A:** Custom `SafeJSONResponse` handles:
- numpy types (`.item()`, `.tolist()`)
- sets/frozensets (converted to lists)
- Other non-serializable objects (converted to strings)

---

## 15. Troubleshooting

### Q15.1: Backend won't start?
**A:** Check:
- All dependencies installed
- Port 8000 available
- No syntax errors in code

### Q15.2: No anomalies detected during simulation?
**A:** Check:
- Data collector is running
- Simulation mode is active (check `logs/current_mode.txt`)
- Detector has been trained (50+ logs collected)

### Q15.3: Slack alerts not working?
**A:** Verify:
- Webhook URL in `.env` file
- Slack app has Incoming Webhooks enabled
- Test webhook manually with curl

### Q15.4: Frontend can't connect?
**A:** Check:
- Backend running on port 8000
- CORS origins configured
- No network/firewall issues

---

## 16. Evaluation Questions (For Testing)

### Q16.1: If CPU usage is 96%, what severity would be assigned?
**A:** CRITICAL (exceeds 95% critical threshold)

### Q16.2: If the detector hasn't trained yet, can it detect anomalies?
**A:** Yes, using hard-threshold detection only

### Q16.3: What happens to health score after detecting 3 CRITICAL anomalies?
**A:** Health decreases by 60 points (3 × 20 penalty) = 40

### Q16.4: How long does it take for health to recover by 1 point?
**A:** 60 seconds without anomalies

### Q16.5: Can the system detect a DDoS attack? How?
**A:** Yes, via:
- Hard threshold: requests_per_sec > 2500 (2+ thresholds triggered)
- Isolation Forest: pattern shows extremely high RPS

### Q16.6: What is the difference between model anomaly and threshold anomaly?
**A:**
- Model anomaly: ML-based pattern detection
- Threshold anomaly: Rule-based hard limits
- Both can trigger detection (hybrid approach)

### Q16.7: How does the data collector know which mode to simulate?
**A:** It reads the mode from `logs/current_mode.txt` file

### Q16.8: What happens if OpenRouter API fails?
**A:** Falls back to simple rule-based explanation

### Q16.9: How many logs are kept in memory?
**A:** Maximum 10,000 (older logs discarded)

### Q16.10: What triggers auto-reset of simulation mode?
**A:** After 30 seconds (15 for CPU spike), mode automatically resets to "normal"