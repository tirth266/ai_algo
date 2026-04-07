import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  SendHorizontal, 
  PieChart, 
  FileText,
  Link2,
  FileStack,
  Cpu,
  Activity,
  BarChart3,
  LineChart
} from 'lucide-react';

const menuItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/order-panel', label: 'Order Panel', icon: SendHorizontal },
  { path: '/positions', label: 'Positions', icon: PieChart },
  { path: '/orders', label: 'Orders', icon: FileText },
  { path: '/strategies', label: 'Strategies', icon: Cpu },
  { path: '/backtest', label: 'Backtesting', icon: BarChart3 },
  { path: '/broker', label: 'Broker Connection', icon: Link2 },
  { path: '/logs', label: 'Logs', icon: FileStack },
  { path: '/trading', label: 'Live Trading', icon: Activity },
  { path: '/trading-dashboard', label: 'Trading Dashboard', icon: LineChart },
];

export const Sidebar: React.FC = () => {
  return (
    <div 
      className="w-64 flex flex-col glass"
      style={{ borderRight: '1px solid var(--border-default)' }}
    >
      {/* Logo / Title */}
      <div 
        className="p-4"
        style={{ borderBottom: '1px solid var(--border-default)' }}
      >
        <h1 className="text-xl font-bold gradient-text">Algo Trading</h1>
        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>Personal Platform</p>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 p-4 space-y-1">
        {menuItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 btn-micro ${
                isActive
                  ? 'text-white'
                  : 'hover:text-white'
              }`
            }
            style={({ isActive }) => ({
              backgroundColor: isActive ? 'var(--accent-primary)' : 'transparent',
              color: isActive ? '#000000' : 'var(--text-secondary)',
              boxShadow: isActive ? '0 0 20px var(--glow-primary)' : 'none',
            })}
          >
            <item.icon size={20} />
            <span className="text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div 
        className="p-4"
        style={{ borderTop: '1px solid var(--border-default)' }}
      >
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          <p>Localhost Only</p>
          <p className="mt-1">No Database</p>
        </div>
      </div>
    </div>
  );
};