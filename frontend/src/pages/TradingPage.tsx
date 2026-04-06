import React from 'react';
import TradingControlPanel from '../components/TradingControlPanel';

const TradingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-6">Live Trading</h1>
        <TradingControlPanel />
      </div>
    </div>
  );
};

export default TradingPage;
