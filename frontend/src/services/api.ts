// ============================================================================
// API SERVICE LAYER
// Centralized API communication using Axios
// ============================================================================

import axios from 'axios';
import type {
  BrokerConnection,
  BrokerCredentials,
  Order,
  PlaceOrderRequest,
  PlaceOrderResponse,
  Position,
  DashboardData,
  LogEntry,
  MarketQuote,
  Strategy,
  RegisterStrategyRequest,
  RegisterStrategyResponse,
  StrategyStats,
  CombinedStrategyInfo
} from '../types';

// Use environment variable, fallback to local dev server
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:7000';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// BROKER SERVICE
// ============================================================================

export const brokerService = {
  /**
   * Connect to broker API (legacy method - kept for compatibility)
   */
  connect: async (credentials: BrokerCredentials): Promise<BrokerConnection> => {
    const response = await apiClient.post<BrokerConnection>('/broker/connect', credentials);
    return response.data;
  },

  /**
   * Get current broker connection status
   */
  getStatus: async (): Promise<BrokerConnection> => {
    const response = await apiClient.get<BrokerConnection>('/broker/status');
    return response.data;
  },

  /**
   * Get broker account profile with margin details
   */
  getProfile: async (): Promise<any> => {
    const response = await apiClient.get('/broker/profile');
    return response.data;
  },

  /**
   * Logout from broker (new web-based authentication)
   */
  logout: async (): Promise<void> => {
    await apiClient.post('/broker/logout');
  },

  /**
   * Disconnect from broker (legacy - kept for compatibility)
   */
  disconnect: async (): Promise<void> => {
    await apiClient.post('/broker/disconnect');
  },
};

// ============================================================================
// ORDER SERVICE
// ============================================================================

export const orderService = {
  /**
   * Place a new order
   */
  placeOrder: async (orderData: PlaceOrderRequest): Promise<PlaceOrderResponse> => {
    const response = await apiClient.post<PlaceOrderResponse>('/order/place', orderData);
    return response.data;
  },

  /**
   * Get all orders
   */
  getOrders: async (): Promise<Order[]> => {
    const response = await apiClient.get<Order[]>('/orders');
    return response.data;
  },

  /**
   * Get specific order by ID
   */
  getOrder: async (orderId: string): Promise<Order> => {
    const response = await apiClient.get<Order>(`/order/${orderId}`);
    return response.data;
  },
};

// ============================================================================
// POSITION SERVICE
// ============================================================================

export const positionService = {
  /**
   * Get all open positions
   */
  getPositions: async (): Promise<Position[]> => {
    const response = await apiClient.get<Position[]>('/positions');
    return response.data;
  },

  /**
   * Square off a position
   */
  squareOff: async (symbol: string): Promise<void> => {
    await apiClient.post('/position/squareoff', { symbol });
  },
};

// ============================================================================
// DASHBOARD SERVICE
// ============================================================================

export const dashboardService = {
  /**
   * Get dashboard data
   */
  getDashboardData: async (): Promise<DashboardData> => {
    const response = await apiClient.get<DashboardData>('/dashboard');
    return response.data;
  },
};

// ============================================================================
// LOGS SERVICE
// ============================================================================

export const logsService = {
  /**
   * Get system logs
   */
  getLogs: async (level?: string): Promise<LogEntry[]> => {
    const params = level ? { level } : {};
    const response = await apiClient.get<LogEntry[]>('/logs', { params });
    return response.data;
  },

  /**
   * Clear all logs
   */
  clearLogs: async (): Promise<void> => {
    await apiClient.post('/logs/clear');
  },
};

// ============================================================================
// MARKET DATA SERVICE
// ============================================================================

export const marketDataService = {
  /**
   * Get market quote for a symbol
   */
  getQuote: async (symbol: string): Promise<MarketQuote> => {
    const response = await apiClient.get<MarketQuote>('/market/quote', {
      params: { symbol },
    });
    return response.data;
  },
};



export const strategyService = {
  /**
   * Register a new strategy
   */
  register: async (data: RegisterStrategyRequest): Promise<RegisterStrategyResponse> => {
    const response = await apiClient.post<RegisterStrategyResponse>('/strategy/register', data);
    return response.data;
  },

  /**
   * Start a strategy
   */
  start: async (strategyId: string, symbol?: string, timeframe?: string): Promise<void> => {
    const payload: any = { strategy_id: strategyId };
    if (symbol) payload.symbol = symbol;
    if (timeframe) payload.timeframe = timeframe;
    
    await apiClient.post('/strategy/start', payload);
  },

  /**
   * Stop a strategy
   */
  stop: async (strategyId: string): Promise<void> => {
    await apiClient.post('/strategy/stop', { strategy_id: strategyId });
  },

  /**
   * Unregister a strategy
   */
  unregister: async (strategyId: string): Promise<void> => {
    await apiClient.post('/strategy/unregister', { strategy_id: strategyId });
  },

  /**
   * Get all strategies
   */
  list: async (status?: string): Promise<Strategy[]> => {
    const params = status ? { status } : {};
    const response = await apiClient.get<{ strategies: Strategy[]; total: number }>('/strategies', { params });
    return response.data.strategies;
  },

  /**
   * Get combined power strategy details
   */
  getCombinedDetails: async (): Promise<CombinedStrategyInfo> => {
    const response = await apiClient.get<CombinedStrategyInfo>('/strategies/combined/details');
    return response.data;
  },

  /**
   * Get strategy statistics
   */
  getStats: async (): Promise<StrategyStats> => {
    const response = await apiClient.get<StrategyStats>('/strategy/stats');
    return response.data;
  },

  /**
   * Clear all strategies from the registry
   */
  clearAll: async (): Promise<void> => {
    await apiClient.post('/strategies/clear');
  },
};

export default apiClient;
