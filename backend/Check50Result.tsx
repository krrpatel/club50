import React from 'react';
import { CheckCircle2, XCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { TestResult } from '../lib/api';
import { useState } from 'react';

interface Props {
  result: TestResult;
}

export const Check50Result: React.FC<Props> = ({ result }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border-b border-slate-800 last:border-0">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center gap-3 py-3 text-left transition hover:bg-slate-900/50 px-2"
      >
        {result.passed ? (
          <span className="text-green-500 font-bold text-lg">: )</span>
        ) : (
          <span className="text-red-500 font-bold text-lg">: (</span>
        )}
        <span className="flex-1 text-sm font-medium text-slate-200">{result.label}</span>
        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      
      {isExpanded && (
        <div className="bg-slate-950/50 p-4 text-xs font-mono space-y-3 border-t border-slate-800">
          {result.expected && (
            <div>
              <p className="text-slate-500 uppercase mb-1 font-sans font-bold tracking-wider">Expected</p>
              <pre className="text-green-400 whitespace-pre-wrap">{result.expected}</pre>
            </div>
          )}
          {result.got && (
            <div>
              <p className="text-slate-500 uppercase mb-1 font-sans font-bold tracking-wider">Actual</p>
              <pre className="text-red-400 whitespace-pre-wrap">{result.got}</pre>
            </div>
          )}
          {result.hint && (
            <div className="rounded border border-brand-500/20 bg-brand-500/5 p-2 text-brand-300 italic">
              Hint: {result.hint}
            </div>
          )}
        </div>
      )}
    </div>
  );
};