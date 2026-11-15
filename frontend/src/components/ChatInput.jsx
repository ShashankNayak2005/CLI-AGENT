import React, { useRef, useEffect } from 'react';
import { Send, CornerDownLeft, Terminal } from 'lucide-react';

export const ChatInput = ({ input, setInput, onSend, disabled = false, placeholder = "Enter natural-language instruction (e.g. 'Crawl https://example.com and summarize it')..." }) => {
  const textareaRef = useRef(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !disabled) {
        onSend();
      }
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (input.trim() && !disabled) {
            onSend();
          }
        }}
        className="relative flex items-end gap-2 p-2 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl focus-within:border-blue-500/60 focus-within:ring-2 focus-within:ring-blue-500/20 transition-all"
      >
        <div className="pl-2 pb-2.5 text-slate-400 select-none hidden sm:flex items-center">
          <Terminal className="w-4 h-4 text-blue-400" />
        </div>

        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1 max-h-36 py-2 px-2 bg-transparent text-slate-100 placeholder-slate-400 text-sm resize-none focus:outline-none leading-relaxed font-sans"
        />

        <div className="flex items-center gap-1.5 pb-1 pr-1">
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            className={`p-2.5 rounded-xl transition-all duration-150 flex items-center justify-center ${
              input.trim() && !disabled
                ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-900/40 active:scale-95'
                : 'bg-slate-800/80 text-slate-400 cursor-not-allowed'
            }`}
            title="Execute (Enter)"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>

      <div className="flex items-center justify-between px-2 pt-2 text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <CornerDownLeft className="w-3 h-3" />
          Press <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">Enter</kbd> to submit, <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">Shift+Enter</kbd> for new line
        </span>
        <span className="font-mono text-slate-400">Phase 1 Foundation</span>
      </div>
    </div>
  );
};

export default ChatInput;

