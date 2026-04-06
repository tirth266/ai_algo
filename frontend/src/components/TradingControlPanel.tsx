import React, { useState, useEffect } from 'react';
import apiClient from '../services/api';
import { Play, Square, RefreshCw, FileText, TrendingUp, DollarSign, Activity, Clock } from 'lucide-react';

interface TradingStatus {
  trading_active: boolean;
  state: string;
  active_strategy: string;
  last_run_time: string | null;
  total_trades_today: number;
  daily_pnl: number;
  signals_generated: number;
  orders_placed: number;
  uptime: string | null;
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  component?: string;
}

const TradingControlPanel: React.FC = () => {
  const [status, setStatus] = useState<TradingStatus>({
    trading_active: false,
    state: 'stopped',
    active_strategy: 'PowerStrategy',
    last_run_time: null,
    total_trades_today: 0,
    daily_pnl: 0.0,
    signals_generated: 0,
    orders_placed: 0,
    uptime: null
  });
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // Fetch status on mount and every 3 seconds
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await apiClient.get('/trading/status');
      setStatus(response.data);
    } catch (err: any) {
      console.error('Status fetch error:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const response = await apiClient.get('/trading/logs?limit=50');
      setLogs(response.data);
      setShowLogs(true);
    } catch (err: any) {
      setError('Failed to load logs');
    }
  };

  const handleStartTrading = async () => {
    setLoading(true);
    setError('');
    setMessage('Starting Power Strategy...');
    
    try {
      const response = await apiClient.post('/trading/start', {
        strategy: 'PowerStrategy'
      });
      
      if (response.data.success) {
        setMessage('✓ Power Strategy started! Running automated trading.');
        fetchStatus();
      } else {
        setError(response.data.message || 'Failed to start trading');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to start trading');
    } finally {
      setLoading(false);
      setTimeout(() => setMessage(''), 5000);
    }
  };

  const handleStopTrading = async () => {
    setLoading(true);
    setError('');
    setMessage('Stopping trading...');
    
    try {
      const response = await apiClient.post('/trading/stop');
      
      if (response.data.success) {
        setMessage('✓ Trading stopped successfully');
        fetchStatus();
      } else {
        setError(response.data.message || 'Failed to stop trading');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to stop trading');
    } finally {
      setLoading(false);
      setTimeout(() => setMessage(''), 5000);
    }
  };

  const handleRunOnce = async () => {
    setLoading(true);
    setError('');
    setMessage('Running strategy evaluation...');
    
    try {
      const response = await apiClient.post('/trading/run');
      
      if (response.data.success) {
        const signalCount = response.data.signals?.length || 0;
        setMessage(`✓ Strategy evaluated ${signalCount} symbols`);
        fetchStatus();
      } else {
        setError(response.data.message || 'Strategy run failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Strategy run failed');
    } finally {
      setLoading(false);
      setTimeout(() => setMessage(''), 5000);
    }
  };

  const handleResetStats = async () => {
    if (!confirm('Reset all trading statistics?')) return;
    
    try {
      await apiClient.post('/trading/reset');
      setMessage('✓ Statistics reset');
      fetchStatus();
      setTimeout(() => setMessage(''), 3000);
    } catch (err: any) {
      setError('Failed to reset stats');
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(value);
  };

  const formatTime = (isoString: string | null) => {
    if (!isoString) return 'Never';
    return new Date(isoString).toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="bg-gray-800 rounded-lg shadow-lg p-6 border border-gray-700">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-white flex items-center">
          <Activity className="w-6 h-6 mr-2 text-blue-400" />
          Trading Control Panel
        </h2>
        <div className="text-sm text-gray-400">
          Strategy: <span className="text-blue-400 font-semibold">{status.active_strategy}</span>
        </div>
      </div>
      
      {/* Main Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {/* Trading State */}
        <div className={`p-4 rounded-lg ${status.trading_active ? 'bg-green-900/50 border-green-700' : 'bg-red-900/50 border-red-700'} border`}>
          <div className="text-gray-400 text-xs mb-2 uppercase tracking-wide">Status</div>
          <div className="text-white text-xl font-bold flex items-center">
            {status.trading_active ? (
              <>
                <span className="w-3 h-3 bg-green-400 rounded-full mr-2 animate-pulse"></span>
                Running
              </>
            ) : (
              <>
                <span className="w-3 h-3 bg-red-400 rounded-full mr-2"></span>
                Stopped
              </>
            )}
          </div>
          {status.uptime && (
            <div className="text-gray-300 text-xs mt-2 flex items-center">
              <Clock className="w-3 h-3 mr-1" />
              {status.uptime}
            </div>
          )}
        </div>

        {/* Daily PnL */}
        <div className={`p-4 rounded-lg ${status.daily_pnl >= 0 ? 'bg-green-900/50 border-green-700' : 'bg-red-900/50 border-red-700'} border`}>
          <div className="text-gray-400 text-xs mb-2 uppercase tracking-wide flex items-center">
            <DollarSign className="w-3 h-3 mr-1" />
            Daily P&L
          </div>
          <div className={`text-xl font-bold ${status.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(status.daily_pnl)}
          </div>
          <div className="text-gray-300 text-xs mt-2">Today</div>
        </div>

        {/* Total Trades */}
        <div className="p-4 rounded-lg bg-blue-900/50 border-blue-700 border">
          <div className="text-gray-400 text-xs mb-2 uppercase tracking-wide flex items-center">
            <TrendingUp className="w-3 h-3 mr-1" />
            Total Trades
          </div>
          <div className="text-white text-xl font-bold">{status.total_trades_today}</div>
          <div className="text-gray-300 text-xs mt-2">Today</div>
        </div>

        {/* Last Run */}
        <div className="p-4 rounded-lg bg-purple-900/50 border-purple-700 border">
          <div className="text-gray-400 text-xs mb-2 uppercase tracking-wide">Last Run</div>
          <div className="text-white text-lg font-bold">{formatTime(status.last_run_time)}</div>
          <div className="text-gray-300 text-xs mt-2">Strategy Update</div>
        </div>
      </div>

      {/* Statistics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-gray-700/50 p-3 rounded-lg">
          <div className="text-gray-400 text-xs mb-1">Signals Generated</div>
          <div className="text-white text-lg font-bold">{status.signals_generated}</div>
        </div>
        <div className="bg-gray-700/50 p-3 rounded-lg">
          <div className="text-gray-400 text-xs mb-1">Orders Placed</div>
          <div className="text-white text-lg font-bold">{status.orders_placed}</div>
        </div>
        <div className="bg-gray-700/50 p-3 rounded-lg">
          <div className="text-gray-400 text-xs mb-1">State</div>
          <div className="text-white text-sm font-bold uppercase">{status.state}</div>
        </div>
        <div className="bg-gray-700/50 p-3 rounded-lg">
          <div className="text-gray-400 text-xs mb-1">Strategy</div>
          <div className="text-white text-xs font-bold truncate">{status.active_strategy}</div>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
        {!status.trading_active ? (
          <button
            onClick={handleStartTrading}
            disabled={loading}
            className="flex items-center justify-center bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="w-4 h-4 mr-2" />
            {loading ? 'Starting...' : 'Start Trading'}
          </button>
        ) : (
          <button
            onClick={handleStopTrading}
            disabled={loading}
            className="flex items-center justify-center bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Square className="w-4 h-4 mr-2" />
            {loading ? 'Stopping...' : 'Stop Trading'}
          </button>
        )}
        
        <button
          onClick={handleRunOnce}
          disabled={loading || !status.trading_active}
          className="flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Run Strategy
        </button>
        
        <button
          onClick={fetchLogs}
          className="flex items-center justify-center bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 px-4 rounded-lg transition duration-200"
        >
          <FileText className="w-4 h-4 mr-2" />
          View Logs
        </button>
        
        <button
          onClick={handleResetStats}
          className="flex items-center justify-center bg-gray-600 hover:bg-gray-700 text-white font-bold py-3 px-4 rounded-lg transition duration-200"
        >
          Reset Stats
        </button>
      </div>

      {/* Messages */}
      {message && (
        <div className="bg-blue-900/50 border border-blue-700 text-blue-100 px-4 py-3 rounded-lg mb-4">
          {message}
        </div>
      )}
      
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-4">
          {error}
        </div>
      )}

      {/* Logs Modal */}
      {showLogs && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            <div className="p-4 border-b border-gray-700 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white">Trading Logs</h3>
              <button
                onClick={() => setShowLogs(false)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {logs.length === 0 ? (
                <div className="text-gray-400 text-center py-8">No logs available</div>
              ) : (
                <div className="space-y-2">
                  {logs.map((log, index) => (
                    <div key={index} className="bg-gray-700/50 p-3 rounded text-sm">
                      <div className="flex justify-between items-start mb-1">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${
                          log.level === 'ERROR' ? 'bg-red-900 text-red-200' :
                          log.level === 'WARNING' ? 'bg-yellow-900 text-yellow-200' :
                          'bg-blue-900 text-blue-200'
                        }`}>
                          {log.level}
                        </span>
                        <span className="text-gray-400 text-xs">
                          {new Date(log.timestamp).toLocaleString('en-IN')}
                        </span>
                      </div>
                      <div className="text-gray-200 mt-1">{log.message}</div>
                      {log.component && (
                        <div className="text-gray-500 text-xs mt-1">[{log.component}]</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Info Footer */}
      <div className="text-gray-400 text-xs mt-4 pt-4 border-t border-gray-700">
        <p className="mb-1">• <strong>Power Strategy</strong> combines Supertrend, Liquidity, Trendlines, VWAP & Bollinger Bands</p>
        <p className="mb-1">• Click "Start Trading" to begin automated execution (runs every 60 seconds)</p>
        <p className="mb-1">• Use "Run Strategy" for manual evaluation without placing trades</p>
        <p>• All trading activity is logged and can be viewed in real-time</p>
      </div>
    </div>
  );
};

export default TradingControlPanel;
