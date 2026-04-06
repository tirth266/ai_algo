import React, { useEffect, useState } from 'react';
import { logsService } from '../services/api';
import type { LogEntry } from '../types';
import { FileStack, Trash2, Filter } from 'lucide-react';

export const LogsPage: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('ALL');
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async (level?: string) => {
    try {
      setLoading(true);
      const data = level && level !== 'ALL' 
        ? await logsService.getLogs(level)
        : await logsService.getLogs();
      setLogs(data);
      setError(null);
    } catch (err) {
      setError('Failed to load logs');
      console.error('Logs error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleFilterChange = (level: string) => {
    setFilter(level);
    fetchLogs(level === 'ALL' ? undefined : level);
  };

  const handleClearLogs = async () => {
    try {
      await logsService.clearLogs();
      setLogs([]);
    } catch (err) {
      console.error('Clear logs error:', err);
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'INFO':
        return 'text-accent-blue';
      case 'ERROR':
        return 'text-loss-red';
      case 'WARNING':
        return 'text-orange-500';
      case 'DEBUG':
        return 'text-gray-400';
      default:
        return 'text-gray-400';
    }
  };

  const getLevelBg = (level: string) => {
    switch (level) {
      case 'INFO':
        return 'bg-accent-blue/10 border-accent-blue';
      case 'ERROR':
        return 'bg-loss-red/10 border-loss-red';
      case 'WARNING':
        return 'bg-orange-500/10 border-orange-500';
      case 'DEBUG':
        return 'bg-gray-500/10 border-gray-500';
      default:
        return 'bg-gray-500/10 border-gray-500';
    }
  };

  if (loading && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Logs</h1>
          <p className="text-gray-400 mt-1">Monitor system events and errors</p>
        </div>
        <button
          onClick={handleClearLogs}
          className="flex items-center gap-2 px-4 py-2 bg-trading-card border border-trading-border rounded hover:bg-trading-border transition-colors"
        >
          <Trash2 size={18} />
          Clear Logs
        </button>
      </div>

      {error && (
        <div className="bg-loss-red/10 border border-loss-red text-loss-red p-4 rounded-lg">
          {error}
        </div>
      )}
      {/* Filter Controls */}
      <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-gray-400">
            <Filter size={18} />
            <span className="text-sm font-medium">Filter:</span>
          </div>
          <div className="flex gap-2">
            {['ALL', 'INFO', 'ERROR', 'WARNING', 'DEBUG'].map((level) => (
              <button
                key={level}
                onClick={() => handleFilterChange(level)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  filter === level
                    ? 'bg-accent-blue text-white'
                    : 'bg-trading-dark text-gray-400 hover:bg-trading-border'
                }`}
              >
                {level}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Logs List */}
      <div className="bg-trading-card rounded-lg border border-trading-border overflow-hidden">
        <div className="max-h-[600px] overflow-y-auto">
          {logs.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              <FileStack size={48} className="mx-auto mb-4 opacity-50" />
              <p>No logs found</p>
            </div>
          ) : (
            <div className="divide-y divide-trading-border">
              {logs.map((log, index) => (
                <div
                  key={index}
                  className={`p-4 hover:bg-trading-border/50 transition-colors ${getLevelBg(log.level)}`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`px-2 py-1 rounded text-xs font-bold border ${getLevelColor(log.level)}`}>
                      {log.level}
                    </div>
                    <div className="flex-1">
                      <p className="text-white">{log.message}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {new Date(log.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      {logs.length > 0 && (
        <div className="grid grid-cols-4 gap-6">
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Total Logs</div>
            <div className="text-2xl font-bold text-white">{logs.length}</div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Info</div>
            <div className="text-2xl font-bold text-accent-blue">
              {logs.filter(l => l.level === 'INFO').length}
            </div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Errors</div>
            <div className="text-2xl font-bold text-loss-red">
              {logs.filter(l => l.level === 'ERROR').length}
            </div>
          </div>
          <div className="bg-trading-card rounded-lg p-4 border border-trading-border">
            <div className="text-sm text-gray-400 mb-1">Warnings</div>
            <div className="text-2xl font-bold text-orange-500">
              {logs.filter(l => l.level === 'WARNING').length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
