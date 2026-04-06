// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

// Broker Connection Types
export interface BrokerConnection {
  connected: boolean;
  broker: string | null;
  user_id?: string;
  user_name?: string;
  email?: string;
  login_time?: string;
  expiry_date?: string;
  connected_at?: string;
}

export interface BrokerCredentials {
  api_key: string;
  api_secret: string;
  access_token: string;
}

// Order Types
export interface Order {
  order_id: string;
  symbol: string;
  exchange: string;
  transaction_type: 'BUY' | 'SELL';
  order_type: 'MARKET' | 'LIMIT';
  quantity: number;
  price?: number;
  product: 'MIS' | 'CNC';
  status: string;
  timestamp: string;
}

export interface PlaceOrderRequest {
  symbol: string;
  exchange: string;
  transaction_type: 'BUY' | 'SELL';
  order_type: 'MARKET' | 'LIMIT';
  quantity: number;
  price?: number;
  product: 'MIS' | 'CNC';
}

export interface PlaceOrderResponse {
  order_id: string;
  status: string;
  message?: string;
}

// Position Types
export interface Position {
  symbol: string;
  quantity: number;
  average_price: number;
  ltp: number;
  pnl: number;
  product: 'MIS' | 'CNC';
}

// Dashboard Types
export interface DashboardData {
  account_balance: number;
  available_margin: number;
  used_margin: number;
  total_pnl?: number;
  today_pnl: number;
  open_positions: number;
  total_orders: number;
  holdings_count?: number;
  broker_status: 'connected' | 'disconnected';
  broker_connected?: boolean;
  user_id?: string;
  user_name?: string;
  fetched_at?: string;
  error?: string;
}

// Log Types
export interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'ERROR' | 'WARNING' | 'DEBUG';
  message: string;
}

// Market Data Types
export interface MarketQuote {
  symbol: string;
  last_price: number;
  change: number;
  change_percent: number;
  high: number;
  low: number;
  open: number;
  close: number;
  volume: number;
}

// Strategy Types
export interface Strategy {
  strategy_id: string;
  name: string;
  symbol: string;
  timeframe: string;
  status: 'registered' | 'running' | 'stopped';
  created_at?: string;
  started_at?: string;
  stopped_at?: string;
  default?: boolean;  // Indicates if this is a default strategy
  description?: string;
}

// Combined Strategy Types
export interface CombinedStrategyInfo {
  name: string;
  type: 'default' | 'individual';
  status: 'active' | 'available' | 'inactive';
  description: string;
  strategies_included?: string[];
  weights?: {
    [key: string]: number;
  };
  min_confidence?: number;
  performance?: {
    total_signals: number;
    win_rate: number;
    avg_confidence: number;
    last_signal: any | null;
  };
}

export interface RegisterStrategyRequest {
  name: string;
  symbol: string;
  timeframe?: string;
}

export interface RegisterStrategyResponse {
  strategy_id: string;
  status: string;
  message?: string;
}

export interface StrategyStats {
  total: number;
  running: number;
  registered: number;
  stopped: number;
}
