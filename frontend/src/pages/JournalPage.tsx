import React, { useEffect, useState } from 'react';
import { journalService } from '../services/api';
import { TrendingUp, TrendingDown, Activity, PieChart, BarChart3, Calendar } from 'lucide-react';

export const JournalPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'trades' | 'signals' | 'strategies'>('overview');
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const data = await journalService.getAnalytics();
      setAnalytics(data.analytics);
      setError(null);
    } catch (err) {
      setError('Failed to load analytics');
      console.error('Analytics error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading analytics...</div>
      </div>
    );
  }

  const performance = analytics?.performance || {};
  const equityCurve = analytics?.equity_curve || [];
  const strategyPerf = analytics?.strategy_performance || {};

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Trade Journal</h1>
          <p className="text-gray-400 mt-1">Performance analytics and trade history</p>
        </div>
        <button
          onClick={fetchAnalytics}
          className="px-4 py-2 bg-accent-blue text-white rounded hover:bg-accent-blue/80"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-loss-red/10 border border-loss-red text-loss-red p-4 rounded-lg">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        {['overview', 'trades', 'signals', 'strategies'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab as any)}
            className={`px-4 py-2 rounded font-medium transition-colors ${
              activeTab === tab
                ? 'bg-accent-blue text-white'
                : 'bg-trading-card text-gray-400 hover:bg-trading-border'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <>
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <Activity size={18} />
                <span className="text-sm">Total Trades</span>
              </div>
              <div className="text-3xl font-bold text-white">{performance.total_trades || 0}</div>
            </div>
            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <TrendingUp size={18} />
                <span className="text-sm">Win Rate</span>
              </div>
              <div className="text-3xl font-bold text-profit-green">{performance.win_rate || 0}%</div>
            </div>
            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <TrendingDown size={18} />
                <span className="text-sm">Total PnL</span>
              </div>
              <div className={`text-3xl font-bold ${performance.total_pnl >= 0 ? 'text-profit-green' : 'text-loss-red'}`}>
                ₹{performance.total_pnl?.toFixed(2) || 0}
              </div>
            </div>
            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <PieChart size={18} />
                <span className="text-sm">Profit Factor</span>
              </div>
              <div className="text-3xl font-bold text-accent-blue">{performance.profit_factor || 0}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Performance Metrics</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Winning Trades</span>
              <span className="text-profit-green">{performance.winning_trades || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Losing Trades</span>
                  <span className="text-loss-red">{performance.losing_trades || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Average Win</span>
                  <span className="text-profit-green">₹{performance.avg_win?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Average Loss</span>
                  <span className="text-loss-red">₹{performance.avg_loss?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Gross Profit</span>
                  <span className="text-profit-green">₹{performance.gross_profit?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Gross Loss</span>
                  <span className="text-loss-red">₹{performance.gross_loss?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Expectancy</span>
                  <span className={performance.expectancy >= 0 ? 'text-profit-green' : 'text-loss-red'}>
                    ₹{performance.expectancy?.toFixed(2) || 0}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Additional Metrics</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Largest Win</span>
                  <span className="text-profit-green">₹{performance.largest_win?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Largest Loss</span>
                  <span className="text-loss-red">₹{performance.largest_loss?.toFixed(2) || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Avg Trade Duration</span>
                  <span className="text-white">{performance.avg_trade_duration || 0} min</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Best Day</span>
                  <span className="text-profit-green">{performance.best_day || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Worst Day</span>
                  <span className="text-loss-red">{performance.worst_day || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>

          {equityCurve.length > 0 && (
            <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Equity Curve</h3>
              <div className="h-48 flex items-end gap-1">
                {equityCurve.slice(-50).map((point: any, i: number) => (
                  <div
                    key={i}
                    className="flex-1 bg-accent-blue/50 rounded-t"
                    style={{ height: `${Math.min(100, (parseFloat(point.equity) / Math.max(...equityCurve.map((p: any) => parseFloat(p.equity)))) * 100)}%` }}
                  />
                ))}
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-2">
                <span>Oldest</span>
                <span>Latest</span>
              </div>
            </div>
          )}
        </>
      )}

      {activeTab === 'trades' && (
        <TradeLogTable />
      )}

      {activeTab === 'signals' && (
        <SignalLogTable />
      )}

      {activeTab === 'strategies' && (
        <StrategyBreakdown strategies={strategyPerf} />
      )}
    </div>
  );
};

const TradeLogTable: React.FC = () => {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    journalService.getTrades({ limit: 50 }).then((res) => {
      setTrades(res.trades);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400">Loading trades...</div>;

  return (
    <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full">
          <thead className="bg-trading-border sticky top-0">
            <tr className="text-left text-gray-400 text-sm">
              <th className="p-3">Symbol</th>
              <th className="p-3">Direction</th>
              <th className="p-3">Entry</th>
              <th className="p-3">Exit</th>
              <th className="p-3">Qty</th>
              <th className="p-3">PnL</th>
              <th className="p-3">Result</th>
              <th className="p-3">Strategy</th>
              <th className="p-3">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trading-border">
            {trades.map((trade, i) => (
              <tr key={i} className="hover:bg-trading-border/50">
                <td className="p-3 text-white font-medium">{trade.symbol}</td>
                <td className="p-3">
                  <span className={trade.direction === 'BUY' ? 'text-profit-green' : 'text-loss-red'}>
                    {trade.direction}
                  </span>
                </td>
                <td className="p-3 text-gray-300">₹{trade.entry_price}</td>
                <td className="p-3 text-gray-300">₹{trade.exit_price || '-'}</td>
                <td className="p-3 text-gray-300">{trade.quantity}</td>
                <td className={`p-3 font-medium ${parseFloat(trade.pnl) >= 0 ? 'text-profit-green' : 'text-loss-red'}`}>
                  ₹{parseFloat(trade.pnl).toFixed(2)}
                </td>
                <td className="p-3">
                  <span className={`px-2 py-1 rounded text-xs ${
                    trade.result === 'WIN' ? 'bg-profit-green/20 text-profit-green' :
                    trade.result === 'LOSS' ? 'bg-loss-red/20 text-loss-red' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {trade.result}
                  </span>
                </td>
                <td className="p-3 text-gray-400">{trade.strategy}</td>
                <td className="p-3 text-gray-400 text-xs">
                  {trade.entry_time ? new Date(trade.entry_time).toLocaleDateString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {trades.length === 0 && (
          <div className="p-8 text-center text-gray-400">No trades found</div>
        )}
      </div>
    </div>
  );
};

const SignalLogTable: React.FC = () => {
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    journalService.getSignals({ limit: 50 }).then((res) => {
      setSignals(res.signals);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400">Loading signals...</div>;

  return (
    <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full">
          <thead className="bg-trading-border sticky top-0">
            <tr className="text-left text-gray-400 text-sm">
              <th className="p-3">Symbol</th>
              <th className="p-3">Type</th>
              <th className="p-3">Entry</th>
              <th className="p-3">SL</th>
              <th className="p-3">TP</th>
              <th className="p-3">Status</th>
              <th className="p-3">Strategy</th>
              <th className="p-3">Confidence</th>
              <th className="p-3">Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trading-border">
            {signals.map((signal, i) => (
              <tr key={i} className="hover:bg-trading-border/50">
                <td className="p-3 text-white font-medium">{signal.symbol}</td>
                <td className="p-3">
                  <span className={signal.signal_type === 'BUY' ? 'text-profit-green' : 'text-loss-red'}>
                    {signal.signal_type}
                  </span>
                </td>
                <td className="p-3 text-gray-300">₹{signal.entry || '-'}</td>
                <td className="p-3 text-gray-300">₹{signal.stop_loss || '-'}</td>
                <td className="p-3 text-gray-300">₹{signal.take_profit || '-'}</td>
                <td className="p-3">
                  <span className={`px-2 py-1 rounded text-xs ${
                    signal.executed === 'TRUE' ? 'bg-profit-green/20 text-profit-green' : 'bg-loss-red/20 text-loss-red'
                  }`}>
                    {signal.executed === 'TRUE' ? 'Executed' : 'Rejected'}
                  </span>
                </td>
                <td className="p-3 text-gray-400">{signal.strategy}</td>
                <td className="p-3 text-gray-300">{signal.confidence}%</td>
                <td className="p-3 text-gray-400 text-xs max-w-[200px] truncate">{signal.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {signals.length === 0 && (
          <div className="p-8 text-center text-gray-400">No signals found</div>
        )}
      </div>
    </div>
  );
};

const StrategyBreakdown: React.FC<{ strategies: Record<string, any> }> = ({ strategies }) => {
  const strategyList = Object.entries(strategies);

  return (
    <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full">
          <thead className="bg-trading-border sticky top-0">
            <tr className="text-left text-gray-400 text-sm">
              <th className="p-3">Strategy</th>
              <th className="p-3">Trades</th>
              <th className="p-3">Wins</th>
              <th className="p-3">Losses</th>
              <th className="p-3">Win Rate</th>
              <th className="p-3">Total PnL</th>
              <th className="p-3">Avg PnL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trading-border">
            {strategyList.map(([name, stats], i) => (
              <tr key={i} className="hover:bg-trading-border/50">
                <td className="p-3 text-white font-medium">{name}</td>
                <td className="p-3 text-gray-300">{stats.trades}</td>
                <td className="p-3 text-profit-green">{stats.wins}</td>
                <td className="p-3 text-loss-red">{stats.losses}</td>
                <td className="p-3">
                  <span className={stats.win_rate >= 50 ? 'text-profit-green' : 'text-loss-red'}>
                    {stats.win_rate}%
                  </span>
                </td>
                <td className={`p-3 font-medium ${stats.total_pnl >= 0 ? 'text-profit-green' : 'text-loss-red'}`}>
                  ₹{stats.total_pnl?.toFixed(2)}
                </td>
                <td className={`p-3 ${stats.avg_pnl >= 0 ? 'text-profit-green' : 'text-loss-red'}`}>
                  ₹{stats.avg_pnl?.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {strategyList.length === 0 && (
          <div className="p-8 text-center text-gray-400">No strategy data available</div>
        )}
      </div>
    </div>
  );
};

export default JournalPage;