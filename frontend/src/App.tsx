import { useEffect, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { DashboardPage } from './pages/DashboardPage';
import { OrderPanelPage } from './pages/OrderPanelPage';
import { PositionsPage } from './pages/PositionsPage';
import { OrdersPage } from './pages/OrdersPage';
import { StrategiesPage } from './pages/StrategiesPage';
import { BrokerConnectionPage } from './pages/BrokerConnectionPage';
import { LogsPage } from './pages/LogsPage';
import { BacktestingPage } from './pages/BacktestingPage';
import TradingPage from './pages/TradingPage';
import { BacktestDashboard } from './pages/BacktestDashboard';
import { LiveTradingPanel } from './pages/LiveTradingPanel';
import { AngelOneCallback } from './pages/AngelOneCallback';
import { TradingDashboard } from './pages/TradingDashboard';
import { brokerService } from './services/api';
import type { BrokerConnection } from './types';

function App() {
  const [brokerStatus, setBrokerStatus] = useState<BrokerConnection | null>(null);

  useEffect(() => {
    brokerService.getStatus()
      .then(setBrokerStatus)
      .catch(console.error);
  }, []);

  return (
    <div className="flex h-screen" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header brokerStatus={brokerStatus} />
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: 'var(--bg-primary)' }}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/order-panel" element={<OrderPanelPage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/strategies" element={<StrategiesPage />} />
            <Route path="/backtest" element={<BacktestingPage />} />
            <Route path="/broker" element={<BrokerConnectionPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <Route path="/backtest-dashboard" element={<BacktestDashboard />} />
            <Route path="/live-trading" element={<LiveTradingPanel />} />
            <Route path="/angel-callback" element={<AngelOneCallback />} />
            <Route path="/trading-dashboard" element={<TradingDashboard />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;