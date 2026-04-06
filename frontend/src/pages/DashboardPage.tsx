import React, { useEffect, useState } from 'react';
import { dashboardService } from '../services/api';
import type { DashboardData } from '../types';
import { IndianRupee, TrendingUp, Briefcase, Activity, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { BalanceWidget } from '../components/dashboard/BalanceWidget';

export const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchDashboardData = async () => {
    try {
      const responseData = await dashboardService.getDashboardData();
      if (responseData) {
        setData(responseData);
        setLastUpdated(new Date());
        setError(null);
      } else {
        setError('No data received');
      }
    } catch (err: any) {
      console.error('Dashboard error:', err);
      if (!data) {
        setError(err.response?.data?.message || 'Failed to load dashboard data');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
          <RefreshCw className="animate-spin" size={24} />
          Loading dashboard...
        </div>
      </div>
    );
  }

  const isConnected = data?.broker_status === 'connected';
  const todayPnl = data?.today_pnl || 0;

  const stats = [
    {
      label: 'Account Balance',
      value: `₹${(data?.account_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
      icon: IndianRupee,
      color: 'var(--accent-primary)',
    },
    {
      label: 'Available Margin',
      value: `₹${(data?.available_margin || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
      icon: TrendingUp,
      color: 'var(--accent-success)',
    },
    {
      label: 'Used Margin',
      value: `₹${(data?.used_margin || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
      icon: Briefcase,
      color: '#f97316',
    },
    {
      label: "Today's P&L",
      value: `₹${todayPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
      icon: Activity,
      color: todayPnl >= 0 ? 'var(--accent-success)' : 'var(--accent-danger)',
    },
  ];

  return (
    <div className="p-6 space-y-6" style={{ backgroundColor: 'var(--bg-primary)', minHeight: '100%' }}>
      {/* Page Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Dashboard</h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>Real-time trading overview</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <div 
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm"
            style={{ 
              backgroundColor: isConnected ? 'rgba(0, 255, 156, 0.15)' : 'rgba(255, 77, 79, 0.15)',
              color: isConnected ? 'var(--accent-success)' : 'var(--accent-danger)',
              border: `1px solid ${isConnected ? 'var(--accent-success)' : 'var(--accent-danger)'}`
            }}
          >
            {isConnected ? <Wifi size={16} /> : <WifiOff size={16} />}
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
          
          {/* Last Updated */}
          {lastUpdated && (
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Updated: {lastUpdated.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {/* Connection Error Banner */}
      {!isConnected && (
        <div 
          className="p-4 rounded-lg"
          style={{ 
            backgroundColor: 'rgba(255, 77, 79, 0.15)',
            border: '1px solid var(--accent-danger)'
          }}
        >
          <div className="flex items-center gap-2" style={{ color: 'var(--accent-danger)' }}>
            <WifiOff size={20} />
            <span className="font-medium">Zerodha Disconnected</span>
          </div>
          <p className="text-sm mt-1" style={{ color: 'rgba(255, 77, 79, 0.8)' }}>
            Please connect your broker account from the Broker page
          </p>
        </div>
      )}
      
      {error && (
        <div 
          className="p-4 rounded-lg"
          style={{ 
            backgroundColor: 'rgba(255, 77, 79, 0.15)',
            border: '1px solid var(--accent-danger)',
            color: 'var(--accent-danger)'
          }}
        >
          {error}
        </div>
      )}

      {/* Balance Widget */}
      <BalanceWidget />

      {/* Stats Grid - Staggered Animation */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 stagger-children">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="glass-card card-micro rounded-xl p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <stat.icon style={{ color: stat.color }} size={24} />
              <span 
                className="text-xs px-2 py-1 rounded-full"
                style={{ 
                  backgroundColor: `${stat.color}20`,
                  color: stat.color 
                }}
              >
                Live
              </span>
            </div>
            <div 
              className="text-2xl font-bold mb-1"
              style={{ color: 'var(--text-primary)' }}
            >
              {stat.value}
            </div>
            <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Account Summary Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account Details */}
        <div 
          className="rounded-lg p-6"
          style={{ 
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-default)'
          }}
        >
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Account Details</h3>
          <div className="space-y-3">
            {data?.user_id && (
              <div 
                className="flex justify-between items-center pb-2"
                style={{ borderBottom: '1px solid var(--border-default)' }}
              >
                <span style={{ color: 'var(--text-secondary)' }}>User ID</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data.user_id}</span>
              </div>
            )}
            {data?.user_name && (
              <div 
                className="flex justify-between items-center pb-2"
                style={{ borderBottom: '1px solid var(--border-default)' }}
              >
                <span style={{ color: 'var(--text-secondary)' }}>Account Name</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data.user_name}</span>
              </div>
            )}
            <div 
              className="flex justify-between items-center pb-2"
              style={{ borderBottom: '1px solid var(--border-default)' }}
            >
              <span style={{ color: 'var(--text-secondary)' }}>Total Orders Today</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data?.total_orders || 0}</span>
            </div>
            <div 
              className="flex justify-between items-center pb-2"
              style={{ borderBottom: '1px solid var(--border-default)' }}
            >
              <span style={{ color: 'var(--text-secondary)' }}>Open Positions</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data?.open_positions || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span style={{ color: 'var(--text-secondary)' }}>Holdings Count</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{data?.holdings_count || 0}</span>
            </div>
          </div>
        </div>

        {/* Market Status */}
        <div 
          className="rounded-lg p-6"
          style={{ 
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-default)'
          }}
        >
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Market Status</h3>
          <div className="space-y-3">
            {['NSE', 'BSE', 'MCX'].map((market) => (
              <div key={market} className="flex justify-between items-center">
                <span style={{ color: 'var(--text-secondary)' }}>{market}</span>
                <span 
                  className="font-medium flex items-center gap-2"
                  style={{ color: 'var(--accent-success)' }}
                >
                  <span 
                    className="w-2 h-2 rounded-full animate-pulse"
                    style={{ 
                      backgroundColor: 'var(--accent-success)',
                      boxShadow: '0 0 8px var(--glow-success)'
                    }}
                  ></span>
                  Open
                </span>
              </div>
            ))}
            <div className="pt-3 mt-3" style={{ borderTop: '1px solid var(--border-default)' }}>
              <div className="flex justify-between items-center">
                <span style={{ color: 'var(--text-secondary)' }}>Margin Utilization</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                  {data?.account_balance && data.account_balance > 0 
                    ? Math.round(((data.used_margin || 0) / data.account_balance) * 100) 
                    : 0}%
                </span>
              </div>
              <div 
                className="w-full h-2 mt-2 rounded-full"
                style={{ backgroundColor: 'var(--border-default)' }}
              >
                <div 
                  className="h-2 rounded-full transition-all duration-500"
                  style={{ 
                    width: `${data?.account_balance && data.account_balance > 0 
                      ? Math.min(((data.used_margin || 0) / data.account_balance) * 100, 100) 
                      : 0}%`,
                    backgroundColor: 'var(--accent-primary)'
                  }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chart Placeholder */}
      <div 
        className="rounded-lg p-6"
        style={{ 
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-default)'
        }}
      >
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Market Overview</h3>
        <div 
          className="h-64 flex items-center justify-center rounded border border-dashed"
          style={{ 
            backgroundColor: 'var(--bg-secondary)',
            borderColor: 'var(--border-subtle)'
          }}
        >
          <div className="text-center" style={{ color: 'var(--text-muted)' }}>
            <Activity size={48} className="mx-auto mb-2 opacity-50" />
            <p>TradingView chart integration coming soon</p>
            <p className="text-sm mt-1">Real-time charts will be added in future updates</p>
          </div>
        </div>
      </div>
    </div>
  );
};