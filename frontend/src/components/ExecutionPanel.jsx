import React from 'react';
import {
  Terminal,
  Activity,
  Clock,
  AlertCircle,
  Shield,
  Cpu,
  FileCode,
  Globe,
  Hash,
  CheckCircle2,
  XCircle,
  FileText,
} from 'lucide-react';
import StatusIndicator from './StatusIndicator';

export const ExecutionPanel = ({
  taskStatus = 'Idle',
  cliStatus = 'Ready / No process active',
  duration = '0.00s',
  outputPreview = 'No active execution output.',
  errorDisplay = 'None',
  isCollapsed = false,
  // Detailed Execution Props
  operation = 'N/A',
  targetUrl = 'None',
  exitCode = 'N/A',
  pagesCrawled = 0,
  pagesFailed = 0,
  outputValidation = 'N/A',
  taskId = 'None',
}) => {
  const isCompleted = taskStatus === 'Completed' || taskStatus === 'completed';
  const isFailed =
    taskStatus === 'Failed' ||
    taskStatus === 'failed' ||
    taskStatus === 'Rejected' ||
    taskStatus === 'rejected' ||
    taskStatus === 'Timeout' ||
    taskStatus === 'timeout' ||
    taskStatus === 'invalid_output';
  const isRunning = taskStatus === 'Running' || taskStatus === 'running';

  return (
    <aside
      className={`border-l border-slate-800/80 bg-[#070b13] flex flex-col transition-all duration-300 ${
        isCollapsed ? 'w-12' : 'w-80 lg:w-96'
      } h-full select-none`}
    >
      {/* Panel Header */}
      <div className="h-14 border-b border-slate-800/80 px-4 flex items-center justify-between bg-slate-950/40">
        {!isCollapsed && (
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Execution Telemetry
            </h3>
          </div>
        )}
        <div className="flex items-center gap-2 ml-auto">
          <StatusIndicator
            status={
              isRunning
                ? 'busy'
                : isCompleted
                ? 'online'
                : isFailed
                ? 'error'
                : 'idle'
            }
            size="xs"
            label={!isCollapsed ? taskStatus : undefined}
          />
        </div>
      </div>

      {!isCollapsed && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Status Metrics Cards */}
          <div className="grid grid-cols-2 gap-2.5">
            {/* Task Status */}
            <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800/70">
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">
                <Activity className="w-3.5 h-3.5 text-blue-400" />
                Execution Status
              </div>
              <div
                className={`text-sm font-semibold font-mono flex items-center gap-1.5 ${
                  isCompleted
                    ? 'text-emerald-400'
                    : isFailed
                    ? 'text-rose-400'
                    : isRunning
                    ? 'text-amber-400'
                    : 'text-slate-200'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full inline-block ${
                    isCompleted
                      ? 'bg-emerald-500'
                      : isFailed
                      ? 'bg-rose-500'
                      : isRunning
                      ? 'bg-amber-500 animate-ping'
                      : 'bg-slate-500'
                  }`}
                />
                {taskStatus}
              </div>
            </div>

            {/* Duration */}
            <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800/70">
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">
                <Clock className="w-3.5 h-3.5 text-blue-400" />
                Duration
              </div>
              <div className="text-sm font-semibold text-slate-200 font-mono">
                {duration}
              </div>
            </div>
          </div>

          {/* Section: Structured Execution Details */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 pb-1 border-b border-slate-800/80">
              <FileCode className="w-3.5 h-3.5 text-blue-400" />
              Execution Details
            </div>

            <div className="space-y-1.5 text-[11px] font-mono">
              <div className="flex items-center justify-between text-slate-400">
                <span>Operation:</span>
                <span className="text-blue-300 font-semibold">{operation}</span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Target URL:</span>
                <span className="text-sky-300 truncate max-w-[170px]" title={targetUrl}>
                  {targetUrl}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Execution status:</span>
                <span
                  className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold ${
                    isCompleted
                      ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/40'
                      : isFailed
                      ? 'bg-rose-950/60 text-rose-300 border border-rose-800/40'
                      : isRunning
                      ? 'bg-amber-950/60 text-amber-300 border border-amber-800/40'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {taskStatus}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Exit code:</span>
                <span className={exitCode === 0 || exitCode === '0' ? 'text-emerald-400 font-bold' : 'text-slate-300'}>
                  {exitCode}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Execution duration:</span>
                <span className="text-slate-200">{duration}</span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Pages crawled:</span>
                <span className="text-emerald-300">{pagesCrawled}</span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Pages failed:</span>
                <span className={pagesFailed > 0 ? 'text-rose-400' : 'text-slate-400'}>
                  {pagesFailed}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400">
                <span>Output validation:</span>
                <span className="text-emerald-400 truncate max-w-[150px]" title={outputValidation}>
                  {outputValidation}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400 pt-1 border-t border-slate-800/60">
                <span>Task ID:</span>
                <span className="text-slate-400 text-[10px] truncate max-w-[160px]" title={taskId}>
                  {taskId}
                </span>
              </div>
            </div>
          </div>

          {/* CLI Execution Process Status */}
          <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/70">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-blue-400" />
                CLI Process
              </span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/30">
                shell=False
              </span>
            </div>
            <div className="text-xs text-slate-300 font-mono bg-slate-950/70 p-2 rounded-lg border border-slate-800/60 break-all leading-relaxed">
              {cliStatus}
            </div>
          </div>

          {/* Terminal Output Preview */}
          <div className="flex flex-col flex-1">
            <div className="flex items-center justify-between text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">
              <span className="flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                Stdout / Stderr Output
              </span>
              <span className="text-[10px] text-slate-400 font-mono">
                {isCompleted ? 'Captured' : isRunning ? 'Streaming' : 'Idle'}
              </span>
            </div>
            <div className="relative rounded-xl bg-black/80 border border-slate-800 p-3 font-mono-code text-xs text-slate-300 min-h-[160px] flex flex-col justify-between overflow-hidden shadow-inner">
              <div className="space-y-1 overflow-y-auto max-h-48">
                <div className="text-[11px] text-slate-500 select-none pb-1 border-b border-slate-900 flex items-center justify-between">
                  <span>pty: subprocess.PIPE</span>
                  <span>Exit: {isCompleted ? '0' : isFailed ? 'Non-Zero' : '-'}</span>
                </div>
                <pre className="pt-2 text-slate-300 whitespace-pre-wrap font-mono-code text-[11px]">
                  {outputPreview}
                </pre>
              </div>
              <div className="text-[10px] text-slate-500 select-none pt-2 border-t border-slate-900/80 flex items-center justify-between">
                <span>Buffer: {Math.round(outputPreview.length / 1024 * 10) / 10} KB</span>
                <span className={isRunning ? 'text-amber-400' : 'text-blue-500/70'}>
                  {isRunning ? 'Executing CLI process...' : isCompleted ? 'Subprocess Terminated' : 'Awaiting user trigger'}
                </span>
              </div>
            </div>
          </div>

          {/* Error Display Area */}
          <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/70">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
              Error Diagnostics
            </div>
            <div className="text-xs font-mono text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/50 break-words">
              {errorDisplay === 'None' ? (
                <span className="text-slate-500">No active execution errors.</span>
              ) : (
                <span className="text-rose-400 font-semibold">{errorDisplay}</span>
              )}
            </div>
          </div>

          {/* Security & Runtime Mode Notice */}
          <div className="p-3 rounded-xl bg-blue-950/20 border border-blue-900/30 flex items-start gap-2.5 text-xs text-blue-300/80">
            <Shield className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <div className="text-[11px] leading-relaxed">
              <strong className="text-blue-200 block mb-0.5">Controlled Execution Engine</strong>
              Commands execute via strict token arguments with <code className="font-mono text-cyan-300">shell=False</code>. Arbitrary execution is blocked by the intent validator.
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};

export default ExecutionPanel;
