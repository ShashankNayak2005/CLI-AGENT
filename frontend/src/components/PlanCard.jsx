import React, { useState } from 'react';
import {
  Play,
  X,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileJson,
  Download,
  Loader2,
  ShieldCheck,
  Globe,
  FileText,
  Save,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Ban,
} from 'lucide-react';
import { downloadPlanExport } from '../services/api';

const OPERATION_CONFIG = {
  crawl_website: {
    label: 'Crawl Website',
    icon: Globe,
    color: 'text-sky-400 bg-sky-950/60 border-sky-800/60',
  },
  summarize_crawl: {
    label: 'Summarize Content',
    icon: FileText,
    color: 'text-purple-400 bg-purple-950/60 border-purple-800/60',
  },
  export_json: {
    label: 'Export JSON',
    icon: Save,
    color: 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60',
  },
};

export const PlanCard = ({
  plan,
  onApprove,
  onCancel,
  isExecuting = false,
}) => {
  const [showRawJson, setShowRawJson] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (!plan) return null;

  const { plan_id, goal, steps = [], status, total_duration, final_result, error_message } = plan;

  const isPending = status === 'pending';
  const isRunning = status === 'running' || isExecuting;
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isCancelled = status === 'cancelled';

  const summaryData = final_result?.summary || final_result?.crawl?.website_summary;

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadPlanExport(plan_id);
    } catch (err) {
      alert(`Failed to download exported artifact: ${err.message}`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="w-full rounded-2xl bg-slate-900/95 border border-slate-800/90 shadow-xl overflow-hidden mt-3 transition-all">
      {/* 1. Header Banner */}
      <div className="p-4 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400">
            <ShieldCheck className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white tracking-wide">Multi-Step Execution Plan</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-slate-700/50">
                {plan_id}
              </span>
            </div>
            <p className="text-sm font-semibold text-slate-200 mt-0.5">{goal}</p>
          </div>
        </div>

        {/* Plan Status Badge */}
        <div>
          {isPending && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30 animate-pulse">
              <Clock className="w-3.5 h-3.5" /> Awaiting Approval
            </span>
          )}
          {isRunning && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-300 border border-blue-500/30">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" /> Executing Steps...
            </span>
          )}
          {isCompleted && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
              <CheckCircle2 className="w-3.5 h-3.5" /> Completed ({total_duration ? `${total_duration}s` : 'Success'})
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/30">
              <AlertCircle className="w-3.5 h-3.5" /> Failed
            </span>
          )}
          {isCancelled && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-700/40 text-slate-400 border border-slate-700/60">
              <Ban className="w-3.5 h-3.5" /> Cancelled
            </span>
          )}
        </div>
      </div>

      {/* 2. Step Pipeline Flow */}
      <div className="p-4 space-y-3">
        <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-1">
          Execution Steps ({steps.length})
        </div>

        <div className="space-y-2.5">
          {steps.map((step) => {
            const config = OPERATION_CONFIG[step.operation] || {
              label: step.operation,
              icon: FileText,
              color: 'text-slate-300 bg-slate-800/60 border-slate-700/60',
            };
            const StepIcon = config.icon;

            const isStepRunning = step.status === 'running';
            const isStepCompleted = step.status === 'completed';
            const isStepFailed = step.status === 'failed';
            const isStepSkipped = step.status === 'skipped';

            return (
              <div
                key={step.step_id}
                className={`p-3.5 rounded-xl border transition-all ${
                  isStepRunning
                    ? 'bg-blue-950/20 border-blue-500/50 ring-1 ring-blue-500/20'
                    : isStepCompleted
                    ? 'bg-slate-950/40 border-slate-800/80'
                    : isStepFailed
                    ? 'bg-rose-950/20 border-rose-800/50'
                    : isStepSkipped
                    ? 'bg-slate-950/20 border-slate-900 opacity-60'
                    : 'bg-slate-950/30 border-slate-800/60'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    {/* Step Number Badge */}
                    <span className="flex items-center justify-center w-6 h-6 rounded-lg text-xs font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700/60">
                      {step.step_id}
                    </span>

                    {/* Operation Pill */}
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${config.color}`}
                    >
                      <StepIcon className="w-3.5 h-3.5" />
                      {config.label}
                    </span>

                    {/* Dependencies */}
                    {step.depends_on && step.depends_on.length > 0 && (
                      <span className="text-[11px] text-slate-400 font-mono">
                        depends on: {step.depends_on.map((id) => `Step ${id}`).join(', ')}
                      </span>
                    )}
                  </div>

                  {/* Step Status Indicator */}
                  <div className="text-xs">
                    {step.status === 'pending' && (
                      <span className="text-slate-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> Pending
                      </span>
                    )}
                    {isStepRunning && (
                      <span className="text-blue-400 font-medium flex items-center gap-1 animate-pulse">
                        <Loader2 className="w-3 h-3 animate-spin" /> Running...
                      </span>
                    )}
                    {isStepCompleted && (
                      <span className="text-emerald-400 font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Completed
                        {step.duration_seconds > 0 && ` (${step.duration_seconds}s)`}
                      </span>
                    )}
                    {isStepSkipped && (
                      <span className="text-slate-400 flex items-center gap-1">
                        <Ban className="w-3 h-3" /> Skipped
                      </span>
                    )}
                    {isStepFailed && (
                      <span className="text-rose-400 font-medium flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" /> Failed
                      </span>
                    )}
                  </div>
                </div>

                {/* Step Description */}
                {step.description && (
                  <p className="text-xs text-slate-300 mt-2 pl-8 leading-relaxed">
                    {step.description}
                  </p>
                )}

                {/* Parameters Preview */}
                {step.parameters && Object.keys(step.parameters).length > 0 && (
                  <div className="mt-2 pl-8 flex flex-wrap gap-2 text-[11px] font-mono text-slate-400">
                    {step.parameters.url && (
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-sky-300 truncate max-w-sm">
                        url: {step.parameters.url}
                      </span>
                    )}
                    {step.parameters.max_pages !== undefined && (
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                        max_pages: {step.parameters.max_pages}
                      </span>
                    )}
                    {step.parameters.max_depth !== undefined && (
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                        max_depth: {step.parameters.max_depth}
                      </span>
                    )}
                    {step.parameters.filename && (
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-emerald-300">
                        file: {step.parameters.filename}
                      </span>
                    )}
                  </div>
                )}

                {/* Step Error Details */}
                {step.error && (
                  <div className="mt-2 pl-8 text-xs text-rose-300 bg-rose-950/40 p-2 rounded-lg border border-rose-900/50">
                    {step.error}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Plan Level Error Message */}
        {error_message && (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
            <span>{error_message}</span>
          </div>
        )}

        {/* 3. Human-in-the-Loop Action Bar */}
        {isPending && (
          <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-900/40 mt-4 space-y-3">
            <div className="flex items-center gap-2 text-xs text-blue-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>
                <strong>Human-in-the-Loop Safeguard:</strong> This plan has been verified by the backend. No system operations will execute without your confirmation.
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                onClick={() => onApprove(plan_id)}
                disabled={isRunning}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white shadow-lg shadow-emerald-950/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Executing Plan...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" /> Approve and Execute Plan
                  </>
                )}
              </button>

              <button
                onClick={() => onCancel(plan_id)}
                disabled={isRunning}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 active:scale-95 text-slate-300 hover:text-white border border-slate-700 transition-all disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" /> Cancel Plan
              </button>
            </div>
          </div>
        )}

        {/* 4. Summarization Results Card (Phase 5) */}
        {summaryData && (
          <div className="mt-4 p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-bold text-slate-200">Grounded Website Summary</span>
              </div>
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 transition-colors"
                title="Download exported JSON artifact"
              >
                {downloading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}
                Download Exported JSON
              </button>
            </div>

            {summaryData.website_title && (
              <h4 className="text-sm font-semibold text-white">{summaryData.website_title}</h4>
            )}

            {summaryData.overview && (
              <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded-lg border border-slate-800/80">
                {summaryData.overview}
              </p>
            )}

            {summaryData.key_points && summaryData.key_points.length > 0 && (
              <div>
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">Key Points</span>
                <ul className="mt-1 space-y-1 text-xs text-slate-300">
                  {summaryData.key_points.map((pt, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-purple-400 mt-1">•</span>
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summaryData.source_urls && summaryData.source_urls.length > 0 && (
              <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center gap-2 text-[11px] text-slate-400 font-mono">
                <span>Sources:</span>
                {summaryData.source_urls.map((u, i) => (
                  <a
                    key={i}
                    href={u}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-400 hover:underline flex items-center gap-1"
                  >
                    {u} <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 5. View Raw Plan JSON toggle */}
        <div className="pt-2 border-t border-slate-800/60">
          <button
            onClick={() => setShowRawJson(!showRawJson)}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            {showRawJson ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            <FileJson className="w-3.5 h-3.5 text-slate-400" />
            <span>{showRawJson ? 'Hide Plan JSON' : 'View Plan JSON'}</span>
          </button>

          {showRawJson && (
            <div className="mt-2 p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] text-emerald-400 overflow-x-auto max-h-60">
              <pre>{JSON.stringify(plan, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlanCard;

