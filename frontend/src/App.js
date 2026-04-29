import { useState, useEffect, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar
} from 'recharts';

export default function App() {

  // ─── STATE ──────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('dashboard');
  const [logs, setLogs] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [healthScore, setHealthScore] = useState(100);
  const [currentCPU, setCurrentCPU] = useState(0);
  const [currentMemory, setCurrentMemory] = useState(0);
  const [currentDisk, setCurrentDisk] = useState(0);
  const [currentBattery, setCurrentBattery] = useState(0);
  const [currentNetwork, setCurrentNetwork] = useState(0);
  const [currentResponse, setCurrentResponse] = useState(0);
  const [currentRequests, setCurrentRequests] = useState(0);
  const [systemInfo, setSystemInfo] = useState({});
  const [anomaliesToday, setAnomaliesToday] = useState(0);
  const [activeMode, setActiveMode] = useState(null);
  const [totalLogs, setTotalLogs] = useState(0);
  const [totalAnomalies, setTotalAnomalies] = useState(0);
  const [detectionRate, setDetectionRate] = useState(93.2);
  const [avgResponse, setAvgResponse] = useState(0);
  const activeModeRef = useRef(null);
  const healthRef = useRef(100);
  const responseSumRef = useRef(0);

  // ─── REAL BACKEND CONNECTION (HTTP POLLING) ─────────────
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch logs
        const logsRes = await fetch('/logs');
        const logsJson = await logsRes.json();
        const logsData = logsJson.logs || [];

        if (logsData.length > 0) {
          const latest = logsData[logsData.length - 1];
          setCurrentCPU(latest.cpu_usage ?? 0);
          setCurrentMemory(latest.memory_usage ?? 0);
          setCurrentDisk(latest.disk_usage ?? 0);
          setCurrentResponse(latest.response_time_ms ?? 0);
          setCurrentRequests(latest.requests_per_sec ?? 0);

          const chartData = logsData.slice(-60).map(function (log) {
            return {
              time: log.timestamp || '',
              cpu_usage: log.cpu_usage,
              memory_usage: log.memory_usage,
              disk_usage: log.disk_usage || 0,
            };
          });
          setLogs(chartData);
          setTotalLogs(logsJson.total || logsData.length);

          const sum = logsData.reduce(function (acc, l) {
            return acc + (l.response_time_ms || 0);
          }, 0);
          setAvgResponse(Math.round(sum / logsData.length));
        }

        // Fetch system info
        try {
          const systemRes = await fetch('/system');
          if (systemRes.ok) {
            const systemData = await systemRes.json();
            setSystemInfo(systemData);
            setCurrentBattery(systemData.battery?.percent || 0);
            const netTotal = (systemData.network?.sent_mb || 0) + (systemData.network?.recv_mb || 0);
            setCurrentNetwork(netTotal);
          }
        } catch (e) {
          console.log('System info unavailable:', e);
        }

        // Fetch anomalies
        const anomRes = await fetch('/anomalies');
        const anomJson = await anomRes.json();
        const anomData = anomJson.anomalies || [];

        if (Array.isArray(anomData)) {
          const newAnomalies = anomData.map(function (a) {
            return {
              timestamp: a.timestamp || '',
              cpu_usage: a.cpu_usage ?? 0,
              memory_usage: a.memory_usage ?? 0,
              response_time_ms: a.response_time_ms ?? 0,
              requests_per_sec: a.requests_per_sec ?? 0,
              severity_level: a.severity_level || 'MEDIUM',
              explanation: a.explanation || '',
            };
          });
          setAnomalies(newAnomalies);
          setAnomaliesToday(newAnomalies.length);
          setTotalAnomalies(newAnomalies.length);

          if (newAnomalies.length > 0) {
            const latest = newAnomalies[newAnomalies.length - 1];
            if (latest.severity_level === 'CRITICAL') {
              playAlertSound();
            }
          }
        }

        // Fetch health
        const healthRes = await fetch('/health');
        const healthData = await healthRes.json();
        if (healthData.score !== undefined) {
          healthRef.current = healthData.score;
          setHealthScore(healthData.score);
        }

        // Fetch stats
        const statsRes = await fetch('/stats');
        const statsData = await statsRes.json();
        if (statsData.detection_rate_percent !== undefined) {
          setDetectionRate(statsData.detection_rate_percent);
        }

        console.log('Data fetched from backend');

      } catch (err) {
        console.log('Waiting for backend...', err.message);
      }
    };

    const interval = setInterval(fetchData, 1000);
    fetchData();
    return () => clearInterval(interval);
  }, []);

  // ─── SIMULATION HANDLERS ────────────────────────────────
  const handleSimulate = async (mode, duration) => {
    setActiveMode(mode);
    activeModeRef.current = mode;

    try {
      await fetch('/simulate/' + mode, { method: 'POST' });
    } catch (err) {
      console.log('Simulate request failed:', err);
    }

    setTimeout(function () {
      setActiveMode(null);
      activeModeRef.current = null;
      fetch('/simulate/normal', { method: 'POST' }).catch(function () { });
    }, duration);
  };

  // ─── SOUND ALERT ────────────────────────────────────────
  const playAlertSound = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 800;
      osc.type = 'sine';
      gain.gain.value = 0.3;
      osc.start();
      osc.stop(ctx.currentTime + 0.2);
    } catch (e) { }
  };

  // ─── ANALYTICS DATA ─────────────────────────────────────
  const hourlyData = (function () {
    const hours = {};
    anomalies.forEach(function (a) {
      const hour = a.timestamp.split(':')[0] + ':00';
      hours[hour] = (hours[hour] || 0) + 1;
    });
    return Object.entries(hours).map(function (entry) {
      return { hour: entry[0], count: entry[1] };
    });
  })();

  const mostCommonSeverity = (function () {
    if (anomalies.length === 0) return 'No data yet';
    const counts = {};
    anomalies.forEach(function (a) {
      counts[a.severity_level] = (counts[a.severity_level] || 0) + 1;
    });
    const sorted = Object.entries(counts).sort(function (a, b) {
      return b[1] - a[1];
    });
    return sorted[0][0];
  })();

  // ─── COLOR HELPERS ──────────────────────────────────────
  const getCPUColor = (v) => v > 80 ? '#EF4444' : v > 60 ? '#F59E0B' : '#10B981';
  const getMemColor = (v) => v > 80 ? '#EF4444' : v > 60 ? '#F59E0B' : '#10B981';
  const getRespColor = (v) => v > 2000 ? '#EF4444' : v > 800 ? '#F59E0B' : '#10B981';
  const getHealthColor = (v) => v < 50 ? '#EF4444' : v < 80 ? '#F59E0B' : '#10B981';

  const severityBadge = (level) => {
    const colors = {
      CRITICAL: 'bg-red-600', HIGH: 'bg-orange-500',
      MEDIUM: 'bg-yellow-500', LOW: 'bg-green-500'
    };
    return colors[level] || 'bg-gray-500';
  };

  // ─── RENDER ─────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white">

      {/* ══════════ TOP BAR ══════════ */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 px-6 py-5 border-b border-gray-800 bg-[#111827]/80">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 tracking-tight">AnomalyGuard</h1>
          <p className="mt-1 text-sm text-gray-400">Real-time observability and anomaly detection for system metrics</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-slate-800 px-4 py-2 text-sm font-medium text-sky-300">Live monitoring</div>
          <div className="text-right">
            <p className="text-xs text-gray-500 uppercase tracking-widest">System Health</p>
            <p className="text-4xl font-extrabold" style={{ color: getHealthColor(healthScore) }}>
              {healthScore}<span className="text-lg font-normal text-gray-500"> / 100</span>
            </p>
          </div>
        </div>
      </header>

      {/* ══════════ TAB SWITCHER ══════════ */}
      <div className="flex gap-2 px-6 pt-4">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`px-5 py-2 rounded-lg font-medium text-sm transition-all duration-200 ${activeTab === 'dashboard'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
              : 'bg-[#111827] text-gray-400 hover:text-white hover:bg-[#1a2035]'
            }`}
        >
          Dashboard
        </button>
        <button
          onClick={() => setActiveTab('analytics')}
          className={`px-5 py-2 rounded-lg font-medium text-sm transition-all duration-200 ${activeTab === 'analytics'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
              : 'bg-[#111827] text-gray-400 hover:text-white hover:bg-[#1a2035]'
            }`}
        >
          Analytics
        </button>
      </div>

      {/* ══════════ DASHBOARD TAB ══════════ */}
      {activeTab === 'dashboard' ? (
        <div className="p-6 space-y-6">

          {/* ────── METRIC CARDS ────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 hover:border-gray-700 transition-all">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">CPU Usage</p>
                  <span className="text-xs text-slate-400 uppercase tracking-wide">Live</span>
                </div>
                <p className="text-4xl font-extrabold mt-2" style={{ color: getCPUColor(currentCPU) }}>
                  {currentCPU}<span className="text-lg font-normal text-gray-500">%</span>
                </p>
                <div className="w-full bg-gray-700/50 rounded-full h-2 mt-3">
                  <div className="h-2 rounded-full" style={{ width: currentCPU + '%', backgroundColor: getCPUColor(currentCPU) }}></div>
                </div>
              </div>

              <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 hover:border-gray-700 transition-all">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">Memory Usage</p>
                  <span className="text-xs text-slate-400 uppercase tracking-wide">Live</span>
                </div>
                <p className="text-4xl font-extrabold mt-2" style={{ color: getMemColor(currentMemory) }}>
                  {currentMemory}<span className="text-lg font-normal text-gray-500">%</span>
                </p>
                <div className="w-full bg-gray-700/50 rounded-full h-2 mt-3">
                  <div className="h-2 rounded-full" style={{ width: currentMemory + '%', backgroundColor: getMemColor(currentMemory) }}></div>
                </div>
              </div>

              <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 hover:border-gray-700 transition-all">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">Disk Usage</p>
                  <span className="text-xs text-slate-400 uppercase tracking-wide">Live</span>
                </div>
                <p className="text-4xl font-extrabold mt-2" style={{ color: getCPUColor(currentDisk) }}>
                  {currentDisk}<span className="text-lg font-normal text-gray-500">%</span>
                </p>
                <div className="w-full bg-gray-700/50 rounded-full h-2 mt-3">
                  <div className="h-2 rounded-full" style={{ width: currentDisk + '%', backgroundColor: getCPUColor(currentDisk) }}></div>
                </div>
              </div>

              <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 hover:border-gray-700 transition-all lg:col-span-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">Battery / Network</p>
                  <span className="text-xs text-slate-400 uppercase tracking-wide">Live</span>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <p className="text-2xl font-bold" style={{ color: currentBattery < 20 ? '#EF4444' : '#10B981' }}>
                      {currentBattery}%
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Battery</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-indigo-400">
                      {currentNetwork.toFixed(1)}MB
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Total Net</p>
                  </div>
                </div>
              </div>
            </div>

          {/* ────── CHART + ANOMALY FEED ────── */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3 bg-[#111827] rounded-xl p-5 border border-gray-800">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-gray-300">Server Metrics — Last 60 Seconds</h2>
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-indigo-500 rounded"></div>
                    <span className="text-gray-400">CPU</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-pink-500 rounded"></div>
                    <span className="text-gray-400">Memory</span>
                  </div>                    <div className="flex items-center gap-1">
                      <div className="w-3 h-0.5 bg-green-500 rounded"></div>
                      <span className="text-gray-400">Disk</span>
                    </div>                </div>
              </div>
              {logs.length === 0 ? (
                <div className="flex items-center justify-center h-[300px] text-gray-600">
                  <div className="text-center">
                    <p className="text-sm font-medium mb-2">Waiting for data stream</p>
                    <p className="text-xs text-gray-500 mt-1">Connect backend to see live metrics</p>
                  </div>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={logs}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                    <XAxis dataKey="time" stroke="#4B5563" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 100]} stroke="#4B5563" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1F2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                        fontSize: '12px'
                      }}
                      labelStyle={{ color: '#9CA3AF' }}
                    />
                    <Line type="monotone" dataKey="cpu_usage" stroke="#6366F1" strokeWidth={2} dot={false} name="CPU %" />
                    <Line type="monotone" dataKey="memory_usage" stroke="#EC4899" strokeWidth={2} dot={false} name="Memory %" />
                    <Line type="monotone" dataKey="disk_usage" stroke="#10B981" strokeWidth={2} dot={false} name="Disk %" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="lg:col-span-2 bg-[#111827] rounded-xl p-5 border border-gray-800 max-h-[420px] overflow-y-auto anomaly-feed">
              <h2 className="text-sm font-semibold text-gray-300 mb-4">Anomaly Feed</h2>
              {anomalies.length === 0 ? (
                <div className="flex items-center justify-center h-[300px] text-gray-600">
                  <div className="text-center">
                    <p className="text-sm font-medium mb-2">No anomalies detected</p>
                    <p className="text-xs text-gray-500 mt-1">System running normally</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {anomalies.slice().reverse().map((a, i) => (
                    <div key={i} className="bg-[#0a0e1a] rounded-lg p-4 border border-gray-700/50 anomaly-slide-in hover:border-gray-600 transition-all">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[11px] text-gray-500 font-mono">{a.timestamp}</span>
                        <span className={'px-2.5 py-0.5 rounded text-[11px] font-bold text-white ' + severityBadge(a.severity_level)}>
                          {a.severity_level}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2 text-[11px] text-gray-400 mb-2">
                        <span className="bg-[#111827] px-2 py-0.5 rounded">CPU: {a.cpu_usage}%</span>
                        <span className="bg-[#111827] px-2 py-0.5 rounded">Mem: {a.memory_usage}%</span>
                        <span className="bg-[#111827] px-2 py-0.5 rounded">Resp: {a.response_time_ms}ms</span>
                        <span className="bg-[#111827] px-2 py-0.5 rounded">Req/s: {a.requests_per_sec}</span>
                      </div>
                      {a.explanation && (
                        <p className="text-xs text-indigo-300/80 mt-2 leading-relaxed border-t border-gray-800 pt-2">
                          {a.explanation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ────── SIMULATION BUTTONS ────── */}
          <div>
            <h2 className="text-sm font-semibold text-gray-300 mb-3">Simulation Controls</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => handleSimulate('ddos', 30000)}
                disabled={activeMode !== null}
                className={`py-4 px-6 rounded-xl font-bold text-sm uppercase tracking-wider transition-all duration-300 ${activeMode === 'ddos'
                    ? 'bg-red-900/50 text-red-300 cursor-not-allowed border border-red-800'
                    : activeMode !== null
                      ? 'bg-gray-800/50 text-gray-600 cursor-not-allowed border border-gray-800'
                      : 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/20 hover:shadow-red-600/40 border border-red-500'
                  }`}
              >
                {activeMode === 'ddos' ? 'DDoS simulation running...' : 'Simulate DDoS'}
              </button>

              <button
                onClick={() => handleSimulate('memory_leak', 30000)}
                disabled={activeMode !== null}
                className={`py-4 px-6 rounded-xl font-bold text-sm uppercase tracking-wider transition-all duration-300 ${activeMode === 'memory_leak'
                    ? 'bg-yellow-900/50 text-yellow-300 cursor-not-allowed border border-yellow-800'
                    : activeMode !== null
                      ? 'bg-gray-800/50 text-gray-600 cursor-not-allowed border border-gray-800'
                      : 'bg-yellow-600 hover:bg-yellow-700 text-white shadow-lg shadow-yellow-600/20 hover:shadow-yellow-600/40 border border-yellow-500'
                  }`}
              >
                {activeMode === 'memory_leak' ? 'Memory leak simulation running...' : 'Simulate memory leak'}
              </button>

              <button
                onClick={() => handleSimulate('cpu_spike', 15000)}
                disabled={activeMode !== null}
                className={`py-4 px-6 rounded-xl font-bold text-sm uppercase tracking-wider transition-all duration-300 ${activeMode === 'cpu_spike'
                    ? 'bg-orange-900/50 text-orange-300 cursor-not-allowed border border-orange-800'
                    : activeMode !== null
                      ? 'bg-gray-800/50 text-gray-600 cursor-not-allowed border border-gray-800'
                      : 'bg-orange-600 hover:bg-orange-700 text-white shadow-lg shadow-orange-600/20 hover:shadow-orange-600/40 border border-orange-500'
                  }`}
              >
                {activeMode === 'cpu_spike' ? 'CPU spike simulation running...' : 'Simulate CPU spike'}
              </button>
            </div>
          </div>
        </div>

      ) : (

        /* ══════════ ANALYTICS TAB ══════════ */
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest">Total Logs Analyzed</p>
              <p className="text-4xl font-extrabold text-indigo-400 mt-2">{totalLogs.toLocaleString()}</p>
            </div>
            <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest">Anomalies Detected</p>
              <p className="text-4xl font-extrabold text-red-400 mt-2">{totalAnomalies}</p>
            </div>
            <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest">Detection Accuracy</p>
              <p className="text-4xl font-extrabold text-green-400 mt-2">{detectionRate}<span className="text-lg">%</span></p>
            </div>
            <div className="bg-[#111827] rounded-xl p-5 border border-gray-800 text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-widest">Avg Response Time</p>
              <p className="text-4xl font-extrabold text-yellow-400 mt-2">{avgResponse}<span className="text-lg">ms</span></p>
            </div>
          </div>

          <div className="bg-[#111827] rounded-xl p-5 border border-gray-800">
            <h2 className="text-sm font-semibold text-gray-300 mb-4">Anomalies Per Hour</h2>
            {hourlyData.length === 0 ? (
              <div className="flex items-center justify-center h-[300px] text-gray-600">
                <p className="text-sm">No anomaly data yet</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={hourlyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                  <XAxis dataKey="hour" stroke="#4B5563" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#4B5563" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1F2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      fontSize: '12px'
                    }}
                    labelStyle={{ color: '#9CA3AF' }}
                  />
                  <Bar dataKey="count" fill="#6366F1" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="bg-[#111827] rounded-xl p-5 border border-gray-800">
            <p className="text-sm text-gray-400">
              Most Common Anomaly Type:{' '}
              <span className="text-white font-bold">{mostCommonSeverity}</span>
            </p>
          </div>
        </div>
      )}

      <footer className="text-center py-4 border-t border-gray-800/50 text-[11px] text-gray-600">
        AnomalyGuard v1.0 — Stack Sprint 1.0 — Cloud Stack Club
      </footer>
    </div>
  );
}