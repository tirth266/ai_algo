import React, { useState, useEffect, useCallback } from 'react';
import { angelService, setAngelConnected, removeAngelConnected, getAngelConnected, getSessionExpiry, setSessionExpiry } from '../services/angelApi';
import { Link2, Loader, CheckCircle, XCircle, LogOut, Key, Clock } from 'lucide-react';

const SESSION_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours

export const AngelOneCard: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [sessionTimeLeft, setSessionTimeLeft] = useState<string>('');
  const [totp, setTotp] = useState('');

  const checkStatus = useCallback(async () => {
    try {
      const storedConnected = getAngelConnected();
      const sessionExpiry = getSessionExpiry();
      
      if (storedConnected && sessionExpiry) {
        const now = Date.now();
        if (now > sessionExpiry) {
          removeAngelConnected();
          setIsConnected(false);
          setError('Session expired. Please login again.');
          return;
        }
        setIsConnected(true);
        
        const timeLeft = sessionExpiry - now;
        const hours = Math.floor(timeLeft / (1000 * 60 * 60));
        const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        setSessionTimeLeft(`${hours}h ${minutes}m`);
      }
      
      const status = await angelService.getStatus();
      if (status.data?.authenticated) {
        setIsConnected(true);
        setAngelConnected(true);
        setSessionExpiry(Date.now() + SESSION_DURATION_MS);
      }
    } catch (err) {
      console.error('Failed to check Angel One status:', err);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 60000);
    return () => clearInterval(interval);
  }, [checkStatus]);

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
        setSessionExpiry(Date.now() + SESSION_DURATION_MS);
        setTotp('');
        setTimeout(() => setSuccessMessage(null), 3000);
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
      setSessionTimeLeft('');
      setSuccessMessage('Disconnected from Angel One');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to disconnect');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-trading-card rounded-2xl p-6 border border-trading-border shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Key size={20} className="text-purple-400" />
          Angel One
        </h3>
        {isConnected && (
          <span className="flex items-center gap-1 text-xs text-profit-green bg-profit-green/10 px-2 py-1 rounded-full">
            <span className="w-2 h-2 bg-profit-green rounded-full animate-pulse"></span>
            Active
          </span>
        )}
      </div>

      <div className="space-y-3">
        {successMessage && (
          <div className="p-3 bg-profit-green/10 border border-profit-green/30 rounded-lg flex items-center gap-2 text-profit-green text-sm animate-fade-in">
            <CheckCircle size={16} />
            <span>{successMessage}</span>
          </div>
        )}

        {error && (
          <div className="p-3 bg-loss-red/10 border border-loss-red/30 rounded-lg flex items-center gap-2 text-loss-red text-sm animate-fade-in">
            <XCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {isConnected ? (
          <div className="space-y-4">
            <div className="p-4 bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
                  <CheckCircle size={20} className="text-purple-400" />
                </div>
                <div>
                  <p className="text-white font-medium">Connected</p>
                  <p className="text-xs text-gray-400">Angel One SmartAPI</p>
                </div>
              </div>
              
              {sessionTimeLeft && (
                <div className="flex items-center gap-2 text-xs text-gray-400 mt-2 pt-2 border-t border-gray-700">
                  <Clock size={14} />
                  <span>Session expires in {sessionTimeLeft}</span>
                </div>
              )}
            </div>

            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="w-full bg-loss-red/20 hover:bg-loss-red/30 text-loss-red border border-loss-red/30 font-medium py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {loading ? (
                <Loader size={18} className="animate-spin" />
              ) : (
                <LogOut size={18} />
              )}
              {loading ? 'Disconnecting...' : 'Disconnect'}
            </button>
          </div>
        ) : (
          <form onSubmit={handleConnect} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">One-Time Password</label>
              <div className="relative">
                <input
                  type="text"
                  value={totp}
                  onChange={(e) => setTotp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="------"
                  maxLength={6}
                  autoComplete="one-time-code"
                  className="w-full px-4 py-4 bg-trading-dark border border-trading-border rounded-xl text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all text-center text-3xl tracking-[0.5em] font-mono"
                />
                <div className="absolute right-4 top-1/2 -translate-y-1/2 flex gap-1">
                  {[0, 1, 2, 3, 4, 5].map((i) => (
                    <div 
                      key={i} 
                      className={`w-2 h-2 rounded-full transition-colors ${i < totp.length ? 'bg-purple-500' : 'bg-gray-700'}`}
                    />
                  ))}
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || totp.length !== 6}
              className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-semibold py-3.5 px-4 rounded-xl flex items-center justify-center gap-2 transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-lg shadow-purple-500/20"
            >
              {loading ? (
                <>
                  <Loader size={20} className="animate-spin" />
                  <span>Connecting...</span>
                </>
              ) : (
                <>
                  <Link2 size={20} />
                  <span>Connect Angel One</span>
                </>
              )}
            </button>
            
            <p className="text-xs text-gray-500 text-center">
              Enter the 6-digit code from your authenticator app
            </p>
          </form>
        )}
      </div>
    </div>
  );
};

export default AngelOneCard;