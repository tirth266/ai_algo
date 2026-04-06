import React, { useState } from 'react';
import { orderService } from '../services/api';
import type { PlaceOrderRequest, PlaceOrderResponse } from '../types';
import { Send, TrendingUp, TrendingDown } from 'lucide-react';

export const OrderPanelPage: React.FC = () => {
  const [formData, setFormData] = useState<PlaceOrderRequest>({
    symbol: '',
    exchange: 'NSE',
    transaction_type: 'BUY',
    order_type: 'MARKET',
    quantity: 1,
    product: 'MIS',
    price: undefined,
  });

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<PlaceOrderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const result = await orderService.placeOrder(formData);
      setResponse(result);
      
      // Reset form after successful order
      setFormData({
        symbol: '',
        exchange: 'NSE',
        transaction_type: 'BUY',
        order_type: 'MARKET',
        quantity: 1,
        product: 'MIS',
        price: undefined,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to place order');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'quantity' ? parseInt(value) || 0 : value,
    }));
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Order Panel</h1>
        <p className="text-gray-400 mt-1">Place manual trades</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Order Form */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="bg-trading-card rounded-lg p-6 border border-trading-border space-y-4">
            {/* Symbol and Exchange */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Symbol *</label>
                <input
                  type="text"
                  name="symbol"
                  value={formData.symbol}
                  onChange={handleChange}
                  placeholder="e.g., RELIANCE"
                  className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-2">Exchange *</label>
                <select
                  name="exchange"
                  value={formData.exchange}
                  onChange={handleChange}
                  className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
                >
                  <option value="NSE">NSE</option>
                  <option value="BSE">BSE</option>
                  <option value="NFO">NFO</option>
                  <option value="MCX">MCX</option>
                </select>
              </div>
            </div>

            {/* Transaction Type */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Transaction Type *</label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, transaction_type: 'BUY' }))}
                  className={`flex items-center justify-center gap-2 py-3 rounded font-medium transition-colors ${
                    formData.transaction_type === 'BUY'
                      ? 'bg-profit-green text-white'
                      : 'bg-trading-dark text-gray-400 hover:bg-trading-border'
                  }`}
                >
                  <TrendingUp size={20} />
                  BUY
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, transaction_type: 'SELL' }))}
                  className={`flex items-center justify-center gap-2 py-3 rounded font-medium transition-colors ${
                    formData.transaction_type === 'SELL'
                      ? 'bg-loss-red text-white'
                      : 'bg-trading-dark text-gray-400 hover:bg-trading-border'
                  }`}
                >
                  <TrendingDown size={20} />
                  SELL
                </button>
              </div>
            </div>

            {/* Order Type and Product */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Order Type *</label>
                <select
                  name="order_type"
                  value={formData.order_type}
                  onChange={handleChange}
                  className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
                >
                  <option value="MARKET">MARKET</option>
                  <option value="LIMIT">LIMIT</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-2">Product *</label>
                <select
                  name="product"
                  value={formData.product}
                  onChange={handleChange}
                  className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
                >
                  <option value="MIS">MIS</option>
                  <option value="CNC">CNC</option>
                </select>
              </div>
            </div>

            {/* Quantity and Price */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Quantity *</label>
                <input
                  type="number"
                  name="quantity"
                  value={formData.quantity}
                  onChange={handleChange}
                  placeholder="0"
                  min="1"
                  className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-2">
                  Price {formData.order_type === 'LIMIT' ? '*' : '(Optional)'}
                </label>
                <input
                  type="number"
                  name="price"
                  value={formData.price || ''}
                  onChange={handleChange}
                  placeholder="0.00"
                  step="0.05"
                  disabled={formData.order_type === 'MARKET'}
                  className="w-full bg-trading-dark border border-trading-border rounded px-4 py-2 text-white focus:outline-none focus:border-accent-blue disabled:opacity-50"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-accent-blue hover:bg-blue-700 text-white font-medium py-3 rounded flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              <Send size={20} />
              {loading ? 'Placing Order...' : 'Place Order'}
            </button>
          </form>
        </div>

        {/* Response Panel */}
        <div className="space-y-6">
          {/* Success Response */}
          {response && (
            <div className="bg-trading-card rounded-lg p-6 border border-profit-green">
              <h3 className="text-lg font-semibold text-profit-green mb-4">Order Placed Successfully</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Order ID</span>
                  <span className="text-white font-mono">{response.order_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Status</span>
                  <span className="text-profit-green">{response.status}</span>
                </div>
                {response.message && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Message</span>
                    <span className="text-white">{response.message}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error Response */}
          {error && (
            <div className="bg-trading-card rounded-lg p-6 border border-loss-red">
              <h3 className="text-lg font-semibold text-loss-red mb-4">Order Failed</h3>
              <p className="text-gray-300">{error}</p>
            </div>
          )}

          {/* Instructions */}
          {!response && !error && (
            <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
              <h3 className="text-lg font-semibold text-white mb-4">Instructions</h3>
              <ul className="space-y-2 text-sm text-gray-400">
                <li>• Fill in all required fields marked with *</li>
                <li>• For LIMIT orders, price is mandatory</li>
                <li>• MARKET orders execute at current market price</li>
                <li>• MIS is for intraday, CNC is for delivery</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
