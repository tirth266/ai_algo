import React, { useState } from 'react';
import apiClient from '../services/api';
import { Play, BarChart3, TrendingUp, Activity, DollarSign } from 'lucide-react';

interface BacktestResults {
  symbol: string;
  initial_capital: number;
  final_capital: number;
  total_pnl: number;
  return_percent: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  loss_rate: number;
  max_drawdown: number;
  sharpe_ratio: number;
  profit_factor: number;
  expectancy: number;
  avg_pnl: number;
  avg_win: number;
  avg_loss: number;
}

export const BacktestingPage: React.FC = () => {
  const [symbol, setSymbol] = useState('RELIANCE');
  const [timeframe, setTimeframe] = useState('5minute');
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [initialCapital, setInitialCapital] = useState(100000);
  const [capitalPerTrade, setCapitalPerTrade] = useState(25000);
  
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<BacktestResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detailedTrades, setDetailedTrades] = useState<any[]>([]);
  const runBacktest = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Sending backtest request:', {
        strategy: 'combined_power_strategy',
        symbol: symbol.toUpperCase(),
        timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        capital_per_trade: capitalPerTrade
      });
      
      const response = await apiClient.post('/backtest/run', {
        strategy: 'combined_power_strategy',
        symbol: symbol.toUpperCase(),
        timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        capital_per_trade: capitalPerTrade
      });
      

      
      if (response.data.success) {
        setResults(response.data.results);
        setDetailedTrades(response.data.detailed_trades || []);
      } else {
        setError(response.data.error || 'Backtest failed');
      }
    } catch (err: any) {
      console.error('Backtest error:', err);
      console.error('Error response:', err.response?.data);
      console.error('Error status:', err.response?.status);
      setError(err.response?.data?.error || err.message || 'Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(value);
  };

  const getStatusColor = (pnl: number) => {
    return pnl >= 0 ? 'text-profit-green' : 'text-loss-red';
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 size={28} className="text-accent-blue" />
            Backtesting Engine
          </h1>
          <p className="text-gray-400 mt-1">Test Combined Power Strategy on historical data</p>
        </div>
      </div>

      {/* Configuration Form */}
      <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
        <h3 className="text-lg font-semibold text-white mb-4">Backtest Configuration</h3>
        
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Symbol *</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
              placeholder="RELIANCE"
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-2">Timeframe *</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            >
              <option value="1minute">1 minute</option>
              <option value="5minute">5 minutes</option>
              <option value="15minute">15 minutes</option>
              <option value="30minute">30 minutes</option>
              <option value="60minute">1 hour</option>
              <option value="1day">1 day</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-2">Start Date *</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-2">End Date *</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-2">Initial Capital</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
              placeholder="100000"
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-2">Capital per Trade</label>
            <input
              type="number"
              value={capitalPerTrade}
              onChange={(e) => setCapitalPerTrade(Number(e.target.value))}
              className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
              placeholder="25000"
            />
          </div>
        </div>
        
        <button
          onClick={runBacktest}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 bg-accent-blue hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play size={18} />
          {loading ? 'Running Backtest...' : 'Run Backtest'}
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-loss-red/10 border border-loss-red rounded-lg p-4">
          <p className="text-loss-red font-medium">{error}</p>
        </div>
      )}

      {/* Results Display */}
      {results && (
        <>
          {/* Performance Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign size={20} className="text-accent-blue" />
                <span className="text-sm text-gray-400">Total P&L</span>
              </div>
              <div className={`text-2xl font-bold ${getStatusColor(results.total_pnl)}`}>
                {formatCurrency(results.total_pnl)}
              </div>
              <div className={`text-sm ${getStatusColor(results.return_percent)}`}>
                {results.return_percent.toFixed(2)}%
              </div>
            </div>
            
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <Activity size={20} className="text-profit-green" />
                <span className="text-sm text-gray-400">Win Rate</span>
              </div>
              <div className="text-2xl font-bold text-white">
                {results.win_rate.toFixed(1)}%
              </div>
              <div className="text-sm text-gray-400">
                {results.winning_trades}W / {results.losing_trades}L
              </div>
            </div>
            
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={20} className="text-accent-blue" />
                <span className="text-sm text-gray-400">Sharpe Ratio</span>
              </div>
              <div className="text-2xl font-bold text-white">
                {results.sharpe_ratio.toFixed(2)}
              </div>
              <div className="text-sm text-gray-400">
                Risk-adjusted return
              </div>
            </div>
            
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 size={20} className="text-loss-red" />
                <span className="text-sm text-gray-400">Max Drawdown</span>
              </div>
              <div className="text-2xl font-bold text-loss-red">
                {results.max_drawdown.toFixed(2)}%
              </div>
              <div className="text-sm text-gray-400">
                Largest peak decline
              </div>
            </div>
          </div>

          {/* Detailed Stats */}
          <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
            <h3 className="text-lg font-semibold text-white mb-4">Performance Statistics</h3>
            
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <div className="text-sm text-gray-400">Total Trades</div>
                <div className="text-xl font-bold text-white">{results.total_trades}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Profit Factor</div>
                <div className="text-xl font-bold text-white">{results.profit_factor.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Expectancy</div>
                <div className="text-xl font-bold text-white">{formatCurrency(results.expectancy)}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Average Win</div>
                <div className="text-xl font-bold text-profit-green">{formatCurrency(results.avg_win)}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Average Loss</div>
                <div className="text-xl font-bold text-loss-red">{formatCurrency(results.avg_loss)}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Final Capital</div>
                <div className="text-xl font-bold text-white">{formatCurrency(results.final_capital)}</div>
              </div>
            </div>
          </div>

          {/* Trade Log */}
          {detailedTrades.length > 0 && (
            <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Recent Trades ({detailedTrades.length})</h3>
              
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-trading-dark border-b border-trading-border">
                    <tr>
                      <th className="text-left px-4 py-3 text-sm text-gray-400">#</th>
                      <th className="text-left px-4 py-3 text-sm text-gray-400">Symbol</th>
                      <th className="text-left px-4 py-3 text-sm text-gray-400">Direction</th>
                      <th className="text-left px-4 py-3 text-sm text-gray-400">Entry</th>
                      <th className="text-left px-4 py-3 text-sm text-gray-400">Exit</th>
                      <th className="text-left px-4 py-3 text-sm text-gray-400">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailedTrades.slice(0, 20).map((trade, idx) => (
                      <tr key={trade.trade_id} className="border-b border-trading-border">
                        <td className="px-4 py-3 text-white text-sm">{idx + 1}</td>
                        <td className="px-4 py-3 text-white text-sm">{trade.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-1 rounded ${
                            trade.direction === 'BUY' 
                              ? 'bg-profit-green/10 text-profit-green' 
                              : 'bg-loss-red/10 text-loss-red'
                          }`}>
                            {trade.direction}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-sm">{formatCurrency(trade.entry_price)}</td>
                        <td className="px-4 py-3 text-gray-400 text-sm">{formatCurrency(trade.exit_price)}</td>
                        <td className={`px-4 py-3 text-sm font-medium ${getStatusColor(trade.pnl)}`}>
                          {formatCurrency(trade.pnl)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Info Box */}
      {!results && !loading && (
        <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
          <h3 className="text-lg font-semibold text-white mb-4">How Backtesting Works</h3>
          <div className="space-y-3 text-sm text-gray-400">
            <p>
              <strong className="text-white">1. Historical Data:</strong> Loads historical OHLCV data from Zerodha or generates mock data
            </p>
            <p>
              <strong className="text-white">2. Strategy Simulation:</strong> Runs Combined Power Strategy candle-by-candle
            </p>
            <p>
              <strong className="text-white">3. Realistic Execution:</strong> Applies slippage (0.05%) and brokerage (₹20/trade)
            </p>
            <p>
              <strong className="text-white">4. Risk Management:</strong> Enforces stop-loss (2%) and take-profit (4%)
            </p>
            <p>
              <strong className="text-white">5. Performance Analytics:</strong> Calculates comprehensive metrics including Sharpe ratio, drawdown, and win rate
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
