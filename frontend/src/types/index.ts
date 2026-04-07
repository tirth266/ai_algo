// ============================================================================
// TRADING SYSTEM TYPES
// ============================================================================

export interface TradeSignal {
  type: 'BUY' | 'SELL';
  entry: number;
  stop_loss: number;
  take_profit: number[];
  confidence: 'high' | 'medium' | 'low';
  reason: string;
}

export interface ActiveTrade {
  id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  entry_price: number;
  quantity: number;
  stop_loss: number;
  current_stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  status: 'OPEN' | 'PARTIAL' | 'CLOSED';
  entry_time: string;
  confidence: string;
  reason: string;
  unrealized_pnl?: number;
}

export interface TradePerformance {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
}

export interface TradingSystemStatus {
  is_running: boolean;
  capital: number;
  open_trades: number;
  performance: TradePerformance;
}

export interface SystemControlRequest {
  action: 'start' | 'stop';
}

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

// ============================================================================
// JOURNAL TYPES - Trade Logging and Analytics
// ============================================================================

export interface TradeLog {
  trade_id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  stop_loss: number | null;
  take_profit: number | null;
  pnl: number;
  fees: number;
  slippage: number;
  entry_time: string;
  exit_time: string | null;
  result: 'WIN' | 'LOSS' | 'BREAKEVEN';
  strategy: string;
  duration_minutes: number;
}

export interface SignalLog {
  signal_id: string;
  timestamp: string;
  symbol: string;
  signal_type: string;
  entry: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  reason: string;
  executed: boolean;
  execution_price: number | null;
  strategy: string;
  confidence: number;
  market_condition: string;
}

export interface PerformanceMetrics {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  loss_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  expectancy: number;
  largest_win: number;
  largest_loss: number;
  avg_trade_duration: number;
  best_day: string;
  worst_day: string;
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
  drawdown: number;
  open_positions: number;
}

export interface StrategyPerformance {
  trades: number;
  wins: number;
  losses: number;
  pnl: number;
  win_rate: number;
  avg_pnl: number;
}

export interface DailySummary {
  date: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
}

export interface SignalStats {
  total_signals: number;
  executed: number;
  rejected: number;
  execution_rate: number;
  rejection_reasons: Record<string, number>;
}

export interface JournalAnalytics {
  performance: PerformanceMetrics;
  equity_curve: EquityPoint[];
  strategy_performance: Record<string, StrategyPerformance>;
  generated_at: string;
}
