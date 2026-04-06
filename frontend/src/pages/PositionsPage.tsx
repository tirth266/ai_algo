import React, { useEffect, useState } from 'react';
import { positionService } from '../services/api';
import type { Position } from '../types';
import { RefreshCw } from 'lucide-react';

export const PositionsPage: React.FC = () => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPositions = async () => {
    try {
      setLoading(true);
      const data = await positionService.getPositions();
      setPositions(data);
      setError(null);
    } catch (err) {
      setError('Failed to load positions');
      console.error('Positions error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
  }, []);

  const handleRefresh = () => {
    fetchPositions();
  };

  if (loading && positions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Positions</h1>
          <p className="text-gray-400 mt-1">Your open positions</p>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 px-4 py-2 bg-trading-card border border-trading-border rounded hover:bg-trading-border transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-loss-red/10 border border-loss-red text-loss-red p-4 rounded-lg">
          {error}
        </div>
      )}
      {/* Positions Table */}
      <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-trading-dark border-b border-trading-border">
            <tr>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Symbol</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Type</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">Quantity</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">Avg Price</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">LTP</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">P&L</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((position, index) => (
                <tr key={index} className="border-b border-trading-border hover:bg-trading-border/50">
                  <td className="px-6 py-4 text-white font-medium">{position.symbol}</td>
                  <td className="px-6 py-4 text-gray-400">{position.product}</td>
                  <td className="px-6 py-4 text-right text-white">{position.quantity}</td>
                  <td className="px-6 py-4 text-right text-white">₹{position.average_price.toFixed(2)}</td>
                  <td className="px-6 py-4 text-right text-white">₹{position.ltp.toFixed(2)}</td>
                  <td className={`px-6 py-4 text-right font-medium ${position.pnl >= 0 ? 'text-profit-green' : 'text-loss-red'}`}>
                    {position.pnl >= 0 ? '+' : ''}₹{position.pnl.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => positionService.squareOff(position.symbol)}
                      className="px-3 py-1 bg-loss-red text-white text-sm rounded hover:bg-red-700 transition-colors"
                    >
                      Square Off
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      {positions.length > 0 && (
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Total Positions</div>
            <div className="text-2xl font-bold text-white">{positions.length}</div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Total P&L</div>
            <div className={`text-2xl font-bold ${positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? 'text-profit-green' : 'text-loss-red'}`}>
              {positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? '+' : ''}
              ₹{positions.reduce((sum, p) => sum + p.pnl, 0).toFixed(2)}
            </div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Invested Value</div>
            <div className="text-2xl font-bold text-white">
              ₹{positions.reduce((sum, p) => sum + (p.average_price * p.quantity), 0).toFixed(2)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
