import React, { useState, useEffect } from 'react';
import { angelService, setAngelConnected, removeAngelConnected, getAngelConnected } from '../services/angelApi';
import { Link2, Loader, CheckCircle, XCircle, LogOut, Key } from 'lucide-react';

export const AngelOneCard: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  const [totp, setTotp] = useState('');

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const storedConnected = getAngelConnected();
      if (storedConnected) {
        setIsConnected(true);
      }
      
      const status = await angelService.getStatus();
      if (status.data?.authenticated) {
        setIsConnected(true);
        setAngelConnected(true);
      }
    } catch (err) {
      console.error('Failed to check Angel One status:', err);
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    if (!totp || totp.length !== 6) {
      setError('Please enter a valid 6-digit OTP');
      setLoading(false);
      return;
    }

    try {
      const result = await angelService.login({ totp });

      if (result.success || result.status === 'success') {
        setSuccessMessage('Connected to Angel One successfully!');
        setIsConnected(true);
        setAngelConnected(true);
        setTotp('');
      } else {
        setError(result.message || 'Login failed. Please check your OTP.');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to connect. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    setError(null);

    try {
      await angelService.logout();
      removeAngelConnected();
      setIsConnected(false);
      setSuccessMessage('Disconnected from Angel One');
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to disconnect');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-trading-card rounded-xl p-6 border border-trading-border">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <Key size={20} className="text-purple-400" />
        Angel One Connection
      </h3>

      {successMessage && (
        <div className="mb-4 p-3 bg-profit-green/10 border border-profit-green rounded-lg flex items-center gap-2 text-profit-green text-sm">
          <CheckCircle size={16} />
          <span>{successMessage}</span>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-loss-red/10 border border-loss-red rounded-lg flex items-center gap-2 text-loss-red text-sm">
          <XCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {isConnected ? (
        <div className="space-y-4">
          <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-purple-400 mb-3">
              <CheckCircle size={18} />
              <span className="font-medium">Connected ✅</span>
            </div>
            <div className="text-sm text-gray-300 space-y-2">
              <div className="flex justify-between py-1">
                <span>Broker:</span>
                <span className="font-medium">Angel One SmartAPI</span>
              </div>
              <div className="flex justify-between py-1">
                <span>Status:</span>
                <span className="text-profit-green">Session Active</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleDisconnect}
            disabled={loading}
            className="w-full bg-loss-red hover:bg-red-700 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
          >
            <LogOut size={20} />
            {loading ? 'Disconnecting...' : 'Disconnect'}
          </button>
        </div>
      ) : (
        <form onSubmit={handleConnect} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Enter OTP (6-digit)</label>
            <input
              type="text"
              value={totp}
              onChange={(e) => setTotp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="w-full px-4 py-4 bg-trading-dark border border-trading-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all text-center text-2xl tracking-widest font-mono"
            />
          </div>

          <button
            type="submit"
            disabled={loading || totp.length !== 6}
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader size={20} className="animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                <Link2 size={20} />
                Connect Angel One
              </>
            )}
          </button>
          
          <p className="text-xs text-gray-500 text-center">
            Enter the 6-digit OTP from your Authenticator app
          </p>
        </form>
      )}
    </div>
  );
};

export default AngelOneCard;