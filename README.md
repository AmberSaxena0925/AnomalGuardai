# AnomalyGuard

A real-time anomaly detection system for monitoring system metrics and detecting performance issues using machine learning.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Anomaly Detection](#anomaly-detection)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Overview

AnomalyGuard is a comprehensive monitoring solution that uses machine learning to detect anomalies in system performance metrics. It provides real-time monitoring of CPU usage, memory consumption, response times, and request rates, automatically identifying and alerting on potential issues.

The system consists of:
- **Backend API** (Python/FastAPI): Handles data ingestion, anomaly detection, and alerting
- **Frontend Dashboard** (React): Real-time visualization and control interface
- **Data Collector**: Simulated metric collection (can be replaced with real monitoring)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Collector │───▶│   Backend API   │───▶│ Frontend Dashboard│
│                 │    │                 │    │                 │
│ • CPU Usage     │    │ • FastAPI        │    │ • React App      │
│ • Memory Usage  │    │ • IsolationForest│    │ • Real-time Charts│
│ • Response Time │    │ • Health Scoring │    │ • Anomaly Logs   │
│ • Request Rate  │    │ • Slack Alerts   │    │ • Simulation Ctrl │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Components

- **Data Collector** (`backend/data_collector.py`): Collects system metrics and sends them to the backend
- **Core Engine** (`backend/core/`):
  - `detector.py`: Machine learning anomaly detection using Isolation Forest
  - `explainer.py`: AI-powered anomaly explanations via OpenRouter API
  - `severity.py`: Severity classification and scoring
  - `alerter.py`: Alert management and notifications
  - `state.py`: Global state management
- **API Server** (`backend/main.py`): FastAPI server with WebSocket support
- **Dashboard** (`frontend/`): React application with real-time updates

## ✨ Features

### Real-time Monitoring
- Continuous metric collection (CPU, memory, response time, requests/sec)
- Live dashboard with real-time charts
- WebSocket-based updates for instant notifications

### Anomaly Detection
- Machine learning-based detection using Isolation Forest algorithm
- Configurable sensitivity and contamination parameters
- Severity classification (CRITICAL, HIGH, MEDIUM, LOW)
- AI-powered explanations for detected anomalies

### Alerting & Notifications
- Slack webhook integration for instant alerts
- Sound alerts for critical anomalies in the dashboard
- Configurable alert thresholds

### Simulation & Testing
- Built-in anomaly simulation modes:
  - **DDoS**: High request rates with increased latency
  - **Memory Leak**: Gradually increasing memory usage
  - **CPU Spike**: High CPU utilization with variable response times
- Easy testing and demonstration capabilities

### Health Monitoring
- System health scoring (0-100)
- Automatic health recovery over time
- Visual health indicators with color coding

### Analytics
- Historical anomaly data
- Detection rate statistics
- Hourly anomaly distribution charts
- Severity level analysis

## 📋 Prerequisites

- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **Git** for cloning the repository

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd anomalyguard
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn scikit-learn numpy psutil requests python-dotenv pydantic
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# OpenRouter API key for AI explanations (optional)
OPENROUTER_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Slack webhook URL for alerts (optional)
SLACK_WEBHOOK=https://hooks.slack.com/services/TXXXXXXXXX/BXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXX
```

### Slack Webhook Setup

1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new app
3. Enable "Incoming Webhooks"
4. Add webhook to your desired channel
5. Copy the webhook URL to your `.env` file

## 🎮 Usage

### Starting the Application

1. **Start the Backend**:
   ```bash
   cd backend
   python main.py
   ```
   The API will be available at `http://localhost:8000`

2. **Start the Frontend**:
   ```bash
   cd frontend
   npm start
   ```
   The dashboard will be available at `http://localhost:3000`

3. **Start Data Collection**:
   ```bash
   cd backend
   python data_collector.py
   ```
   This will begin collecting real system metrics (CPU, memory, disk, network, battery) and sending them to the backend for monitoring and anomaly detection.

### Using the Dashboard

1. **Dashboard Tab**: View real-time metrics and recent anomalies
2. **Analytics Tab**: View historical data and statistics
3. **Simulation Buttons**: Trigger different anomaly types for testing
4. **Anomaly Logs**: Review detected anomalies with explanations

### Simulation Modes

- **Normal**: Baseline operation with typical metrics
- **DDoS**: Simulates distributed denial of service attack
- **Memory Leak**: Gradually increasing memory consumption
- **CPU Spike**: High CPU utilization with performance impact

## 📡 API Reference

### Endpoints

#### Data Ingestion
- `POST /ingest` - Submit metric data
  ```json
  {
    "timestamp": "2024-01-01T12:00:00",
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "response_time_ms": 150,
    "requests_per_sec": 120,
    "mode": "normal"
  }
  ```

#### Data Retrieval
- `GET /logs` - Get recent metric logs
- `GET /anomalies` - Get detected anomalies
- `GET /health` - Get system health score
- `GET /stats` - Get detection statistics

#### Simulation Control
- `POST /simulate/{mode}` - Trigger anomaly simulation
  - Modes: `normal`, `ddos`, `memory_leak`, `cpu_spike`

#### WebSocket
- `ws://localhost:8000/ws` - Real-time updates

## 🧠 Anomaly Detection

### Algorithm

AnomalyGuard uses the **Isolation Forest** algorithm from scikit-learn, which:

1. **Isolation**: Anomalies are easier to isolate in random forests
2. **Scoring**: Lower scores indicate higher anomaly likelihood
3. **Thresholding**: Configurable contamination parameter determines anomaly threshold

### Detection Process

1. **Data Collection**: Metrics are collected every 2 seconds
2. **Preprocessing**: Features are normalized and prepared
3. **Detection**: Isolation Forest predicts anomaly scores
4. **Classification**: Anomalies are classified by severity
5. **Explanation**: AI generates human-readable explanations
6. **Alerting**: Notifications are sent via configured channels

### Severity Levels

- **CRITICAL**: Immediate attention required (score > 20 penalty)
- **HIGH**: High priority issue (score > 10 penalty)
- **MEDIUM**: Moderate issue (score > 5 penalty)
- **LOW**: Minor issue (score > 2 penalty)

## 🔧 Troubleshooting

### Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'sklearn'`

**Solution**: Install missing dependencies
```bash
cd backend
pip install scikit-learn numpy psutil requests python-dotenv pydantic
```

### Frontend Won't Load

**Error**: Connection refused to backend

**Solution**: Ensure backend is running on port 8000
```bash
cd backend
python main.py
```

### No Anomalies Detected

**Issue**: System appears normal even during simulation

**Solution**:
1. Check that data collector is running
2. Verify simulation mode is active
3. Check backend logs for errors
4. Adjust detection sensitivity if needed

### Slack Alerts Not Working

**Issue**: No notifications in Slack

**Solution**:
1. Verify webhook URL in `.env` file
2. Check Slack app permissions
3. Test webhook manually with curl:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"Test"}' \
        YOUR_WEBHOOK_URL
   ```

### Performance Issues

**Issue**: High CPU usage or slow response

**Solution**:
1. Reduce data collection frequency in `data_collector.py`
2. Adjust WebSocket polling interval in frontend
3. Optimize Isolation Forest parameters

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint for React code
- Add documentation for new features
- Test thoroughly before submitting

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with FastAPI, React, and scikit-learn
- Uses OpenRouter API for AI explanations
- Inspired by modern monitoring and observability practices