import React, { useEffect, useState } from 'react';
import { strategyService } from '../services/api';
import type { Strategy, RegisterStrategyRequest } from '../types';
import { Play, Square, RefreshCw, Plus, Trash2, X, Zap } from 'lucide-react';

export const StrategiesPage: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Auto-refresh interval
  const REFRESH_INTERVAL = 15000; // 15 seconds
  
  // Form state for registering new strategy
  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [newStrategy, setNewStrategy] = useState<RegisterStrategyRequest>({
    name: '',
    symbol: '',
    timeframe: '5minute',
  });
  const [registering, setRegistering] = useState(false);

  const fetchStrategies = async () => {
    try {
      setLoading(true);
      const data = await strategyService.list();
      setStrategies(data);
      setError(null);
    } catch (err) {
      setError('Failed to load strategies');
      console.error('Strategies error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStrategies();
    
    // Auto-refresh every 15 seconds
    const intervalId = setInterval(fetchStrategies, REFRESH_INTERVAL);
    
    return () => clearInterval(intervalId);
  }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegistering(true);
    
    try {
      await strategyService.register(newStrategy);
      
      // Reset form and close
      setNewStrategy({
        name: '',
        symbol: '',
        timeframe: '5minute',
      });
      setShowRegisterForm(false);
      
      // Refresh list
      fetchStrategies();
    } catch (err: any) {
      alert(`Failed to register strategy: ${err.response?.data?.error || 'Unknown error'}`);
    } finally {
      setRegistering(false);
    }
  };

  const handleStart = async (strategyId: string) => {
    try {
      const strategy = strategies.find(s => s.strategy_id === strategyId);
      
      if (!strategy) {
        alert('Error: Strategy not found. Please refresh the page.');
        return;
      }
      
      if (!strategy.symbol) {
        alert('Error: Strategy missing symbol configuration. Cannot start without trading symbol.');
        return;
      }
      
      await strategyService.start(
        strategyId,
        strategy.symbol,
        strategy.timeframe
      );
      
      fetchStrategies();
    } catch (err: any) {
      const errorMsg = err.response?.data?.message || err.response?.data?.error || 'Failed to start strategy';
      console.error('START ERROR:', err);
      alert(`Failed to start strategy: ${errorMsg}`);
    }
  };

  const handleStop = async (strategyId: string) => {
    try {
      await strategyService.stop(strategyId);
      fetchStrategies();
    } catch (err) {
      alert('Failed to stop strategy');
    }
  };

  const handleDelete = async (strategyId: string) => {
    if (!confirm(`Delete strategy "${strategyId}"? This cannot be undone.`)) {
      return;
    }
    
    try {
      await strategyService.unregister(strategyId);
      fetchStrategies();
    } catch (err) {
      alert('Failed to delete strategy');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-profit-green bg-profit-green/10 border-profit-green';
      case 'registered':
        return 'text-accent-blue bg-accent-blue/10 border-accent-blue';
      case 'stopped':
        return 'text-gray-400 bg-gray-500/10 border-gray-500';
      default:
        return 'text-gray-400';
    }
  };

  if (loading && strategies.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400 flex items-center gap-2">
          <RefreshCw className="animate-spin" size={20} />
          Loading strategies...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Strategies</h1>
          <p className="text-gray-400 mt-1">
            Manage automated trading strategies
            <span className="ml-2 text-xs text-gray-500">• Manual registration required</span>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchStrategies}
            className="flex items-center gap-2 px-4 py-2 bg-trading-card border border-trading-border rounded hover:bg-trading-border transition-colors text-gray-300"
          >
            <RefreshCw size={18} />
            Refresh
          </button>
          <button
            onClick={() => setShowRegisterForm(!showRegisterForm)}
            className="flex items-center gap-2 px-4 py-2 bg-accent-blue/20 border border-accent-blue text-accent-blue rounded hover:bg-accent-blue/30 transition-colors"
          >
            <Plus size={18} />
            Register Strategy
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-loss-red/10 border border-loss-red text-loss-red p-4 rounded-lg">
          {error}
        </div>
      )}
      {/* Registration Form */}
      {showRegisterForm && (
        <div className="bg-trading-card rounded-lg p-6 border border-accent-blue/30">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Register New Strategy</h3>
            <button
              onClick={() => setShowRegisterForm(false)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <X size={20} />
            </button>
          </div>
          <form onSubmit={handleRegister} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Strategy Name</label>
              <input
                type="text"
                value={newStrategy.name}
                onChange={(e) => setNewStrategy({ ...newStrategy, name: e.target.value })}
                placeholder="e.g. Combined Power Strategy"
                className="w-full px-3 py-2 bg-trading-dark border border-trading-border rounded text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Symbol</label>
              <input
                type="text"
                value={newStrategy.symbol}
                onChange={(e) => setNewStrategy({ ...newStrategy, symbol: e.target.value.toUpperCase() })}
                placeholder="e.g. NIFTY50"
                className="w-full px-3 py-2 bg-trading-dark border border-trading-border rounded text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Timeframe</label>
              <select
                value={newStrategy.timeframe}
                onChange={(e) => setNewStrategy({ ...newStrategy, timeframe: e.target.value })}
                className="w-full px-3 py-2 bg-trading-dark border border-trading-border rounded text-white focus:outline-none focus:border-accent-blue"
              >
                <option value="minute">1 minute</option>
                <option value="3minute">3 minutes</option>
                <option value="5minute">5 minutes</option>
                <option value="15minute">15 minutes</option>
                <option value="30minute">30 minutes</option>
                <option value="60minute">1 hour</option>
                <option value="day">Daily</option>
              </select>
            </div>
            <div className="md:col-span-3 flex gap-3 mt-2">
              <button
                type="submit"
                disabled={registering}
                className="flex items-center gap-2 px-6 py-2 bg-accent-blue text-white rounded hover:bg-accent-blue/80 transition-colors disabled:opacity-50"
              >
                {registering ? <RefreshCw size={16} className="animate-spin" /> : <Plus size={16} />}
                {registering ? 'Registering...' : 'Register'}
              </button>
              <button
                type="button"
                onClick={() => setShowRegisterForm(false)}
                className="px-6 py-2 bg-trading-dark hover:bg-trading-border text-gray-400 rounded transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Strategies Table */}
      <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-trading-dark border-b border-trading-border">
            <tr>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Strategy ID</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Name</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Symbol</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Timeframe</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Status</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {strategies.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-16 text-center">
                  <div className="flex flex-col items-center">
                    <Zap size={48} className="text-gray-600 mb-4" />
                    <div className="text-lg text-gray-400 mb-2">No Strategies Registered</div>
                    <div className="text-sm text-gray-500 mb-6 max-w-md">
                      Register a strategy to begin trading. You define the Symbol and Timeframe
                      at the moment of registration for maximum control.
                    </div>
                    <button
                      onClick={() => setShowRegisterForm(true)}
                      className="flex items-center gap-2 px-6 py-2.5 bg-accent-blue/20 border border-accent-blue text-accent-blue rounded-lg hover:bg-accent-blue/30 transition-colors"
                    >
                      <Plus size={18} />
                      Register New Strategy
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              strategies.map((strategy) => (
                <tr key={strategy.strategy_id} className="border-b border-trading-border hover:bg-trading-border/50">
                  <td className="px-6 py-4 text-white font-mono text-sm">
                    {strategy.strategy_id}
                  </td>
                  <td className="px-6 py-4 text-white font-medium">
                    {strategy.name}
                  </td>
                  <td className="px-6 py-4 text-gray-400">{strategy.symbol}</td>
                  <td className="px-6 py-4 text-gray-400">{strategy.timeframe}</td>
                  <td className="px-6 py-4">
                    <span className={`px-3 py-1 rounded text-xs font-medium border ${getStatusColor(strategy.status)}`}>
                      {strategy.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {strategy.status === 'running' ? (
                        <button
                          onClick={() => handleStop(strategy.strategy_id)}
                          className="p-2 bg-loss-red/10 hover:bg-loss-red/20 text-loss-red rounded transition-colors"
                          title="Stop Strategy"
                        >
                          <Square size={16} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleStart(strategy.strategy_id)}
                          className="p-2 bg-profit-green/10 hover:bg-profit-green/20 text-profit-green rounded transition-colors"
                          title="Start Strategy"
                        >
                          <Play size={16} />
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(strategy.strategy_id)}
                        className="p-2 bg-trading-dark hover:bg-loss-red/10 text-gray-400 hover:text-loss-red rounded transition-colors"
                        title="Delete Strategy"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Statistics */}
      {strategies.length > 0 && (
        <div className="grid grid-cols-4 gap-6">
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Total Strategies</div>
            <div className="text-2xl font-bold text-white">{strategies.length}</div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Running</div>
            <div className="text-2xl font-bold text-profit-green">
              {strategies.filter(s => s.status === 'running').length}
            </div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Registered</div>
            <div className="text-2xl font-bold text-accent-blue">
              {strategies.filter(s => s.status === 'registered').length}
            </div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Stopped</div>
            <div className="text-2xl font-bold text-gray-400">
              {strategies.filter(s => s.status === 'stopped').length}
            </div>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
        <h3 className="text-lg font-semibold text-white mb-4">How It Works</h3>
        <div className="space-y-3 text-sm text-gray-400">
          <p>
            <strong className="text-white">1. Register:</strong> Click "Register Strategy" to add a strategy with your chosen Symbol and Timeframe
          </p>
          <p>
            <strong className="text-white">2. Start:</strong> Click the play button to activate a strategy and begin monitoring market data
          </p>
          <p>
            <strong className="text-white">3. Execute:</strong> The execution loop runs every 60 seconds, checking for signals
          </p>
          <p>
            <strong className="text-white">4. Monitor:</strong> Watch strategy status and performance in real-time
          </p>
          <div className="bg-orange-500/10 border border-orange-500/30 rounded p-3 mt-4">
            <p className="text-orange-400 font-medium text-xs">
              ⚠️ No strategies auto-load. You must explicitly register before trading.
              This is a safety feature for Live Production.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
