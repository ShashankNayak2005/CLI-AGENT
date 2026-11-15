import React, { useState } from 'react';
import {
  Terminal,
  Plus,
  Settings,
  Server,
  RefreshCw,
  Trash2,
  Globe,
  Database,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ExternalLink,
} from 'lucide-react';
import StatusIndicator from './StatusIndicator';

export const Sidebar = ({
  tasks = [],
  activeTaskId,
  onSelectTask,
  onNewChat,
  onDeleteTask,
  onRefreshHistory,
  historyLoading = false,
  historyError = null,
  isBackendOnline,
  backendLoading,
  onRefreshBackend,
}) => {
  const [deletingTaskId, setDeletingTaskId] = useState(null);

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return (
          <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.2 rounded border border-emerald-800/40">
            <CheckCircle2 className="w-2.5 h-2.5" /> Done
          </span>
        );
      case 'rejected':
        return (
          <span className="flex items-center gap-1 text-[10px] font-mono text-amber-400 bg-amber-950/40 px-1.5 py-0.2 rounded border border-amber-800/40">
            <AlertTriangle className="w-2.5 h-2.5" /> Rejected
          </span>
        );
      case 'timeout':
        return (
          <span className="flex items-center gap-1 text-[10px] font-mono text-orange-400 bg-orange-950/40 px-1.5 py-0.2 rounded border border-orange-800/40">
            <Clock className="w-2.5 h-2.5" /> Timeout
          </span>
        );
      case 'failed':
      case 'invalid_output':
      default:
        return (
          <span className="flex items-center gap-1 text-[10px] font-mono text-rose-400 bg-rose-950/40 px-1.5 py-0.2 rounded border border-rose-800/40">
            <XCircle className="w-2.5 h-2.5" /> Failed
          </span>
        );
    }
  };

  const formatTimestamp = (isoString) => {
    if (!isoString) return '';
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  const handleDeleteClick = (e, taskId) => {
    e.stopPropagation();
    if (deletingTaskId === taskId) {
      // Confirmed delete
      onDeleteTask(taskId);
      setDeletingTaskId(null);
    } else {
      setDeletingTaskId(taskId);
      // Auto-reset confirmation after 4s
      setTimeout(() => {
        setDeletingTaskId((current) => (current === taskId ? null : current));
      }, 4000);
    }
  };

  return (
    <aside className="w-64 md:w-72 h-full bg-[#0b0f19] border-r border-slate-800/80 flex flex-col justify-between flex-shrink-0 select-none">
      {/* Top Section: Brand & New Chat */}
      <div className="p-4 border-b border-slate-800/80">
        {/* Brand */}
        <div className="flex items-center gap-2.5 mb-5 px-1">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-500 text-white flex items-center justify-center shadow-lg shadow-blue-900/30">
            <Terminal className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-100 tracking-tight flex items-center gap-1.5">
              CLI Agent AI
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-blue-950/80 text-blue-400 border border-blue-800/50">
                v1.0
              </span>
            </h1>
            <p className="text-[11px] text-slate-400">Conversational CLI Platform</p>
          </div>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 active:scale-[0.99] text-white text-xs font-semibold shadow-md shadow-blue-900/30 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Middle Section: Task History (SQLite-backed) */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5">
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-2 mb-2 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Database className="w-3 h-3 text-cyan-400" />
            Task History
          </span>
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-mono text-slate-500 mr-1">{tasks.length}</span>
            <button
              onClick={onRefreshHistory}
              disabled={historyLoading}
              className={`p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors ${
                historyLoading ? 'animate-spin text-blue-400' : ''
              }`}
              title="Refresh task history from SQLite"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Loading state */}
        {historyLoading && tasks.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-slate-500 animate-pulse">
            Loading persistent task history...
          </div>
        )}

        {/* Error state */}
        {historyError && (
          <div className="p-2.5 rounded-lg bg-rose-950/30 border border-rose-900/40 text-xs text-rose-300">
            <div className="font-medium text-[11px] mb-0.5">Database Error</div>
            <p className="text-[10px] text-rose-400">{historyError}</p>
          </div>
        )}

        {/* Empty history state */}
        {!historyLoading && tasks.length === 0 && !historyError && (
          <div className="px-3 py-8 text-center">
            <Database className="w-7 h-7 text-slate-700 mx-auto mb-2 opacity-40" />
            <p className="text-xs text-slate-400">No previous tasks</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Execute a crawl to record history in SQLite</p>
          </div>
        )}

        {/* Task Items */}
        {tasks.map((t) => {
          const isActive = t.id === activeTaskId;
          const isConfirmingDelete = deletingTaskId === t.id;

          return (
            <div
              key={t.id}
              onClick={() => onSelectTask(t.id)}
              className={`group relative p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                isActive
                  ? 'bg-slate-800/90 text-white border-blue-500/50 shadow-md shadow-blue-950/30'
                  : 'bg-slate-900/50 text-slate-300 border-slate-800/60 hover:bg-slate-800/60 hover:border-slate-700/60'
              }`}
            >
              {/* Top row: Status and Duration */}
              <div className="flex items-center justify-between mb-1.5">
                {getStatusBadge(t.status)}
                <div className="flex items-center gap-1 text-[10px] font-mono text-slate-400">
                  <span>{t.execution_duration ? `${t.execution_duration}s` : ''}</span>
                  <span>•</span>
                  <span>{formatTimestamp(t.created_at)}</span>
                </div>
              </div>

              {/* URL or prompt snippet */}
              <div className="font-medium truncate text-slate-200 mb-1 flex items-center gap-1.5">
                {t.target_url ? (
                  <>
                    <Globe className="w-3 h-3 text-cyan-400 flex-shrink-0" />
                    <span className="truncate">{t.target_url}</span>
                  </>
                ) : (
                  <span className="truncate">{t.user_message}</span>
                )}
              </div>

              {/* Bottom row: Shortened ID and Delete action */}
              <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[10px] text-slate-500 font-mono">
                <span>#{t.id.slice(0, 10)}</span>
                <button
                  onClick={(e) => handleDeleteClick(e, t.id)}
                  className={`p-1 rounded transition-colors ${
                    isConfirmingDelete
                      ? 'bg-rose-600 text-white font-sans text-[10px] px-2'
                      : 'hover:text-rose-400 hover:bg-slate-800 opacity-0 group-hover:opacity-100'
                  }`}
                  title={isConfirmingDelete ? 'Click again to confirm delete' : 'Delete task'}
                >
                  {isConfirmingDelete ? 'Confirm?' : <Trash2 className="w-3 h-3" />}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom Section: Settings & Backend Health Indicator */}
      <div className="p-3 border-t border-slate-800/80 space-y-2 bg-[#090d16]">
        {/* Settings Info Card */}
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/60 space-y-1.5 text-[11px]">
          <div className="flex items-center justify-between text-slate-400 font-medium">
            <span className="flex items-center gap-1.5">
              <Settings className="w-3.5 h-3.5 text-slate-400" />
              Settings
            </span>
            <span className="text-[10px] font-mono text-emerald-400">SQLite Active</span>
          </div>
          <div className="flex justify-between text-slate-400 text-[10px]">
            <span>AI Model:</span>
            <span className="font-mono text-slate-300">Groq (Llama-3.3)</span>
          </div>
          <div className="flex justify-between text-slate-400 text-[10px]">
            <span>Database:</span>
            <span className="font-mono text-slate-300">backend/cli_agent.db</span>
          </div>
        </div>

        {/* Backend Connection Indicator */}
        <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <div>
              <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                Backend Status
              </div>
              <StatusIndicator
                status={isBackendOnline ? 'online' : backendLoading ? 'busy' : 'offline'}
                label={
                  isBackendOnline
                    ? 'Connected (Healthy)'
                    : backendLoading
                    ? 'Connecting...'
                    : 'Disconnected'
                }
                size="xs"
              />
            </div>
          </div>
          <button
            onClick={onRefreshBackend}
            disabled={backendLoading}
            className={`p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors ${
              backendLoading ? 'animate-spin text-blue-400' : ''
            }`}
            title="Refresh connection status"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
