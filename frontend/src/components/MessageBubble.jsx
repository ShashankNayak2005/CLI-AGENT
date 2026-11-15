import React, { useState } from 'react';
import {
  Terminal,
  User,
  Clock,
  ShieldCheck,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileCode,
  Globe,
  AlertTriangle,
  Info,
  CheckCircle2,
  XCircle,
  Hash,
  Download,
} from 'lucide-react';
import { downloadTaskResult } from '../services/api';
import PlanCard from './PlanCard';

export const MessageBubble = ({ message, onApprovePlan, onCancelPlan }) => {
  const isUser = message.sender === 'user';
  const [copied, setCopied] = React.useState(false);
  const [showJson, setShowJson] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [showPages, setShowPages] = useState(false);

  const handleCopy = (text) => {
    if (text) {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const responseData = message.payload;
  const execution = responseData?.execution;
  const intent = responseData?.intent;
  const result = responseData?.result;
  const summary = result?.website_summary;
  const pages = result?.pages || [];
  const errors = result?.errors || [];

  // Phase 5 Multi-Step Plan object
  const planData = message.plan || responseData?.plan;

  return (
    <div className={`flex w-full gap-3 py-3 px-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-950/70 border border-blue-800/40 text-blue-400 flex items-center justify-center shadow-sm mt-0.5">
          <Terminal className="w-4 h-4" />
        </div>
      )}

      <div
        className={`w-full max-w-[85%] md:max-w-[78%] rounded-2xl p-4 transition-all ${
          isUser
            ? 'bg-blue-600/90 text-white shadow-md shadow-blue-900/20 border border-blue-500/30 rounded-tr-sm'
            : 'bg-slate-900/90 text-slate-200 border border-slate-800/80 shadow-md rounded-tl-sm'
        }`}
      >
        {/* Header: Identity & Timestamp */}
        <div className="flex items-center justify-between gap-4 mb-2 pb-1.5 border-b border-white/10">
          <span className="text-[11px] font-semibold tracking-wide uppercase opacity-75 flex items-center gap-1.5">
            {isUser ? (
              <>
                <User className="w-3 h-3" /> User Instruction
              </>
            ) : (
              <>
                <ShieldCheck className="w-3 h-3 text-emerald-400" /> CLI Agent AI
              </>
            )}
          </span>
          <div className="flex items-center gap-2 text-[10px] opacity-60">
            <span className="flex items-center gap-1 font-mono">
              <Clock className="w-2.5 h-2.5" />
              {message.timestamp || 'Just now'}
            </span>
            <button
              onClick={() => handleCopy(message.text || JSON.stringify(responseData, null, 2))}
              className="hover:opacity-100 transition-opacity p-0.5"
              title="Copy text"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-300" /> : <span className="underline">copy</span>}
            </button>
          </div>
        </div>

        {/* User Prompt Text */}
        {message.text && (
          <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {message.text}
          </div>
        )}

        {/* Phase 5 Multi-Step Plan Card (with Human-in-the-Loop Approval) */}
        {planData && (
          <PlanCard
            plan={planData}
            onApprove={onApprovePlan}
            onCancel={onCancelPlan}
          />
        )}

        {/* Phase 3 Agent Response Card (Single Step Crawl) */}
        {!planData && responseData && (
          <div className="space-y-3 mt-2">
            {/* 1. AI Planning / Intent Header */}
            {intent && (
              <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 font-mono text-[11px]">Intent:</span>
                  <span className="px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/40 text-blue-300 font-mono text-[11px]">
                    {intent.intent}
                  </span>
                  {intent.url && (
                    <a
                      href={intent.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-cyan-400 hover:underline flex items-center gap-1 font-mono text-[11px] truncate max-w-xs"
                    >
                      <Globe className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">{intent.url}</span>
                    </a>
                  )}
                </div>
                {intent.max_pages && (
                  <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                    <span>Pages: {intent.max_pages}</span>
                    <span>Depth: {intent.max_depth}</span>
                  </div>
                )}
              </div>
            )}

            {/* 2. Execution Telemetry Bar */}
            {execution && (
              <div className="p-2.5 rounded-lg bg-slate-950/50 border border-slate-800/60 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
                <div className="flex items-center gap-2">
                  {execution.status === 'completed' ? (
                    <span className="flex items-center gap-1 text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40 text-[11px]">
                      <CheckCircle2 className="w-3 h-3" /> COMPLETED
                    </span>
                  ) : execution.status === 'rejected' ? (
                    <span className="flex items-center gap-1 text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40 text-[11px]">
                      <AlertTriangle className="w-3 h-3" /> REJECTED
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-rose-400 bg-rose-950/40 px-2 py-0.5 rounded border border-rose-800/40 text-[11px]">
                      <XCircle className="w-3 h-3" /> {execution.status.toUpperCase()}
                    </span>
                  )}
                  <span className="text-slate-400 text-[11px]">Exit Code: {execution.exit_code ?? '-'}</span>
                </div>
                <div className="flex items-center gap-3 text-slate-400 text-[11px]">
                  <span>Duration: {execution.duration_seconds}s</span>
                  {result && <span>Crawled: {result.pages_crawled} / Failed: {result.pages_failed}</span>}
                </div>
              </div>
            )}

            {/* 3. Error Banner (if any) */}
            {(!responseData.success || errors.length > 0) && (
              <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/50 text-xs text-rose-300 space-y-1">
                <div className="font-semibold flex items-center gap-1.5 text-rose-200">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  Execution Notice:
                </div>
                <p className="leading-relaxed">{responseData.message}</p>
                {errors.map((err, idx) => (
                  <div key={idx} className="text-[11px] font-mono text-rose-400/90 pl-2 border-l border-rose-800/40 mt-1">
                    [{err.error_type}] {err.url}: {err.message}
                  </div>
                ))}
              </div>
            )}

            {/* 4. Website Summary Card */}
            {summary && (
              <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2 text-xs">
                <div className="flex items-center justify-between border-b border-slate-800/60 pb-1.5">
                  <h4 className="font-semibold text-slate-100 flex items-center gap-1.5">
                    <Globe className="w-3.5 h-3.5 text-blue-400" />
                    {summary.title || 'Website Summary'}
                  </h4>
                  <span className="text-[10px] text-slate-400 font-mono">Actual Crawl Telemetry</span>
                </div>

                {summary.description && (
                  <p className="text-slate-300 leading-relaxed text-xs">
                    {summary.description}
                  </p>
                )}

                {summary.headings && summary.headings.length > 0 && (
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                      Key Headings:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.headings.map((h, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-300 text-[11px] font-mono"
                        >
                          {h}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {summary.main_content && summary.main_content.length > 0 && (
                  <div className="pt-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                      Extracted Text Sample:
                    </span>
                    <div className="space-y-1.5">
                      {summary.main_content.slice(0, 3).map((para, idx) => (
                        <p key={idx} className="text-slate-400 text-xs italic bg-slate-900/40 p-2 rounded border border-slate-800/40">
                          "{para}"
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                {/* Download Validated JSON Result Button */}
                {responseData?.task_id && execution?.status === 'completed' && (
                  <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 font-mono">
                      Task #{responseData.task_id.slice(0, 10)}
                    </span>
                    <button
                      onClick={() => downloadTaskResult(responseData.task_id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-md shadow-blue-950/40 transition-colors"
                      title="Download validated crawl result as JSON"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Result JSON
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* 5. Expandable Sections */}
            <div className="pt-1 space-y-1.5">
              {/* Pages Accordion */}
              {pages.length > 0 && (
                <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/40">
                  <button
                    onClick={() => setShowPages(!showPages)}
                    className="w-full px-3 py-2 text-left text-xs font-medium text-slate-300 hover:bg-slate-800/50 flex items-center justify-between transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      {showPages ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      Crawled Pages ({pages.length})
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">View URLs & Words</span>
                  </button>
                  {showPages && (
                    <div className="p-3 border-t border-slate-800 space-y-2 bg-slate-950/70">
                      {pages.map((p, idx) => (
                        <div key={idx} className="p-2.5 rounded bg-slate-900/60 border border-slate-800/60 space-y-1 text-xs">
                          <div className="flex items-center justify-between font-mono text-[11px]">
                            <span className="text-cyan-300 truncate max-w-sm">{p.url}</span>
                            <span className="text-slate-400">{p.word_count} words</span>
                          </div>
                          <div className="text-slate-300 font-medium">{p.title || 'No Title'}</div>
                          {p.internal_links?.length > 0 && (
                            <div className="text-[10px] text-slate-400 font-mono">
                              Internal links: {p.internal_links.length} | External: {p.external_links?.length || 0}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Raw JSON Output Accordion */}
              {execution?.stdout && (
                <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/40">
                  <button
                    onClick={() => setShowJson(!showJson)}
                    className="w-full px-3 py-2 text-left text-xs font-medium text-slate-300 hover:bg-slate-800/50 flex items-center justify-between transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      {showJson ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      Verified JSON Output (STDOUT)
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {Math.round(execution.stdout.length / 1024 * 10) / 10} KB
                    </span>
                  </button>
                  {showJson && (
                    <div className="p-3 border-t border-slate-800 bg-black/90 font-mono-code text-[11px] overflow-x-auto max-h-72">
                      <pre className="text-emerald-400/90 whitespace-pre">
                        {execution.stdout}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* Subprocess Diagnostics / STDERR Logs Accordion */}
              {execution?.stderr && (
                <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/40">
                  <button
                    onClick={() => setShowLogs(!showLogs)}
                    className="w-full px-3 py-2 text-left text-xs font-medium text-slate-300 hover:bg-slate-800/50 flex items-center justify-between transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      {showLogs ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      CLI Process Diagnostics (STDERR)
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">Telemetry Logs</span>
                  </button>
                  {showLogs && (
                    <div className="p-3 border-t border-slate-800 bg-black/90 font-mono-code text-[11px] overflow-x-auto max-h-48">
                      <pre className="text-slate-400 whitespace-pre">
                        {execution.stderr}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 flex items-center justify-center shadow-sm mt-0.5">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};

export default MessageBubble;
