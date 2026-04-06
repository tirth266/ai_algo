import React, { useEffect, useState, useCallback } from 'react';
import { brokerService } from '../../services/api';
import { IndianRupee, RefreshCw, AlertTriangle, Wallet } from 'lucide-react';

interface MarginData {
  available_cash: number;
  available_margin: number;
  used_margin: number;
  net: number;
}

interface ProfileData {
  user_id: string;
  user_name: string;
  email: string;
  broker: string;
  equity: MarginData;
  commodity: MarginData;
  timestamp: string;
}

export const BalanceWidget: React.FC = () => {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchProfile = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true);
      const response = await brokerService.getProfile();
      if (response?.data) {
        setProfile(response.data);
        setError(null);
      }
    } catch (err: any) {
      const msg =
        err.response?.data?.message ||
        'Unable to fetch balance. Please re-login.';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const formatINR = (value: number) =>
    `₹${value.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  if (loading) {
    return (
      <div className="bg-trading-card rounded-lg p-6 border border-trading-border animate-pulse">
        <div className="h-6 bg-trading-border rounded w-40 mb-4" />
        <div className="h-10 bg-trading-border rounded w-56" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-trading-card rounded-lg p-6 border border-loss-red/30">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-loss-red">
            <AlertTriangle size={20} />
            <span className="font-semibold text-sm">Balance Unavailable</span>
          </div>
          <button
            onClick={() => fetchProfile(true)}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded"
            title="Retry"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
        <p className="text-sm text-gray-400">{error}</p>
      </div>
    );
  }

  const equity = profile?.equity;
  const totalEquity = equity?.net || 0;
  const availableCash = equity?.available_cash || 0;
  const usedMargin = equity?.used_margin || 0;

  return (
    <div className="bg-trading-card rounded-lg p-6 border border-trading-border hover:border-accent-blue/40 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-accent-blue/10">
            <Wallet size={20} className="text-accent-blue" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Account Balance</h3>
            {profile?.user_id && (
              <span className="text-xs text-gray-500">{profile.user_id}</span>
            )}
          </div>
        </div>
        <button
          onClick={() => fetchProfile(true)}
          disabled={refreshing}
          className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/5"
          title="Refresh balance"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Main Balance */}
      <div className="mb-5">
        <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Total Equity</p>
        <p className="text-3xl font-bold text-white tracking-tight">
          {formatINR(totalEquity)}
        </p>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-trading-dark/50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <IndianRupee size={14} className="text-profit-green" />
            <span className="text-xs text-gray-400">Available Cash</span>
          </div>
          <p className="text-sm font-semibold text-profit-green">
            {formatINR(availableCash)}
          </p>
        </div>
        <div className="bg-trading-dark/50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <IndianRupee size={14} className="text-orange-400" />
            <span className="text-xs text-gray-400">Used Margin</span>
          </div>
          <p className="text-sm font-semibold text-orange-400">
            {formatINR(usedMargin)}
          </p>
        </div>
      </div>

      {/* Commodity (if applicable) */}
      {profile?.commodity && profile.commodity.net > 0 && (
        <div className="mt-4 pt-4 border-t border-trading-border">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            Commodity Segment
          </p>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-400">Net</span>
            <span className="text-sm font-medium text-white">
              {formatINR(profile.commodity.net)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
