import React, { useEffect, useState } from 'react';
import { orderService } from '../services/api';
import type { Order } from '../types';
import { RefreshCw } from 'lucide-react';

export const OrdersPage: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const data = await orderService.getOrders();
      setOrders(data);
      setError(null);
    } catch (err) {
      setError('Failed to load orders');
      console.error('Orders error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, []);

  const handleRefresh = () => {
    fetchOrders();
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'complete':
        return 'text-profit-green';
      case 'pending':
        return 'text-orange-500';
      case 'cancelled':
      case 'rejected':
        return 'text-loss-red';
      default:
        return 'text-gray-400';
    }
  };

  if (loading && orders.length === 0) {
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
          <h1 className="text-2xl font-bold text-white">Orders</h1>
          <p className="text-gray-400 mt-1">Order history</p>
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
      {/* Orders Table */}
      <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-trading-dark border-b border-trading-border">
            <tr>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Order ID</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Symbol</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Type</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Side</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">Quantity</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-gray-400">Price</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Status</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-gray-400">Time</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-gray-400">
                  No orders found
                </td>
              </tr>
            ) : (
              orders.map((order) => (
                <tr key={order.order_id} className="border-b border-trading-border hover:bg-trading-border/50">
                  <td className="px-6 py-4 text-white font-mono text-sm">{order.order_id}</td>
                  <td className="px-6 py-4 text-white font-medium">{order.symbol}</td>
                  <td className="px-6 py-4 text-gray-400">{order.order_type}</td>
                  <td className={`px-6 py-4 font-medium ${order.transaction_type === 'BUY' ? 'text-profit-green' : 'text-loss-red'}`}>
                    {order.transaction_type}
                  </td>
                  <td className="px-6 py-4 text-right text-white">{order.quantity}</td>
                  <td className="px-6 py-4 text-right text-white">
                    {order.price ? `₹${order.price.toFixed(2)}` : 'MARKET'}
                  </td>
                  <td className={`px-6 py-4 ${getStatusColor(order.status)}`}>
                    {order.status}
                  </td>
                  <td className="px-6 py-4 text-gray-400 text-sm">
                    {new Date(order.timestamp).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      {orders.length > 0 && (
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Total Orders</div>
            <div className="text-2xl font-bold text-white">{orders.length}</div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Completed</div>
            <div className="text-2xl font-bold text-profit-green">
              {orders.filter(o => o.status.toLowerCase() === 'complete').length}
            </div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Pending</div>
            <div className="text-2xl font-bold text-orange-500">
              {orders.filter(o => o.status.toLowerCase() === 'pending').length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
