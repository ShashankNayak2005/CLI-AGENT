import React, { useRef, useEffect } from 'react';
import { Terminal, Sparkles, Shield, Cpu } from 'lucide-react';
import MessageBubble from './MessageBubble';
import ExamplePrompts from './ExamplePrompts';
import ChatInput from './ChatInput';

export const ChatWindow = ({
  messages = [],
  input = '',
  setInput,
  onSendMessage,
  onSelectPrompt,
  onApprovePlan,
  onCancelPlan,
  isLoading = false,
  agentMode = true,
  setAgentMode,
}) => {
  const messagesEndRef = useRef(null);

  // Auto scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex-1 flex flex-col h-full bg-[#080c14] overflow-hidden relative">
      {/* Top Bar */}
      <header className="h-14 border-b border-slate-800/80 px-6 flex items-center justify-between bg-slate-950/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-blue-950/60 text-blue-400 border border-blue-800/30">
            <Terminal className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-semibold text-slate-300">
            Interactive Agent Console
          </span>
          <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
            • PowerShell / Windows 11 Native
          </span>
        </div>

        <div className="flex items-center gap-2">
          {setAgentMode && (
            <button
              onClick={() => setAgentMode(!agentMode)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition-all ${
                agentMode
                  ? 'bg-purple-950/60 border-purple-500/50 text-purple-300 shadow-sm'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
              title="Toggle Autonomous Multi-Step Planning (Phase 5)"
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>{agentMode ? 'Autonomous Multi-Step Agent' : 'Direct CLI Execution'}</span>
            </button>
          )}

          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-slate-400 flex items-center gap-1.5">
            <Shield className="w-3 h-3 text-emerald-400" />
            Zero-Simulation Active
          </span>
        </div>
      </header>

      {/* Main Scrollable Content */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 flex flex-col justify-between">
        {isEmpty ? (
          <div className="flex-1 flex flex-col items-center justify-center max-w-3xl mx-auto text-center px-4 py-8 my-auto">
            {/* Header Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-950/50 border border-blue-800/40 text-blue-400 text-xs font-medium mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              BuildSprint Round 2 Implementation Foundation
            </div>

            {/* Welcome Heading */}
            <h2 className="text-3xl md:text-4xl font-extrabold text-slate-100 tracking-tight mb-3">
              What would you like me to execute?
            </h2>

            {/* Description explaining the AI CLI Agent */}
            <p className="text-sm md:text-base text-slate-400 max-w-xl mx-auto leading-relaxed mb-8">
              CLI Agent AI is an AI-powered conversational platform that converts natural-language instructions into controlled, verified command-line executions.
            </p>

            {/* Three Example Prompt Cards */}
            <ExamplePrompts onSelectPrompt={onSelectPrompt} />
          </div>
        ) : (
          <div className="w-full max-w-4xl mx-auto space-y-4 pb-4">
            {messages.map((msg, index) => (
              <MessageBubble
                key={msg.id || index}
                message={msg}
                onApprovePlan={onApprovePlan}
                onCancelPlan={onCancelPlan}
              />
            ))}

            {isLoading && (
              <div className="flex items-center gap-3 py-3 px-4">
                <div className="w-8 h-8 rounded-lg bg-blue-950/70 border border-blue-800/40 text-blue-400 flex items-center justify-center animate-pulse">
                  <Terminal className="w-4 h-4" />
                </div>
                <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                  Analyzing instruction and validating command tokens...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-800/80 bg-[#080c14]/95 backdrop-blur-md">
        <ChatInput
          input={input}
          setInput={setInput}
          onSend={onSendMessage}
          disabled={isLoading}
        />
      </div>
    </div>
  );
};

export default ChatWindow;

