import React, { useState, useEffect } from 'react';
import { brokerService, API_BASE_URL } from '../services/api';
import type { BrokerConnection } from '../types';
import { Link2, Loader, CheckCircle, XCircle, LogOut } from 'lucide-react';

export const BrokerConnectionPage: React.FC = () => {
  const [brokerStatus, setBrokerStatus] = useState<BrokerConnection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Check broker status on mount
  useEffect(() => {
    checkBrokerStatus();
  }, []);

  // Check for callback status
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    const userId = params.get('user_id');
    const userName = params.get('user_name');

    if (status === 'success' && userId) {
      setSuccessMessage(`✅ Connected successfully! Welcome, ${userName || userId}`);
      checkBrokerStatus();
      // Clear the URL
      window.history.replaceState({}, document.title, '/broker');
    } else if (status === 'error') {
      setError('❌ Authentication failed. Please try again.');
    }
  }, []);

  const checkBrokerStatus = async () => {
    try {
      const status = await brokerService.getStatus();
      if (status.connected) {
        setBrokerStatus(status);
      } else {
        setBrokerStatus(null);
      }
    } catch (err) {
      console.error('Failed to check broker status:', err);
    }
  };

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // Redirect to Zerodha login page
      window.location.href = `${API_BASE_URL}/api/broker/login`;
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to initiate connection');
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    setError(null);

    try {
      await brokerService.logout();
      setBrokerStatus(null);
      setSuccessMessage('Successfully disconnected from broker');
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to disconnect');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Broker Connection</h1>
        <p className="text-gray-400 mt-1">Connect to Zerodha Kite Connect API</p>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div className="p-4 bg-profit-green/10 border border-profit-green rounded-lg flex items-center gap-3 text-profit-green">
          <CheckCircle size={20} />
          <span>{successMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-loss-red/10 border border-loss-red rounded-lg flex items-center gap-3 text-loss-red">
          <XCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connection Status */}
        <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Link2 size={20} />
            {brokerStatus?.connected ? 'Connected' : 'Not Connected'}
          </h3>

          {brokerStatus?.connected ? (
            <div className="space-y-4">
              <div className="p-4 bg-profit-green/10 border border-profit-green rounded">
                <div className="flex items-center gap-2 text-profit-green mb-2">
                  <CheckCircle size={18} />
                  <span className="font-medium">Broker Connected Successfully</span>
                </div>
                <div className="text-sm text-gray-300 space-y-2">
                  <div className="flex justify-between py-1">
                    <span>Broker:</span>
                    <span className="font-medium">{brokerStatus.broker}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span>User ID:</span>
                    <span>{brokerStatus.user_id || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span>User Name:</span>
                    <span>{brokerStatus.user_name || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span>Login Time:</span>
                    <span>{brokerStatus.login_time ? new Date(brokerStatus.login_time).toLocaleString() : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span>Expires:</span>
                    <span>{brokerStatus.expiry_date ? new Date(brokerStatus.expiry_date).toLocaleString() : 'N/A'}</span>
                  </div>
                </div>
              </div>

              <button
                onClick={handleDisconnect}
                disabled={loading}
                className="w-full bg-loss-red hover:bg-red-700 text-white font-medium py-3 rounded flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                <LogOut size={20} />
                {loading ? 'Disconnecting...' : 'Disconnect Broker'}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 bg-gray-800 border border-gray-700 rounded text-center">
                <p className="text-gray-400 mb-4">You are not connected to Zerodha</p>
                <p className="text-sm text-gray-500 mb-4">Click the button below to start the authentication process</p>
                
                <button
                  onClick={handleConnect}
                  disabled={loading}
                  className="w-full bg-accent-blue hover:bg-blue-700 text-white font-medium py-3 rounded flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader size={20} className="animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <Link2 size={20} />
                      Connect Zerodha
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="space-y-6">
          <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
            <h3 className="text-lg font-semibold text-white mb-4">How to Connect</h3>
            <ol className="space-y-3 text-sm text-gray-400">
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-accent-blue text-white rounded-full flex items-center justify-center text-xs font-bold">1</span>
                <span>Click the "Connect Zerodha" button</span>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-accent-blue text-white rounded-full flex items-center justify-center text-xs font-bold">2</span>
                <span>You will be redirected to Zerodha's login page</span>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-accent-blue text-white rounded-full flex items-center justify-center text-xs font-bold">3</span>
                <span>Login with your Zerodha Kite credentials</span>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-accent-blue text-white rounded-full flex items-center justify-center text-xs font-bold">4</span>
                <span>After successful login, you'll be redirected back</span>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-accent-blue text-white rounded-full flex items-center justify-center text-xs font-bold">5</span>
                <span>Your session will be stored securely and auto-renewed daily</span>
              </li>
            </ol>
          </div>

          <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
            <h3 className="text-lg font-semibold text-white mb-4">Important Notes</h3>
            <ul className="space-y-2 text-sm text-gray-400">
              <li>• Access tokens expire daily at 3:30 PM IST</li>
              <li>• The system will automatically attempt to renew your token</li>
              <li>• You may need to re-login if token renewal fails</li>
              <li>• Keep your Zerodha credentials secure</li>
              <li>• Session is stored in backend/config/zerodha_session.json</li>
            </ul>
          </div>

          <div className="bg-trading-card rounded-lg p-6 border border-trading-border">
            <h3 className="text-lg font-semibold text-white mb-4">Security</h3>
            <div className="text-sm text-gray-400">
              <p className="mb-2">Your authentication is secure:</p>
              <ul className="space-y-1">
                <li>✓ API credentials stored in .env file only</li>
                <li>✓ Access tokens encrypted and stored securely</li>
                <li>✓ No sensitive data exposed to frontend</li>
                <li>✓ HTTPS recommended for production use</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
