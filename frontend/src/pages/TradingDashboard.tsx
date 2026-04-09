import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { tradingSystemService } from '../services/api';
import type { TradingSystemStatus, ActiveTrade, TradeSignal, TradePerformance } from '../types';

interface EquityPoint {
  time: string;
  equity: number;
}

export function TradingDashboard() {
  const [status, setStatus] = useState<TradingSystemStatus | null>(null);
  const [trades, setTrades] = useState<ActiveTrade[]>([]);
  const [signals, setSignals] = useState<TradeSignal[]>([]);
  const [performance, setPerformance] = useState<TradePerformance | null>(null);
  const [equityCurve] = useState<EquityPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [statusData, tradesData, signalsData, perfData] = await Promise.all([
        tradingSystemService.getStatus(),
        tradingSystemService.getTrades(),
        tradingSystemService.getSignals(),
        tradingSystemService.getPerformance()
      ]);
      setStatus(statusData);
      setTrades(tradesData);
      setSignals(signalsData);
      setPerformance(perfData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      await tradingSystemService.start();
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start');
    }
  };

  const handleStop = async () => {
    try {
      await tradingSystemService.stop();
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trading Dashboard</h1>
        <div className="flex items-center gap-2">
          <span className={`w-3 h-3 rounded-full ${status?.is_running ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span className="text-sm">{status?.is_running ? 'Running' : 'Stopped'}</span>
          {status?.is_running ? (
            <button onClick={handleStop} className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition">
              Stop
            </button>
          ) : (
            <button onClick={handleStart} className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition">
              Start
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500 rounded-lg text-red-500">
          {error}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-gray-800 rounded-lg">
          <p className="text-gray-400 text-sm">Capital</p>
          <p className="text-2xl font-bold">${status?.capital?.toLocaleString() || '0'}</p>
        </div>
        <div className="p-4 bg-gray-800 rounded-lg">
          <p className="text-gray-400 text-sm">Total Trades</p>
          <p className="text-2xl font-bold">{performance?.total_trades || 0}</p>
        </div>
        <div className="p-4 bg-gray-800 rounded-lg">
          <p className="text-gray-400 text-sm">Win Rate</p>
          <p className="text-2xl font-bold">{performance?.win_rate || 0}%</p>
        </div>
        <div className="p-4 bg-gray-800 rounded-lg">
          <p className="text-gray-400 text-sm">Profit Factor</p>
          <p className="text-2xl font-bold">{performance?.profit_factor || '0.00'}</p>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signals Panel */}
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Recent Signals</h2>
          {signals.length === 0 ? (
            <p className="text-gray-400">No signals</p>
          ) : (
            <div className="space-y-2">
              {signals.slice(0, 5).map((signal, i) => (
                <div key={i} className={`p-3 rounded-lg ${signal.type === 'BUY' ? 'bg-green-500/10 border-l-4 border-green-500' : 'bg-red-500/10 border-l-4 border-red-500'}`}>
                  <div className="flex justify-between items-center">
                    <span className="font-bold">{signal.type}</span>
                    <span className={`text-xs px-2 py-1 rounded ${signal.confidence === 'high' ? 'bg-green-500' : signal.confidence === 'medium' ? 'bg-yellow-500' : 'bg-gray-500'}`}>
                      {signal.confidence}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 mt-1">{signal.reason}</p>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-sm">
                    <div>Entry: {signal.entry}</div>
                    <div>SL: {signal.stop_loss}</div>
                    <div>TP: {signal.take_profit[1]}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active Trades */}
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Active Trades</h2>
          {trades.length === 0 ? (
            <p className="text-gray-400">No active trades</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700">
                    <th className="text-left p-2">Symbol</th>
                    <th className="text-left p-2">Entry</th>
                    <th className="text-left p-2">SL</th>
                    <th className="text-left p-2">TP</th>
                    <th className="text-left p-2">Status</th>
                    <th className="text-left p-2">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id} className="border-b border-gray-700">
                      <td className="p-2">{trade.symbol}</td>
                      <td className="p-2">{trade.entry_price}</td>
                      <td className="p-2">{trade.current_stop_loss}</td>
                      <td className="p-2">{trade.take_profit_2}</td>
                      <td className="p-2">
                        <span className={`px-2 py-1 rounded text-xs ${
                          trade.status === 'OPEN' ? 'bg-green-500' : 
                          trade.status === 'PARTIAL' ? 'bg-yellow-500' : 'bg-gray-500'
                        }`}>
                          {trade.status}
                        </span>
                      </td>
                      <td className="p-2">{trade.unrealized_pnl?.toFixed(2) || '0.00'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Performance */}
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">Performance</h2>
          <div className="space-y-4">
            <div>
              <p className="text-gray-400 text-sm">Max Drawdown</p>
              <p className="text-xl font-bold text-red-500">{performance?.max_drawdown || 0}%</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Total P&L</p>
              <p className={`text-xl font-bold ${(performance?.total_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${performance?.total_pnl?.toFixed(2) || '0.00'}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-gray-400 text-sm">Winners</p>
                <p className="text-lg font-bold text-green-500">{performance?.winning_trades || 0}</p>
              </div>
              <div>
                <p className="text-gray-400 text-sm">Losers</p>
                <p className="text-lg font-bold text-red-500">{performance?.losing_trades || 0}</p>
              </div>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Avg Win</p>
              <p className="text-lg font-bold text-green-500">${performance?.avg_win?.toFixed(2) || '0.00'}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Avg Loss</p>
              <p className="text-lg font-bold text-red-500">${performance?.avg_loss?.toFixed(2) || '0.00'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Equity Curve */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-4">Equity Curve</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={equityCurve}>
              <XAxis dataKey="time" stroke="#6b7280" fontSize={12} />
              <YAxis stroke="#6b7280" fontSize={12} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '8px' }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Line type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default TradingDashboard;