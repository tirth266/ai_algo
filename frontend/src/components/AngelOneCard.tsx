import React, { useState, useEffect } from 'react';
import { angelService, setAngelToken, removeAngelToken, getAngelToken } from '../services/angelApi';
import { Link2, Loader, CheckCircle, XCircle, LogOut, Key } from 'lucide-react';

export const AngelOneCard: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  const [clientCode, setClientCode] = useState('');
  const [password, setPassword] = useState('');
  const [totp, setTotp] = useState('');

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const storedToken = getAngelToken();
      if (storedToken) {
        setIsConnected(true);
      }
      
      const status = await angelService.getStatus();
      if (status.data?.authenticated) {
        setIsConnected(true);
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

    if (!clientCode || !password || !totp) {
      setError('Please fill in all fields');
      setLoading(false);
      return;
    }

    try {
      const result = await angelService.login({
        client_code: clientCode,
        password: password,
        totp: totp,
      });

      if (result.success) {
        setSuccessMessage('Connected to Angel One successfully!');
        setIsConnected(true);
        if (result.data?.jwt_token) {
          setAngelToken(result.data.jwt_token);
        }
        setClientCode('');
        setPassword('');
        setTotp('');
      } else {
        setError(result.message || 'Login failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to connect');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    setError(null);

    try {
      await angelService.logout();
      removeAngelToken();
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
            <label className="block text-sm text-gray-400 mb-2">Client ID</label>
            <input
              type="text"
              value={clientCode}
              onChange={(e) => setClientCode(e.target.value)}
              placeholder="Enter Client ID"
              className="w-full px-4 py-3 bg-trading-dark border border-trading-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter Password"
              className="w-full px-4 py-3 bg-trading-dark border border-trading-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">TOTP Code</label>
            <input
              type="text"
              value={totp}
              onChange={(e) => setTotp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="Enter 6-digit TOTP"
              maxLength={6}
              className="w-full px-4 py-3 bg-trading-dark border border-trading-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 transition-all disabled:opacity-50"
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
        </form>
      )}
    </div>
  );
};

export default AngelOneCard;