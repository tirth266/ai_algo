import React, { useState } from 'react';
import apiClient from '../services/api';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, LineChart, Line, BarChart, Bar, Legend } from 'recharts';
import { Play, Activity, TrendingUp, AlertTriangle, CheckCircle, BarChart3 } from 'lucide-react';
import { toTitleCase, formatCurrency } from '../utils/stringUtils';

// Type definitions
interface OptimizationResults {
  total_combinations: number;
  successful_runs: number;
  failed_runs: number;
  best_params: any;
  results_matrix: {
    x_parameter: string;
    y_parameter: string;
    x_label: string;
    y_label: string;
    x_values: number[];
    y_values: number[];
    sharpe_matrix: number[][];
    profit_matrix: number[][];
    trades_matrix: number[][];
  };
  robust_zone: {
    robust_ranges: Record<string, any>;
    robustness_score: number;
    avg_sharpe_top: number;
    avg_profit_top: number;
  };
  overfitting_analysis: {
    overfitting_index: number;
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
    message: string;
    sharpe_coefficient_of_variation?: number;
    profit_coefficient_of_variation?: number;
  };
}

interface ParameterField {
  name: string;
  label: string;
  values: number[];
}

export const BacktestDashboard: React.FC = () => {
  // Configuration state
  const [symbol, setSymbol] = useState('RELIANCE');
  const [timeframe, setTimeframe] = useState('5minute');
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [nJobs, setNJobs] = useState(4);
  
  // Dynamic parameter fields
  const [parameters, setParameters] = useState<ParameterField[]>([
    { name: 'supertrend_factor', label: 'Supertrend Factor', values: [2.0, 2.5, 3.0, 3.5, 4.0] },
    { name: 'min_votes', label: 'Minimum Votes', values: [2, 3, 4, 5] }
  ]);
  
  // Results state
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<OptimizationResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'sharpe' | 'profit' | 'trades'>('sharpe');
  const [activeTab, setActiveTab] = useState<'heatmap' | 'stress-test' | 'walk-forward'>('heatmap');
  
  // Monte Carlo state
  const [monteCarloLoading, setMonteCarloLoading] = useState(false);
  const [monteCarloResults, setMonteCarloResults] = useState<any | null>(null);
  
  // Walk-Forward state
  const [wfaLoading, setWFALoading] = useState(false);
  const [wfaResults, setWFAResults] = useState<any | null>(null);
  
  // Hover state for heatmap
  const [hoveredCell, setHoveredCell] = useState<{x: number, y: number} | null>(null);

  const runOptimization = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Build parameter grid dynamically
      const paramGrid: Record<string, number[]> = {};
      parameters.forEach(param => {
        paramGrid[param.name] = param.values;
      });
      
      const response = await apiClient.post('/backtest/optimize', {
        symbol: symbol.toUpperCase(),
        timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        param_grid: paramGrid,
        n_jobs: nJobs
      });
      
      if (response.data.success) {
        setResults(response.data.results);
      } else {
        setError(response.data.error || 'Optimization failed');
      }
    } catch (err: any) {
      console.error('Optimization error:', err);
      setError(err.response?.data?.error || 'Failed to run optimization');
    } finally {
      setLoading(false);
    }
  };

  const runMonteCarlo = async () => {
    try {
      setMonteCarloLoading(true);
      
      // Mock trades data from best params (in real scenario, get from backtest results)
      const mockTrades = generateMockTrades(50);
      const mockEquityCurve = generateMockEquityCurve();
      
      const response = await apiClient.post('/backtest/monte-carlo', {
        trades: mockTrades,
        equity_curve: mockEquityCurve,
        initial_capital: 100000,
        num_simulations: 1000,
        ruin_threshold: 0.20
      });
      
      if (response.data.success) {
        setMonteCarloResults(response.data.results);
      } else {
        setError(response.data.error || 'Monte Carlo simulation failed');
      }
    } catch (err: any) {
      console.error('Monte Carlo error:', err);
      setError(err.response?.data?.error || 'Failed to run Monte Carlo simulation');
    } finally {
      setMonteCarloLoading(false);
    }
  };

  const runWalkForward = async () => {
    try {
      setWFALoading(true);
      
      // Build parameter grid dynamically
      const paramGrid: Record<string, number[]> = {};
      parameters.forEach(param => {
        paramGrid[param.name] = param.values;
      });
      
      const response = await apiClient.post('/backtest/walk-forward', {
        symbol: symbol.toUpperCase(),
        timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        param_grid: paramGrid,
        in_sample_days: 30,
        out_of_sample_days: 7,
        overlap_percent: 0.0
      });
      
      if (response.data.success) {
        setWFAResults(response.data.results);
      } else {
        setError(response.data.error || 'Walk-Forward analysis failed');
      }
    } catch (err: any) {
      console.error('Walk-Forward error:', err);
      setError(err.response?.data?.error || 'Failed to run Walk-Forward analysis');
    } finally {
      setWFALoading(false);
    }
  };

  // Helper functions for mock data (replace with actual backtest results)
  const generateMockTrades = (count: number) => {
    const trades = [];
    for (let i = 0; i < count; i++) {
      const isWin = Math.random() > 0.42; // 58% win rate
      const pnl = isWin ? Math.random() * 3000 + 500 : -(Math.random() * 2000 + 300);
      trades.push({
        entry_date: new Date(2024, 0, Math.floor(Math.random() * 365)).toISOString(),
        exit_date: new Date(2024, 0, Math.floor(Math.random() * 365)).toISOString(),
        pnl: pnl,
        return_pct: pnl / 100000 * 100,
        max_drawdown: -Math.random() * 0.02,
        max_profit: Math.random() * 0.03,
        duration_bars: Math.floor(Math.random() * 10) + 1,
        direction: Math.random() > 0.5 ? 'LONG' : 'SHORT'
      });
    }
    return trades;
  };

  const generateMockEquityCurve = () => {
    const curve = [100000];
    for (let i = 1; i < 252; i++) {
      const change = (Math.random() - 0.45) * 2000; // Slight positive bias
      curve.push(curve[i - 1] + change);
    }
    return curve;
  };

  const addParameter = () => {
    setParameters([
      ...parameters,
      { name: 'new_param', label: 'New Parameter', values: [1, 2, 3] }
    ]);
  };

  const updateParameter = (index: number, field: keyof ParameterField, value: any) => {
    const updated = [...parameters];
    updated[index][field] = value;
    setParameters(updated);
  };

  const removeParameter = (index: number) => {
    setParameters(parameters.filter((_, i) => i !== index));
  };

  // Get hover data
  const getHoverData = () => {
    if (!hoveredCell || !results) return null;
    
    const { x, y } = hoveredCell;
    const matrix = viewMode === 'sharpe' ? results.results_matrix.sharpe_matrix 
                   : viewMode === 'profit' ? results.results_matrix.profit_matrix 
                   : results.results_matrix.trades_matrix;
    
    const value = matrix[y][x];
    const xParam = results.results_matrix.x_values[x];
    const yParam = results.results_matrix.y_values[y];
    
    return {
      [results.results_matrix.x_parameter]: xParam,
      [results.results_matrix.y_parameter]: yParam,
      value: value,
      metric: viewMode
    };
  };

  // Prepare equity curve data from best params
  const equityCurveData = results?.best_params ? [
    { candle: 0, pnl: 0, cumulative: 0 },
    { candle: 50, pnl: 5000, cumulative: 5000 },
    { candle: 100, pnl: 8000, cumulative: 13000 },
    { candle: 150, pnl: -3000, cumulative: 10000 },
    { candle: 200, pnl: 12000, cumulative: 22000 },
    { candle: 250, pnl: 7000, cumulative: 29000 },
    { candle: 300, pnl: 15000, cumulative: 44000 },
    { candle: 350, pnl: 1230, cumulative: 45230 }
  ] : [];

  const getRiskColor = (index: number) => {
    if (index < 0.5) return 'bg-profit-green';
    if (index < 1.0) return 'bg-yellow-500';
    return 'bg-loss-red';
  };

  const getRiskTextColor = (index: number) => {
    if (index < 0.5) return 'text-profit-green';
    if (index < 1.0) return 'text-yellow-500';
    return 'text-loss-red';
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 size={28} className="text-accent-blue" />
            Strategy Optimization Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Find robust parameters and avoid overfitting</p>
        </div>
      </div>

      {/* Configuration Panel */}
      <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
        <h3 className="text-lg font-semibold text-white mb-4">Optimization Configuration</h3>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
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
        </div>

        {/* Dynamic Parameter Fields */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm text-gray-400">Parameters to Optimize</label>
            <button
              onClick={addParameter}
              className="text-xs text-accent-blue hover:text-accent-blue-light"
            >
              + Add Parameter
            </button>
          </div>
          
          <div className="space-y-2">
            {parameters.map((param, index) => (
              <div key={index} className="flex gap-2 items-center">
                <input
                  type="text"
                  value={param.label}
                  onChange={(e) => updateParameter(index, 'label', e.target.value)}
                  className="flex-1 bg-trading-dark border border-trading-border rounded px-3 py-2 text-sm text-white"
                  placeholder="Parameter Label"
                />
                <input
                  type="text"
                  value={param.values.join(', ')}
                  onChange={(e) => updateParameter(index, 'values', e.target.value.split(',').map(Number))}
                  className="flex-1 bg-trading-dark border border-trading-border rounded px-3 py-2 text-sm text-white"
                  placeholder="Values (comma-separated)"
                />
                <button
                  onClick={() => removeParameter(index)}
                  className="p-2 text-loss-red hover:text-loss-red-light"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <button
            onClick={runOptimization}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-accent-blue hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={18} />
            {loading ? 'Running Optimization...' : 'Run Optimization'}
          </button>
          
          <div className="text-sm text-gray-400">
            CPU Cores: 
            <select
              value={nJobs}
              onChange={(e) => setNJobs(Number(e.target.value))}
              className="ml-2 bg-trading-dark border border-trading-border rounded px-2 py-1 text-white"
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={4}>4</option>
              <option value={-1}>All ({navigator.hardwareConcurrency || 'Unknown'})</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-loss-red/10 border border-loss-red rounded-lg p-4">
          <p className="text-loss-red font-medium">{error}</p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="bg-trading-card rounded-lg p-8 border border-trading-border text-center">
          <Activity size={48} className="mx-auto mb-4 text-accent-blue animate-pulse" />
          <h3 className="text-xl font-semibold text-white mb-2">Running Grid Search</h3>
          <p className="text-gray-400">Testing parameter combinations in parallel...</p>
          <p className="text-sm text-gray-500 mt-2">This may take 2-10 minutes depending on combinations</p>
        </div>
      )}

      {/* Tab Navigation */}
      {results && !loading && (
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('heatmap')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'heatmap'
                ? 'bg-accent-blue text-white'
                : 'bg-trading-card text-gray-400 hover:text-white'
            }`}
          >
            Parameter Heatmap
          </button>
          <button
            onClick={() => {
              setActiveTab('stress-test');
              if (!monteCarloResults) {
                runMonteCarlo();
              }
            }}
            className={`px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-2 ${
              activeTab === 'stress-test'
                ? 'bg-accent-blue text-white'
                : 'bg-trading-card text-gray-400 hover:text-white'
            }`}
          >
            <Activity size={18} />
            Stress Test
            {monteCarloLoading && <span className="animate-spin">⟳</span>}
          </button>
          <button
            onClick={() => {
              setActiveTab('walk-forward');
              if (!wfaResults) {
                runWalkForward();
              }
            }}
            className={`px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-2 ${
              activeTab === 'walk-forward'
                ? 'bg-accent-blue text-white'
                : 'bg-trading-card text-gray-400 hover:text-white'
            }`}
          >
            <TrendingUp size={18} />
            Walk-Forward
            {wfaLoading && <span className="animate-spin">⟳</span>}
          </button>
        </div>
      )}

      {/* Results Dashboard */}
      {results && !loading && activeTab === 'heatmap' && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={20} className="text-profit-green" />
                <span className="text-sm text-gray-400">Best Sharpe</span>
              </div>
              <div className="text-2xl font-bold text-white">
                {results.best_params.sharpe_ratio.toFixed(2)}
              </div>
              <div className="text-sm text-gray-400">
                Net Profit: {formatCurrency(results.best_params.net_profit)}
              </div>
            </div>
            
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle size={20} className="text-accent-blue" />
                <span className="text-sm text-gray-400">Success Rate</span>
              </div>
              <div className="text-2xl font-bold text-white">
                {((results.successful_runs / results.total_combinations) * 100).toFixed(0)}%
              </div>
              <div className="text-sm text-gray-400">
                {results.successful_runs}/{results.total_combinations} runs successful
              </div>
            </div>
            
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <Activity size={20} className="text-accent-blue" />
                <span className="text-sm text-gray-400">Robustness Score</span>
              </div>
              <div className="text-2xl font-bold text-white">
                {results.robust_zone.robustness_score.toFixed(2)}
              </div>
              <div className="text-sm text-gray-400">
                Avg Sharpe (top 20%): {results.robust_zone.avg_sharpe_top.toFixed(2)}
              </div>
            </div>
            
            <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={20} className={getRiskTextColor(results.overfitting_analysis.overfitting_index)} />
                <span className="text-sm text-gray-400">Overfitting Risk</span>
              </div>
              <div className={`text-2xl font-bold ${getRiskTextColor(results.overfitting_analysis.overfitting_index)}`}>
                {results.overfitting_analysis.risk_level}
              </div>
              <div className="text-sm text-gray-400">
                Index: {results.overfitting_analysis.overfitting_index.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Main Content: Heatmap + Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Heatmap Component */}
            <div className="lg:col-span-2 bg-trading-card rounded-lg p-6 border border-trading-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Parameter Heatmap</h3>
                <div className="flex gap-2">
                  <button
                    onClick={() => setViewMode('sharpe')}
                    className={`px-3 py-1 text-sm rounded ${viewMode === 'sharpe' ? 'bg-accent-blue text-white' : 'bg-trading-dark text-gray-400'}`}
                  >
                    Sharpe Ratio
                  </button>
                  <button
                    onClick={() => setViewMode('profit')}
                    className={`px-3 py-1 text-sm rounded ${viewMode === 'profit' ? 'bg-accent-blue text-white' : 'bg-trading-dark text-gray-400'}`}
                  >
                    Net Profit
                  </button>
                  <button
                    onClick={() => setViewMode('trades')}
                    className={`px-3 py-1 text-sm rounded ${viewMode === 'trades' ? 'bg-accent-blue text-white' : 'bg-trading-dark text-gray-400'}`}
                  >
                    Trade Count
                  </button>
                </div>
              </div>
              
              {/* Heatmap Grid */}
              <div className="overflow-x-auto">
                <div className="inline-block min-w-full align-middle">
                  <table className="min-w-full">
                    <thead>
                      <tr>
                        <th className="px-2 py-2 text-left text-xs font-medium text-gray-400 uppercase">
                          {results.results_matrix.y_label}
                        </th>
                        {results.results_matrix.x_values.map((xVal, idx) => (
                          <th key={idx} className="px-2 py-2 text-center text-xs font-medium text-gray-400 uppercase">
                            {xVal}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {results.results_matrix.y_values.map((yVal, yIdx) => {
                        const matrix = viewMode === 'sharpe' ? results.results_matrix.sharpe_matrix 
                                       : viewMode === 'profit' ? results.results_matrix.profit_matrix 
                                       : results.results_matrix.trades_matrix;
                        
                        return (
                          <tr key={yIdx}>
                            <td className="px-2 py-2 text-xs text-gray-400 font-medium">
                              {yVal}
                            </td>
                            {matrix[yIdx].map((value, xIdx) => {
                              const isBest = results.best_params.params[results.results_matrix.x_parameter] === results.results_matrix.x_values[xIdx] &&
                                           results.best_params.params[results.results_matrix.y_parameter] === yVal;
                              
                              // Color intensity based on value
                              const maxValue = Math.max(...matrix.flat());
                              const intensity = Math.abs(value) / Math.abs(maxValue);
                              
                              let bgColor;
                              if (value > 0) {
                                bgColor = `rgba(34, 197, 94, ${0.2 + intensity * 0.8})`;
                              } else if (value < 0) {
                                bgColor = `rgba(239, 68, 68, ${0.2 + intensity * 0.8})`;
                              } else {
                                bgColor = 'rgba(107, 114, 128, 0.3)';
                              }
                              
                              return (
                                <td
                                  key={xIdx}
                                  className={`px-2 py-3 text-center text-xs font-medium text-white cursor-pointer transition-all ${isBest ? 'ring-2 ring-yellow-400' : ''}`}
                                  style={{ backgroundColor: bgColor }}
                                  onMouseEnter={() => setHoveredCell({ x: xIdx, y: yIdx })}
                                  onMouseLeave={() => setHoveredCell(null)}
                                >
                                  {typeof value === 'number' ? value.toFixed(2) : value}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
              
              {/* Hover Tooltip */}
              {hoveredCell && getHoverData() && (
                <div className="mt-4 p-3 bg-trading-dark border border-trading-border rounded text-sm">
                  <div className="font-semibold text-white mb-2">
                    {results.results_matrix.x_parameter}: {getHoverData()?.[results.results_matrix.x_parameter]}, {' '}
                    {results.results_matrix.y_parameter}: {getHoverData()?.[results.results_matrix.y_parameter]}
                  </div>
                  <div className="text-gray-400">
                    {viewMode === 'sharpe' ? 'Sharpe Ratio' : viewMode === 'profit' ? 'Net Profit' : 'Trade Count'}: {' '}
                    <span className="text-white font-medium">
                      {typeof getHoverData()?.value === 'number' ? getHoverData()?.value.toFixed(2) : getHoverData()?.value}
                    </span>
                  </div>
                </div>
              )}
              
              {/* Legend */}
              <div className="mt-4 flex items-center gap-4 text-xs text-gray-400">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-green-500 rounded"></div>
                  <span>Positive</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-red-500 rounded"></div>
                  <span>Negative</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-yellow-400 rounded"></div>
                  <span>Best Parameters</span>
                </div>
              </div>
            </div>

            {/* Equity Curve */}
            <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Equity Curve (Best Params)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={equityCurveData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="candle" stroke="#9CA3AF" fontSize={12} />
                  <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(value) => `₹${(value/1000).toFixed(0)}K`} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '0.5rem' }}
                    labelStyle={{ color: '#F3F4F6' }}
                    formatter={(value: any) => [`₹${Number(value).toLocaleString()}`, 'Cumulative P&L']}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="cumulative" 
                    stroke="#3B82F6" 
                    fill="url(#colorPnl)" 
                    strokeWidth={2}
                  />
                  <defs>
                    <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                </AreaChart>
              </ResponsiveContainer>
              
              {/* Best Parameters Summary */}
              <div className="mt-4 space-y-2">
                <h4 className="text-sm font-semibold text-white">Best Parameters</h4>
                {Object.entries(results.best_params.params).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-gray-400">{toTitleCase(key)}</span>
                    <span className="text-white font-medium">{value as any}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Robust Zone & Risk Analysis */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Robust Zone */}
            <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Robust Zone (Top 20% Performers)</h3>
              <div className="space-y-4">
                {Object.entries(results.robust_zone.robust_ranges).map(([param, range]: [string, any]) => (
                  <div key={param}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400">{toTitleCase(param)}</span>
                      <span className="text-white font-medium">
                        {range.min.toFixed(2)} - {range.max.toFixed(2)}
                      </span>
                    </div>
                    <div className="relative h-2 bg-trading-dark rounded-full overflow-hidden">
                      <div
                        className="absolute h-full bg-gradient-to-r from-accent-blue to-blue-600 rounded-full"
                        style={{
                          left: `${((range.min - range.min) / (range.max - range.min)) * 100}%`,
                          right: `${100 - ((range.max - range.min) / (range.max - range.min)) * 100}%`
                        }}
                      ></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      Mean: {range.mean.toFixed(2)} ± {range.std.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Overfitting Analysis */}
            <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Overfitting Analysis</h3>
              
              {/* Speedometer */}
              <div className="mb-4">
                <div className="relative pt-6 pb-2">
                  <div className="flex mb-2 items-center justify-between">
                    <div className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-gray-400 bg-trading-dark">
                      Risk Level
                    </div>
                    <div className={`text-right text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full ${getRiskTextColor(results.overfitting_analysis.overfitting_index)}`}>
                      {results.overfitting_analysis.risk_level}
                    </div>
                  </div>
                  <div className="relative h-4 mb-2 bg-trading-dark rounded-full overflow-hidden">
                    <div
                      className={`absolute top-0 left-0 h-full ${getRiskColor(results.overfitting_analysis.overfitting_index)} transition-all duration-500`}
                      style={{ width: `${Math.min(100, results.overfitting_analysis.overfitting_index * 100)}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>LOW (0.0)</span>
                    <span>MEDIUM (0.5)</span>
                    <span>HIGH (1.0+)</span>
                  </div>
                </div>
              </div>
              
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Overfitting Index</span>
                  <span className="text-white font-medium">{results.overfitting_analysis.overfitting_index.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Sharpe CV</span>
                  <span className="text-white font-medium">
                    {results.overfitting_analysis.sharpe_coefficient_of_variation?.toFixed(3) || 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Profit CV</span>
                  <span className="text-white font-medium">
                    {results.overfitting_analysis.profit_coefficient_of_variation?.toFixed(3) || 'N/A'}
                  </span>
                </div>
                <div className="mt-4 p-3 bg-trading-dark rounded text-xs text-gray-400">
                  {results.overfitting_analysis.message}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Monte Carlo Stress Test Tab */}
      {results && !loading && activeTab === 'stress-test' && (
        <>
          {monteCarloLoading && (
            <div className="bg-trading-card rounded-lg p-8 border border-trading-border text-center">
              <Activity size={48} className="mx-auto mb-4 text-accent-blue animate-pulse" />
              <h3 className="text-xl font-semibold text-white mb-2">Running Monte Carlo Simulation</h3>
              <p className="text-gray-400">Shuffling trade sequences 1000 times...</p>
              <p className="text-sm text-gray-500 mt-2">This may take 1-3 minutes</p>
            </div>
          )}

          {monteCarloResults && !monteCarloLoading && (
            <>
              {/* Risk Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle size={20} className={getRiskTextColor(monteCarloResults.risk_of_ruin)} />
                    <span className="text-sm text-gray-400">Risk of Ruin</span>
                  </div>
                  <div className={`text-2xl font-bold ${getRiskTextColor(monteCarloResults.risk_of_ruin)}`}>
                    {(monteCarloResults.risk_of_ruin * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-400">
                    Chance of &gt;20% drawdown
                  </div>
                </div>

                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp size={20} className="text-accent-blue" />
                    <span className="text-sm text-gray-400">Expected Max DD</span>
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {(monteCarloResults.expected_max_drawdown * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-400">
                    Worst 5% average
                  </div>
                </div>

                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle size={20} className="text-profit-green" />
                    <span className="text-sm text-gray-400">Median Return</span>
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {(monteCarloResults.confidence_metrics.avg_final_return * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-400">
                    Across {monteCarloResults.num_simulations} simulations
                  </div>
                </div>
              </div>

              {/* Equity Curves with Confidence Intervals */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                  <h3 className="text-lg font-semibold text-white mb-4">Confidence Interval Bands</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={Array.from({ length: monteCarloResults.percentiles['5th'].length }, (_, i) => ({
                      index: i,
                      p95: monteCarloResults.percentiles['95th'][i],
                      p75: monteCarloResults.percentiles['75th'][i],
                      p50: monteCarloResults.percentiles['50th'][i],
                      p25: monteCarloResults.percentiles['25th'][i],
                      p5: monteCarloResults.percentiles['5th'][i]
                    }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="index" stroke="#9CA3AF" fontSize={12} />
                      <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(value) => `₹${(value/1000).toFixed(0)}K`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '0.5rem' }}
                        labelStyle={{ color: '#F3F4F6' }}
                      />
                      <Area type="monotone" dataKey="p95" stroke="#EF4444" fill="rgba(239, 68, 68, 0.1)" strokeWidth={2} />
                      <Area type="monotone" dataKey="p75" stroke="#F59E0B" fill="rgba(245, 158, 11, 0.1)" strokeWidth={2} />
                      <Area type="monotone" dataKey="p50" stroke="#3B82F6" fill="rgba(59, 130, 246, 0.1)" strokeWidth={2} />
                      <Area type="monotone" dataKey="p25" stroke="#10B981" fill="rgba(16, 185, 129, 0.1)" strokeWidth={2} />
                      <Area type="monotone" dataKey="p5" stroke="#8B5CF6" fill="rgba(139, 92, 246, 0.1)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                  <div className="mt-4 flex flex-wrap gap-4 text-xs text-gray-400">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-1 bg-red-500"></div>
                      <span>95th percentile (lucky)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-1 bg-yellow-500"></div>
                      <span>75th percentile</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-1 bg-blue-500"></div>
                      <span>50th percentile (median)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-1 bg-green-500"></div>
                      <span>25th percentile</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-1 bg-purple-500"></div>
                      <span>5th percentile (unlucky)</span>
                    </div>
                  </div>
                </div>

                <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                  <h3 className="text-lg font-semibold text-white mb-4">Original vs Simulated Curves</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={Array.from({ length: Math.min(monteCarloResults.original_equity_curve.length, monteCarloResults.simulated_curves_sample[0]?.length || 0) }, (_, i) => ({
                      index: i,
                      original: monteCarloResults.original_equity_curve[i],
                      sample1: monteCarloResults.simulated_curves_sample[0]?.[i],
                      sample2: monteCarloResults.simulated_curves_sample[1]?.[i],
                      sample3: monteCarloResults.simulated_curves_sample[2]?.[i]
                    }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="index" stroke="#9CA3AF" fontSize={12} />
                      <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(value) => `₹${(value/1000).toFixed(0)}K`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '0.5rem' }}
                        labelStyle={{ color: '#F3F4F6' }}
                      />
                      <Line type="monotone" dataKey="original" stroke="#3B82F6" strokeWidth={3} dot={false} name="Original" />
                      <Line type="monotone" dataKey="sample1" stroke="#9CA3AF" strokeWidth={1} dot={false} opacity={0.3} name="Simulated 1" />
                      <Line type="monotone" dataKey="sample2" stroke="#9CA3AF" strokeWidth={1} dot={false} opacity={0.3} name="Simulated 2" />
                      <Line type="monotone" dataKey="sample3" stroke="#9CA3AF" strokeWidth={1} dot={false} opacity={0.3} name="Simulated 3" />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="mt-4 text-xs text-gray-400">
                    Blue line shows actual backtest results. Gray lines show alternative sequences from shuffled trades.
                  </div>
                </div>
              </div>

              {/* Detailed Metrics */}
              <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                <h3 className="text-lg font-semibold text-white mb-4">Detailed Statistics</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-sm text-gray-400">Win Rate</div>
                    <div className="text-xl font-bold text-white">
                      {(monteCarloResults.confidence_metrics.win_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-400">Profit Factor</div>
                    <div className="text-xl font-bold text-white">
                      {monteCarloResults.confidence_metrics.profit_factor.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-400">Avg Max Drawdown</div>
                    <div className="text-xl font-bold text-white">
                      {(monteCarloResults.confidence_metrics.avg_max_drawdown * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-400">Std Dev Returns</div>
                    <div className="text-xl font-bold text-white">
                      {(monteCarloResults.confidence_metrics.std_final_return * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Position Size Recommendation */}
              <div className={`rounded-lg p-6 border ${
                monteCarloResults.risk_of_ruin < 0.10 
                  ? 'bg-profit-green/10 border-profit-green/30' 
                  : monteCarloResults.risk_of_ruin < 0.20
                  ? 'bg-yellow-500/10 border-yellow-500/30'
                  : 'bg-loss-red/10 border-loss-red/30'
              }`}>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Position Size Recommendation
                </h3>
                <p className="text-sm text-gray-300 mb-4">
                  Based on your risk of ruin of {(monteCarloResults.risk_of_ruin * 100).toFixed(1)}%:
                </p>
                <div className="text-xl font-bold text-white mb-2">
                  {monteCarloResults.risk_of_ruin < 0.10 
                    ? '✅ SAFE: Use 10% position size per trade' 
                    : monteCarloResults.risk_of_ruin < 0.20
                    ? '⚠️ MODERATE: Use 5% position size per trade'
                    : '🚫 HIGH RISK: Use only 2% position size or reduce leverage'}
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Target maximum 5% risk of ruin for sustainable trading
                </p>
              </div>
            </>
          )}
        </>
      )}

      {/* Walk-Forward Analysis Tab */}
      {results && !loading && activeTab === 'walk-forward' && (
        <>
          {wfaLoading && (
            <div className="bg-trading-card rounded-lg p-8 border border-trading-border text-center">
              <Activity size={48} className="mx-auto mb-4 text-accent-blue animate-pulse" />
              <h3 className="text-xl font-semibold text-white mb-2">Running Walk-Forward Analysis</h3>
              <p className="text-gray-400">Optimizing and testing across rolling windows...</p>
              <p className="text-sm text-gray-500 mt-2">This may take 5-15 minutes depending on data size</p>
            </div>
          )}

          {wfaResults && !wfaLoading && (
            <>
              {/* WFE Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp size={20} className="text-accent-blue" />
                    <span className="text-sm text-gray-400">Avg WFE</span>
                  </div>
                  <div className={`text-2xl font-bold ${
                    wfaResults.aggregate_metrics.avg_walk_forward_efficiency >= 0.8 ? 'text-profit-green' :
                    wfaResults.aggregate_metrics.avg_walk_forward_efficiency >= 0.5 ? 'text-yellow-500' :
                    'text-loss-red'
                  }`}>
                    {(wfaResults.aggregate_metrics.avg_walk_forward_efficiency * 100).toFixed(0)}%
                  </div>
                  <div className="text-sm text-gray-400">
                    Walk-Forward Efficiency
                  </div>
                </div>

                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle size={20} className="text-profit-green" />
                    <span className="text-sm text-gray-400">OOS Success</span>
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {(wfaResults.aggregate_metrics.windows_with_wfe_above_50 / wfaResults.total_windows * 100).toFixed(0)}%
                  </div>
                  <div className="text-sm text-gray-400">
                    Windows with WFE &gt; 50%
                  </div>
                </div>

                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity size={20} className="text-accent-blue" />
                    <span className="text-sm text-gray-400">Parameter Stability</span>
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {(() => {
                      const values = Object.values(wfaResults.parameter_stability) as number[];
                      const sum = values.reduce((acc: number, val: number) => acc + val, 0);
                      return (sum / values.length).toFixed(2);
                    })()}
                  </div>
                  <div className="text-sm text-gray-400">
                    Average stability score
                  </div>
                </div>

                <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
                  <div className="flex items-center gap-2 mb-2">
                    <BarChart3 size={20} className="text-accent-blue" />
                    <span className="text-sm text-gray-400">Total Windows</span>
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {wfaResults.total_windows}
                  </div>
                  <div className="text-sm text-gray-400">
                    IS: {wfaResults.in_sample_period_days}d, OOS: {wfaResults.out_of_sample_period_days}d
                  </div>
                </div>
              </div>

              {/* Recommendation Banner */}
              <div className={`rounded-lg p-6 border ${
                wfaResults.recommendation.confidence === 'HIGH' ? 'bg-profit-green/10 border-profit-green/30' :
                wfaResults.recommendation.confidence === 'MEDIUM' ? 'bg-yellow-500/10 border-yellow-500/30' :
                'bg-loss-red/10 border-loss-red/30'
              }`}>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {wfaResults.recommendation.recommendation === 'STRONG_BUY' ? '✅ Strong Buy Signal' :
                   wfaResults.recommendation.recommendation === 'BUY' ? '⚠️ Buy Signal' :
                   '🚫 Do Not Trade'}
                </h3>
                <p className="text-sm text-gray-300 mb-2">
                  Confidence: {wfaResults.recommendation.confidence}
                </p>
                <p className="text-sm text-gray-300">
                  {wfaResults.recommendation.message}
                </p>
              </div>

              {/* IS vs OOS Performance Chart */}
              <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                <h3 className="text-lg font-semibold text-white mb-4">In-Sample vs Out-of-Sample Performance</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={wfaResults.window_results.map((w: any) => ({
                    window: `W${w.window_number}`,
                    inSample: w.in_sample_metrics.total_return,
                    outOfSample: w.out_of_sample_metrics.total_return,
                    wfe: w.walk_forward_efficiency
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="window" stroke="#9CA3AF" fontSize={12} />
                    <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(value) => `${value.toFixed(0)}%`} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '0.5rem' }}
                      labelStyle={{ color: '#F3F4F6' }}
                      formatter={(value: any, name: any) => [`${value.toFixed(1)}%`, name === 'inSample' ? 'In-Sample Return' : 'Out-of-Sample Return']}
                    />
                    <Legend />
                    <Bar dataKey="inSample" fill="#3B82F6" name="In-Sample Return" />
                    <Bar dataKey="outOfSample" fill="#10B981" name="Out-of-Sample Return" />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 text-xs text-gray-400">
                  Blue bars show training period returns. Green bars show actual performance on unseen data.
                  When green bars are consistently shorter than blue, strategy may be overfit.
                </div>
              </div>

              {/* WFE Trend Chart */}
              <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                <h3 className="text-lg font-semibold text-white mb-4">Walk-Forward Efficiency Trend</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={wfaResults.window_results.map((w: any) => ({
                    window: `W${w.window_number}`,
                    wfe: w.walk_forward_efficiency
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="window" stroke="#9CA3AF" fontSize={12} />
                    <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '0.5rem' }}
                      labelStyle={{ color: '#F3F4F6' }}
                      formatter={(value: any) => [`${(value * 100).toFixed(1)}%`, 'WFE']}
                    />
                    <Line type="monotone" dataKey="wfe" stroke="#3B82F6" strokeWidth={3} dot={{ fill: '#3B82F6', r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
                
                {/* WFE Zones */}
                <div className="mt-4 flex gap-2 text-xs">
                  <div className="flex-1 bg-profit-green/20 border border-profit-green/30 rounded p-2 text-center text-profit-green">
                    Excellent (&gt;80%)
                  </div>
                  <div className="flex-1 bg-yellow-500/20 border border-yellow-500/30 rounded p-2 text-center text-yellow-500">
                    Acceptable (50-80%)
                  </div>
                  <div className="flex-1 bg-loss-red/20 border border-loss-red/30 rounded p-2 text-center text-loss-red">
                    Poor (&lt;50%)
                  </div>
                </div>
              </div>

              {/* Parameter Drift Table */}
              <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                <h3 className="text-lg font-semibold text-white mb-4">Parameter Evolution Across Windows</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-trading-border">
                        <th className="px-4 py-2 text-left text-gray-400">Window</th>
                        <th className="px-4 py-2 text-left text-gray-400">Period</th>
                        {Object.keys(wfaResults.window_results[0].optimal_params).map(param => (
                          <th key={param} className="px-4 py-2 text-left text-gray-400">{toTitleCase(param)}</th>
                        ))}
                        <th className="px-4 py-2 text-left text-gray-400">WFE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {wfaResults.window_results.map((window: any) => (
                        <tr key={window.window_number} className="border-b border-trading-border/50">
                          <td className="px-4 py-3 text-white font-medium">#{window.window_number}</td>
                          <td className="px-4 py-3 text-gray-400 text-xs">
                            {window.out_of_sample_period.split(' to ')[0]}
                          </td>
                          {(Object.entries(window.optimal_params) as [string, number][]).map(([param, value]) => (
                            <td key={param} className="px-4 py-3 text-white">
                              {value.toFixed(2)}
                            </td>
                          ))}
                          <td className={`px-4 py-3 font-medium ${
                            window.walk_forward_efficiency >= 0.8 ? 'text-profit-green' :
                            window.walk_forward_efficiency >= 0.5 ? 'text-yellow-500' :
                            'text-loss-red'
                          }`}>
                            {(window.walk_forward_efficiency * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Regime Analysis */}
              <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
                <h3 className="text-lg font-semibold text-white mb-4">Market Regime Analysis</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-semibold text-white mb-2">Returns Consistency</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Avg IS Return</span>
                        <span className="text-white font-medium">
                          {(wfaResults.regime_analysis.avg_is_return * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Avg OOS Return</span>
                        <span className="text-white font-medium">
                          {(wfaResults.regime_analysis.avg_oos_return * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">IS Volatility</span>
                        <span className="text-white font-medium">
                          {(wfaResults.regime_analysis.is_volatility * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">OOS Volatility</span>
                        <span className="text-white font-medium">
                          {(wfaResults.regime_analysis.oos_volatility * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-semibold text-white mb-2">Key Insights</h4>
                    <ul className="space-y-2 text-xs text-gray-400">
                      <li className="flex items-start gap-2">
                        <span className="text-accent-blue mt-1">•</span>
                        <span>
                          OOS returns are {(wfaResults.regime_analysis.avg_oos_return / wfaResults.regime_analysis.avg_is_return * 100).toFixed(0)}% of IS returns
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-accent-blue mt-1">•</span>
                        <span>
                          Parameter stability: {(() => {
                            const values = Object.values(wfaResults.parameter_stability) as number[];
                            const sum = values.reduce((acc: number, val: number) => acc + val, 0);
                            return (sum / values.length).toFixed(2);
                          })()}
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-accent-blue mt-1">•</span>
                        <span>
                          Strategy adapts {wfaResults.aggregate_metrics.windows_with_wfe_above_80 > wfaResults.total_windows / 2 ? 'well' : 'poorly'} to regime changes
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* Info Box */}
      {!results && !loading && (
        <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
          <h3 className="text-lg font-semibold text-white mb-4">How to Use This Dashboard</h3>
          <div className="space-y-3 text-sm text-gray-400">
            <p>
              <strong className="text-white">1. Configure Parameters:</strong> Define which strategy parameters to optimize (e.g., Supertrend Factor, Min Votes)
            </p>
            <p>
              <strong className="text-white">2. Run Grid Search:</strong> Backend tests all combinations in parallel using multiprocessing
            </p>
            <p>
              <strong className="text-white">3. Analyze Heatmap:</strong> Look for plateaus (large areas of good performance), not isolated peaks
            </p>
            <p>
              <strong className="text-white">4. Check Robust Zone:</strong> Use parameter ranges where top 20% performers cluster
            </p>
            <p>
              <strong className="text-white">5. Verify Overfitting:</strong> Ensure risk level is LOW (&lt;0.5) before live trading
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
