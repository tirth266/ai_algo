import { useState, useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

// Define Typescript interfaces for real-time data
export interface RealtimePrice {
  symbol: string;
  ltp: number;
  change: number;
  change_pct: number;
  timestamp: string;
}

export interface RealtimePnL {
  total_pnl: number;
  realized: number;
  unrealized: number;
  timestamp: string;
}

export interface RealtimeOrder {
  order_id: string;
  status: string;
  symbol: string;
  qty: number;
  price: number;
}

export interface RealtimePosition {
  symbol: string;
  qty: number;
  avg_price: number;
  ltp: number;
  pnl: number;
}

/**
 * Custom hook for real-time data via WebSocket connection
 * @param symbols Array of symbols to subscribe to
 * @returns Object containing real-time data and connection status
 */
export const useRealtimeData = (symbols: string[] = []) => {
  const [prices, setPrices] = useState<RealtimePrice[]>([]);
  const [pnl, setPnl] = useState<RealtimePnL>({
    total_pnl: 0,
    realized: 0,
    unrealized: 0,
    timestamp: new Date().toISOString()
  });
  const [orders, setOrders] = useState<RealtimeOrder[]>([]);
  const [positions, setPositions] = useState<RealtimePosition[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    let socket: Socket | null = null;
    let reconnectAttempts = 0;
    const maxRetries = 5;

    const initializeSocket = () => {
      try {
        // Connect to backend WebSocket server
        const s = io(import.meta.env.VITE_API_URL || 'http://localhost:5000', {
          transports: ['websocket'],
          reconnectionAttempts: maxRetries,
          timeout: 10000
        });

        s.on('connect', () => {

          setIsConnected(true);
          setError(null);
          reconnectAttempts = 0;
          
          // Subscribe to symbols upon connection
          if (symbols.length > 0) {
            s.emit('subscribe_symbols', { symbols });
          }
        });

        s.on('disconnect', () => {

          setIsConnected(false);
          
          // Attempt to reconnect if we haven't exceeded max retries
          if (reconnectAttempts < maxRetries) {
            reconnectAttempts++;
            setRetryCount(reconnectAttempts);
            setError(`Reconnecting... (${reconnectAttempts}/${maxRetries})`);
          } else {
            setError('Connection lost. Max retries exceeded.');
          }
        });

        s.on('connect_error', (err) => {
          console.error('WebSocket connection error:', err);
          setIsConnected(false);
          setError(`Connection error: ${err.message}`);
        });

        s.on('price_update', (data: RealtimePrice) => {
          setPrices(prev => {
            const index = prev.findIndex(p => p.symbol === data.symbol);
            if (index >= 0) {
              const updated = [...prev];
              updated[index] = data;
              return updated;
            }
            return [...prev, data];
          });
        });

        s.on('pnl_update', (data: RealtimePnL) => {
          setPnl(data);
        });

        s.on('order_update', (data: RealtimeOrder | RealtimeOrder[]) => {
          const orderArray = Array.isArray(data) ? data : [data];
          setOrders(orderArray);
        });

        s.on('position_update', (data: RealtimePosition | RealtimePosition[]) => {
          const positionArray = Array.isArray(data) ? data : [data];
          setPositions(positionArray);
        });

        return s;
      } catch (err) {
        console.error('Failed to initialize WebSocket:', err);
        setError('Failed to initialize WebSocket connection');
        return null;
      }
    };

    // Initialize socket connection
    socket = initializeSocket();
    socketRef.current = socket;

    // Cleanup on unmount
    return () => {
      if (socket) {
        socket.disconnect();
        socket = null;
      }
    };
  }, [symbols, socketRef]);

  // Resubscribe to symbols when they change
  useEffect(() => {
    // socketRef.current would hold the socket instance
    // In a more complex implementation, we'd use useRef for the socket
    // For now, we'll rely on the reconnection logic to handle symbol changes
  }, [symbols]);

  return {
    prices,
    pnl,
    orders,
    positions,
    isConnected,
    error,
    retryCount
  };
};