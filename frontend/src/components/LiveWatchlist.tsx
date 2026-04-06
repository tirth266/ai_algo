import React, { useEffect, useState } from 'react';

// Replace with your FastAPI backend URL if hosted elsewhere
import { API_BASE_URL } from '../services/api';

interface PriceData {
  [token: string]: number;
}

export const LiveWatchlist: React.FC = () => {
  const [prices, setPrices] = useState<PriceData>({});
  const [prevPrices, setPrevPrices] = useState<PriceData>({});

  // Assuming local mapping or external API mapping to translate token -> symbol visually
  // Hardcoded for demonstration. The actual app would load this from SymbolManager.
  const tokenToSymbolMap: Record<string, string> = {
    '3045': 'SBIN-EQ',
    '2885': 'RELIANCE-EQ',
    '11536': 'TCS-EQ',
    '1594': 'INFY-EQ',
  };

  useEffect(() => {
    // Poll the /api/prices endpoint every 1 second
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/prices`);
        if (response.ok) {
          const freshPrices: PriceData = await response.json();
          
          setPrices((currentPrices) => {
            // Keep the previous prices state so we can calculate flash colors
            setPrevPrices(currentPrices);
            return freshPrices;
          });
        }
      } catch (error) {
        console.error('Failed to fetch prices', error);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const getRowColorClass = (token: string, currentPrice: number) => {
    const prevPrice = prevPrices[token];
    if (!prevPrice) return 'text-gray-100'; // Default Neutral

    if (currentPrice > prevPrice) return 'text-green-500 transition-colors duration-300';
    if (currentPrice < prevPrice) return 'text-red-500 transition-colors duration-300';
    return 'text-gray-100 transition-colors duration-300'; // Unchanged
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow-md border border-gray-700 w-full max-w-md">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-white">Live Watchlist</h2>
        <span className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></span>
          <span className="text-xs text-gray-400 font-mono">LIVE / PUSH</span>
        </span>
      </div>

      {Object.keys(prices).length === 0 ? (
        <div className="text-gray-400 text-center py-4">Waiting for market data...</div>
      ) : (
        <table className="w-full text-left table-auto border-separate pb-2">
          <thead>
            <tr className="text-gray-400 text-sm border-b border-gray-700 uppercase">
              <th className="pb-2 font-medium">Symbol</th>
              <th className="pb-2 text-right font-medium">LTP</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(prices).map(([token, price]) => {
              const symbol = tokenToSymbolMap[token] || `Token ${token}`;
              return (
                <tr key={token} className="hover:bg-gray-750 transition-colors">
                  <td className="py-3 items-center">
                    <span className="font-semibold text-gray-200">{symbol}</span>
                  </td>
                  <td className={`py-3 text-right font-mono font-bold ${getRowColorClass(token, price)}`}>
                    ₹{price.toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};
