import React from 'react';

/**
 * StatusIndicator Component
 * Renders an accessible, pulsating or solid status dot with text label.
 */
export const StatusIndicator = ({ status = 'idle', label, pulse = true, size = 'sm' }) => {
  const getStatusStyles = () => {
    switch (status) {
      case 'online':
      case 'healthy':
      case 'ready':
        return {
          dot: 'bg-emerald-500',
          ping: 'bg-emerald-400',
          text: 'text-emerald-400',
        };
      case 'offline':
      case 'error':
        return {
          dot: 'bg-rose-500',
          ping: 'bg-rose-400',
          text: 'text-rose-400',
        };
      case 'busy':
      case 'running':
        return {
          dot: 'bg-amber-500',
          ping: 'bg-amber-400',
          text: 'text-amber-400',
        };
      case 'idle':
      default:
        return {
          dot: 'bg-slate-400',
          ping: 'bg-slate-400',
          text: 'text-slate-400',
        };
    }
  };

  const styles = getStatusStyles();
  const sizeClass = size === 'xs' ? 'w-1.5 h-1.5' : size === 'lg' ? 'w-3 h-3' : 'w-2 h-2';

  return (
    <div className="inline-flex items-center gap-2" title={label}>
      <span className="relative flex items-center justify-center">
        {pulse && (status === 'online' || status === 'busy') && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${styles.ping}`} />
        )}
        <span className={`relative inline-flex rounded-full ${sizeClass} ${styles.dot}`} />
      </span>
      {label && <span className={`text-xs font-medium ${styles.text}`}>{label}</span>}
    </div>
  );
};

export default StatusIndicator;

