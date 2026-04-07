import React, { useState, useEffect } from 'react';
import apiClient from '../services/api';
import { AlertTriangle, Power, Play, RefreshCw, Activity, TrendingUp, Shield } from 'lucide-react';

export const LiveTradingPanel: React.FC = () => {
  // Trading state
  const [paperTrading, setPaperTrading] = useState(true);
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [tradingStatus, setTradingStatus] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [showKillSwitchConfirm, setShowKillSwitchConfirm] = useState(false);
  
  // Full workflow state
  const [workflowRunning, setWorkflowRunning] = useState(false);
  const [workflowStatus, setWorkflowStatus] = useState<string>('Idle');
  const [workflowResults, setWorkflowResults] = useState<any | null>(null);

  // Load trading status on mount
  useEffect(() => {
    loadTradingStatus();
    const interval = setInterval(loadTradingStatus, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadTradingStatus = async () => {
    try {
      const response = await apiClient.get('/trading/status');
      setTradingStatus(response.data);
      setKillSwitchActive(response.data.kill_switch_active);
      setPaperTrading(response.data.paper_trading);
    } catch (error) {
      console.error('Failed to load trading status:', error);
    }
  };

  const triggerKillSwitch = async (reason: string) => {
    try {
      setLoading(true);
      
      await apiClient.post('/trading/kill-switch', {
        reason: reason,
        message: `Kill-switch triggered from UI - ${reason}`
      });
      
      // Reload status
      await loadTradingStatus();
      setShowKillSwitchConfirm(false);
      
    } catch (error: any) {
      console.error('Kill-switch failed:', error);
      alert('Kill-switch execution failed: ' + (error.response?.data?.error || error.message));
    } finally {
      setLoading(false);
    }
  };

  const resetKillSwitch = async () => {
    try {
      const response = await apiClient.post('/trading/reset-kill-switch');
      
      if (response.data.success) {
        await loadTradingStatus();
        alert('Kill-switch reset successfully. Trading resumed.');
      } else {
        alert('Failed to reset kill-switch');
      }
    } catch (error: any) {
      console.error('Reset failed:', error);
      alert('Kill-switch reset failed: ' + (error.response?.data?.error || error.message));
    }
  };

  const startFullWorkflow = async () => {
    setWorkflowRunning(true);
    setWorkflowStatus('🔄 Optimizing Parameters...');
    
    try {
      // Step 1: Run full validation pipeline
      const response = await apiClient.post('/trading/start-full-workflow', {
        symbol: 'RELIANCE',
        param_grid: {
          supertrend_factor: [2.0, 3.0, 4.0],
          min_votes: [3, 4]
        },
        timeframe: '5minute',
        days: 90
      });

      if (response.data.success) {
        const results = response.data.results;
        
        // Update status based on progress
        setWorkflowStatus(`✅ ${results.message}`);
        setWorkflowResults(results);
        
        // Refresh trading status
        await loadTradingStatus();
        
        alert(`Strategy Activated!\n\nBest Params: ${JSON.stringify(results.best_params)}\nRisk of Ruin: ${(results.risk_profile.risk_of_ruin * 100).toFixed(2)}%\nWFE: ${(results.walk_forward.avg_wfe * 100).toFixed(1)}%\nPosition Size: ${results.risk_profile.position_size_pct}%`);
      }
    } catch (error: any) {
      console.error('Workflow failed:', error);
      setWorkflowStatus('❌ Workflow Failed');
      
      const errorMsg = error.response?.data?.message || error.message;
      alert(`Workflow Failed: ${errorMsg}`);
    } finally {
      setWorkflowRunning(false);
    }
  };

  const quickStartWorkflow = async () => {
    setWorkflowRunning(true);
    setWorkflowStatus('🚀 Quick Starting Strategy...');
    
    try {
      const response = await apiClient.post('/trading/quick-start', {
        symbol: 'NIFTY50',
        supertrend_factor: 3.0,
        min_votes: 3
      });

      if (response.data.success) {
        const results = response.data.results;
        setWorkflowStatus(`✅ ${results.message}`);
        setWorkflowResults(results);
        await loadTradingStatus();
        alert(`Quick Start Successful!\n\n${results.message}`);
      }
    } catch (error: any) {
      console.error('Quick start failed:', error);
      setWorkflowStatus('❌ Quick Start Failed');
      alert(`Quick Start Failed: ${error.response?.data?.message || error.message}`);
    } finally {
      setWorkflowRunning(false);
    }
  };

  const getStatusColor = () => {
    if (killSwitchActive) return 'bg-loss-red';
    if (!tradingStatus) return 'bg-gray-500';
    
    const winRate = tradingStatus.win_rate_today || 0;
    if (winRate >= 60) return 'bg-profit-green';
    if (winRate >= 40) return 'bg-yellow-500';
    return 'bg-loss-red';
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity size={28} className="text-accent-blue" />
            Live Trading Supervisor
          </h1>
          <p className="text-gray-400 mt-1">
            Monitor and control live trading operations
          </p>
        </div>
        
        {/* Mode Indicator */}
        <div className={`px-4 py-2 rounded-lg font-medium ${
          paperTrading ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                       : 'bg-profit-green/20 text-profit-green border border-profit-green/30'
        }`}>
          {paperTrading ? '📄 PAPER TRADING' : '💰 LIVE TRADING'}
        </div>
      </div>

      {/* Emergency Kill-Switch */}
      <div className={`rounded-lg p-6 border-2 ${
        killSwitchActive 
          ? 'bg-loss-red/10 border-loss-red' 
          : 'bg-trading-card border-trading-border'
      }`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Shield size={32} className={killSwitchActive ? 'text-loss-red' : 'text-gray-400'} />
            <div>
              <h3 className="text-lg font-semibold text-white">
                Emergency Kill-Switch
              </h3>
              <p className="text-sm text-gray-400">
                {killSwitchActive 
                  ? 'ACTIVE - All positions closed' 
                  : 'READY - Instantly close all positions'}
              </p>
            </div>
          </div>
          
          {!killSwitchActive && (
            <button
              onClick={() => setShowKillSwitchConfirm(true)}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-3 bg-loss-red hover:bg-red-700 text-white rounded-lg font-bold transition-colors disabled:opacity-50 animate-pulse"
            >
              <Power size={20} />
              EMERGENCY STOP
            </button>
          )}
        </div>

        {killSwitchActive && (
          <div className="mt-4 p-4 bg-loss-red/20 border border-loss-red rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle size={24} className="text-loss-red" />
                <span className="text-loss-red font-bold">
                  KILL-SWITCH ACTIVE
                </span>
              </div>
              
              <button
                onClick={resetKillSwitch}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-white text-loss-red rounded-lg font-medium hover:bg-gray-100 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                Reset & Resume Trading
              </button>
            </div>
            
            {tradingStatus?.last_kill_switch_trigger && (
              <p className="text-xs text-gray-400 mt-2">
                Last triggered: {new Date(tradingStatus.last_kill_switch_trigger).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Kill-Switch Confirmation Modal */}
      {showKillSwitchConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-trading-card rounded-lg p-6 max-w-md border-2 border-loss-red">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle size={32} className="text-loss-red" />
              <h2 className="text-xl font-bold text-white">CONFIRM EMERGENCY STOP</h2>
            </div>
            
            <p className="text-gray-300 mb-6">
              This will IMMEDIATELY close all open positions and cancel all pending orders. 
              This action cannot be undone.
            </p>
            
            <div className="space-y-3 mb-6">
              <button
                onClick={() => triggerKillSwitch('manual')}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-loss-red hover:bg-red-700 text-white rounded-lg font-bold transition-colors"
              >
                <Power size={20} />
                YES - CLOSE ALL POSITIONS NOW
              </button>
              
              <button
                onClick={() => setShowKillSwitchConfirm(false)}
                className="w-full px-4 py-2 bg-trading-dark text-gray-400 rounded-lg hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
            
            <div className="text-xs text-gray-500 text-center">
              Reason will be logged as: MANUAL
            </div>
          </div>
        </div>
      )}

      {/* Trading Status Cards */}
      {tradingStatus && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp size={20} className="text-accent-blue" />
              <span className="text-sm text-gray-400">Daily P&L</span>
            </div>
            <div className={`text-2xl font-bold ${
              tradingStatus.daily_pnl >= 0 ? 'text-profit-green' : 'text-loss-red'
            }`}>
              ₹{tradingStatus.daily_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
            <div className="text-sm text-gray-400">
              Realized: ₹{tradingStatus.realized_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
          </div>

          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={20} className="text-profit-green" />
              <span className="text-sm text-gray-400">Win Rate</span>
            </div>
            <div className="text-2xl font-bold text-white">
              {tradingStatus.win_rate_today.toFixed(1)}%
            </div>
            <div className="text-sm text-gray-400">
              {tradingStatus.total_trades_today} trades today
            </div>
          </div>

          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="flex items-center gap-2 mb-2">
              <Shield size={20} className="text-yellow-500" />
              <span className="text-sm text-gray-400">Slippage</span>
            </div>
            <div className="text-2xl font-bold text-white">
              {tradingStatus.avg_slippage_bps.toFixed(1)} bps
            </div>
            <div className="text-sm text-gray-400">
              Average fill variance
            </div>
          </div>

          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="flex items-center gap-2 mb-2">
              <Power size={20} className={getStatusColor()} />
              <span className="text-sm text-gray-400">Status</span>
            </div>
            <div className={`text-lg font-bold ${getStatusColor()}`}>
              {killSwitchActive ? 'STOPPED' : 
               tradingStatus.active_strategies > 0 ? 'RUNNING' : 'IDLE'}
            </div>
            <div className="text-sm text-gray-400">
              {tradingStatus.open_positions} positions, {tradingStatus.pending_orders} orders
            </div>
          </div>
        </div>
      )}

      {/* Info Box */}
      {!tradingStatus && (
        <div className="bg-trading-card rounded-lg p-6 border border-trading-border text-center">
          <Activity size={48} className="mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-semibold text-white mb-2">Loading Trading Status...</h3>
          <p className="text-gray-400">Connecting to live execution engine</p>
        </div>
      )}

      {/* Full Workflow Control Panel */}
      <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
        <div className="flex items-center gap-3 mb-4">
          <Activity size={24} className="text-accent-blue" />
          <h3 className="text-lg font-semibold text-white">Strategy Control Center</h3>
        </div>
        
        <p className="text-sm text-gray-400 mb-4">
          Click to run the complete validation pipeline: Parameter Optimization → Monte Carlo → Walk-Forward → Paper Trading
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* FULL WORKFLOW BUTTON */}
          <button
            onClick={startFullWorkflow}
            disabled={workflowRunning}
            className={`px-6 py-4 rounded-lg font-bold transition-all ${
              workflowRunning 
                ? 'bg-gray-600 cursor-not-allowed opacity-50'
                : 'bg-blue-600 hover:bg-blue-500 active:scale-95'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              {workflowRunning ? (
                <>
                  <RefreshCw size={20} className="animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play size={20} />
                  Validate & Start Trading
                </>
              )}
            </div>
            <div className="text-xs mt-1 opacity-80">
              Full Pipeline (~10-20 min)
            </div>
          </button>

          {/* QUICK START BUTTON */}
          <button
            onClick={quickStartWorkflow}
            disabled={workflowRunning}
            className={`px-6 py-4 rounded-lg font-bold transition-all ${
              workflowRunning 
                ? 'bg-gray-600 cursor-not-allowed opacity-50'
                : 'bg-green-600 hover:bg-green-500 active:scale-95'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              {workflowRunning ? (
                <>
                  <RefreshCw size={20} className="animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play size={20} />
                  Quick Start (Pre-validated)
                </>
              )}
            </div>
            <div className="text-xs mt-1 opacity-80">
              Instant Start (~1-2 min)
            </div>
          </button>
        </div>

        {/* Workflow Status Display */}
        {(workflowRunning || workflowResults) && (
          <div className="bg-trading-dark rounded-lg p-4 border border-trading-border">
            <div className="flex items-center gap-2 mb-2">
              {workflowRunning ? (
                <RefreshCw size={18} className="animate-spin text-blue-400" />
              ) : workflowResults?.status === 'Active' ? (
                <Shield size={18} className="text-profit-green" />
              ) : (
                <AlertTriangle size={18} className="text-loss-red" />
              )}
              <span className={`font-semibold ${
                workflowRunning ? 'text-blue-400' : 
                workflowResults?.status === 'Active' ? 'text-profit-green' : 'text-loss-red'
              }`}>
                {workflowStatus}
              </span>
            </div>
            
            {workflowResults && workflowResults.status === 'Active' && (
              <div className="grid grid-cols-3 gap-2 mt-3 text-xs">
                <div className="bg-trading-card rounded p-2">
                  <div className="text-gray-400">Best Params</div>
                  <div className="text-white font-medium">
                    Factor: {workflowResults.best_params.supertrend_factor}, 
                    Votes: {workflowResults.best_params.min_votes}
                  </div>
                </div>
                <div className="bg-trading-card rounded p-2">
                  <div className="text-gray-400">Risk of Ruin</div>
                  <div className="text-white font-medium">
                    {(workflowResults.risk_profile.risk_of_ruin * 100).toFixed(2)}%
                  </div>
                </div>
                <div className="bg-trading-card rounded p-2">
                  <div className="text-gray-400">WFE</div>
                  <div className="text-white font-medium">
                    {(workflowResults.walk_forward.avg_wfe * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
        <h3 className="text-lg font-semibold text-white mb-4">Quick Actions</h3>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button
            onClick={() => setPaperTrading(!paperTrading)}
            className={`px-4 py-3 rounded-lg font-medium transition-colors ${
              paperTrading 
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30'
                : 'bg-trading-dark text-gray-400 border border-trading-border hover:text-white'
            }`}
          >
            {paperTrading ? '✓ Paper Mode Active' : 'Enable Paper Mode'}
          </button>
          
          <button
            onClick={loadTradingStatus}
            className="flex items-center justify-center gap-2 px-4 py-3 bg-trading-dark text-gray-400 rounded-lg hover:text-white transition-colors"
          >
            <RefreshCw size={18} />
            Refresh Status
          </button>
          
          <button
            onClick={() => window.location.href = '/backtest-dashboard'}
            className="px-4 py-3 bg-trading-dark text-gray-400 rounded-lg hover:text-white transition-colors"
          >
            View Backtests
          </button>
          
          <button
            onClick={() => window.open('https://ai-algo-66d6.onrender.com/logs', '_blank')}
            className="px-4 py-3 bg-trading-dark text-gray-400 rounded-lg hover:text-white transition-colors"
          >
            View Logs
          </button>
        </div>
      </div>

      {/* Slippage Warning */}
      {tradingStatus && tradingStatus.avg_slippage_bps > 5 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={20} className="text-yellow-500" />
            <h3 className="text-sm font-semibold text-yellow-500">High Slippage Detected</h3>
          </div>
          <p className="text-sm text-gray-300">
            Average slippage is {tradingStatus.avg_slippage_bps.toFixed(1)} bps, which is above the normal range (2-3 bps). 
            This may indicate latency issues or low liquidity.
          </p>
        </div>
      )}
    </div>
  );
};
