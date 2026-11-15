import React from 'react';
import { FileText, Code2, Link2, ArrowUpRight } from 'lucide-react';

const EXAMPLES = [
  {
    id: 1,
    title: 'Multi-Step Autonomous Workflow',
    prompt: 'Visit https://example.com, extract the important information, summarize it, and save the result as JSON.',
    detailedPrompt: 'Visit https://example.com, extract the important information, summarize it, and save the result as JSON.',
    description: 'Autonomous multi-step pipeline: crawl website -> summarize content -> export validated JSON artifact.',
    icon: FileText,
    tag: 'Autonomous Multi-Step',
  },
  {
    id: 2,
    title: 'Crawl & Summarize Content',
    prompt: 'Crawl https://example.com, extract main headings and content, and summarize the key takeaways.',
    detailedPrompt: 'Crawl https://example.com and summarize its core contents.',
    description: 'Scrape web content and synthesize an executive grounded summary using Groq AI.',
    icon: Code2,
    tag: 'Grounded Summary',
  },
  {
    id: 3,
    title: 'Extract & Export to JSON',
    prompt: 'Crawl https://example.com with max 3 pages and export the structured result to JSON.',
    detailedPrompt: 'Analyze https://example.com and collect all important navigation and outbound links.',
    description: 'Inspect anchor elements, extract text, and export validated JSON data.',
    icon: Link2,
    tag: 'JSON Export',
  },
];

export const ExamplePrompts = ({ onSelectPrompt }) => {
  return (
    <div className="w-full max-w-3xl mx-auto my-6">
      <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-3 px-1">
        Suggested Instructions
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {EXAMPLES.map((item) => {
          const IconComponent = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onSelectPrompt(item.prompt)}
              className="group relative flex flex-col justify-between p-4 rounded-xl text-left transition-all duration-200 border border-slate-800/80 bg-slate-900/60 hover:bg-slate-800/60 hover:border-slate-700/80 hover:shadow-lg hover:shadow-blue-950/20 active:scale-[0.99] focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="p-2 rounded-lg bg-slate-800/80 text-blue-400 group-hover:text-blue-300 group-hover:bg-blue-950/50 transition-colors">
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 group-hover:text-slate-300">
                    {item.tag}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-slate-200 group-hover:text-white transition-colors mb-1.5 flex items-center gap-1">
                  {item.title}
                  <ArrowUpRight className="w-3.5 h-3.5 opacity-0 -translate-y-0.5 translate-x-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all text-blue-400" />
                </h4>
                <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                  {item.prompt}
                </p>
              </div>
              <div className="mt-4 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                <span>Click to use</span>
                <span className="text-blue-400/80 group-hover:text-blue-400 font-mono">CLI-ready</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default ExamplePrompts;

