import React from 'react';
import { Activity } from 'lucide-react';
import type { BrokerConnection } from '../../types';

interface HeaderProps {
  brokerStatus: BrokerConnection | null;
}

export const Header: React.FC<HeaderProps> = ({ brokerStatus }) => {
  const isConnected = brokerStatus?.connected ?? false;
  
  return (
    <header 
      className="h-16 px-6 flex items-center justify-between"
      style={{ 
        backgroundColor: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-default)'
      }}
    >
      {/* Left side - Page title will go here */}
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          Trading Platform
        </h2>
      </div>

      {/* Right side - Broker status indicator */}
      <div className="flex items-center gap-3">
        <div 
          className="flex items-center gap-2 px-3 py-1.5 rounded-full"
          style={{ 
            backgroundColor: isConnected ? 'rgba(0, 255, 156, 0.15)' : 'rgba(255, 77, 79, 0.15)',
            border: `1px solid ${isConnected ? 'var(--accent-success)' : 'var(--accent-danger)'}`
          }}
        >
          <Activity 
            size={16} 
            style={{ color: isConnected ? 'var(--accent-success)' : 'var(--accent-danger)' }}
          />
          <span 
            className="text-sm font-medium"
            style={{ color: isConnected ? 'var(--accent-success)' : 'var(--accent-danger)' }}
          >
            {isConnected ? 'Broker Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
    </header>
  );
};