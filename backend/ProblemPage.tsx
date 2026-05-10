import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { Play, Send, Terminal, Code2, BookOpen } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { fetchProblemDetail, runCheck, submitCode, TestResult } from '../lib/api';
import { Check50Result } from '../components/Check50Result';
import { LoadingPage } from '../components/LoadingPage';
import { useAppStore } from '../store/useAppStore';

export default function ProblemPage() {
  const { problemId } = useParams();
  const navigate = useNavigate();
  const selectedLanguage = useAppStore(state => state.selectedLanguage);
  const setLanguage = useAppStore(state => state.setLanguage);
  
  const [code, setCode] = useState('');
  const [results, setResults] = useState<TestResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: problem, isLoading } = useQuery({
    queryKey: ['problem', problemId],
    queryFn: () => fetchProblemDetail(problemId!),
    enabled: !!problemId,
  });

  const handleRunCheck = async () => {
    setIsRunning(true);
    try {
      const res = await runCheck({ problem_id: problemId!, code, language: selectedLanguage });
      setResults(res.results);
    } catch (e) {
      console.error(e);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const res = await submitCode({ problem_id: problemId!, code, language: selectedLanguage, username: 'student_web' });
      navigate(`/submissions/${res.submission_id}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) return <LoadingPage />;
  if (!problem) return <div className="p-8 text-white">Problem not found.</div>;

  return (
    <div className="flex h-[calc(100vh-64px)] w-full overflow-hidden bg-slate-950">
      {/* Left: Problem Description */}
      <div className="w-2/5 overflow-y-auto border-r border-slate-800 p-6 text-slate-200 custom-scrollbar">
        <div className="mb-6 flex items-center gap-2">
          <BookOpen size={18} className="text-brand-400" />
          <span className="rounded bg-brand-500/20 px-2 py-1 text-xs font-bold text-brand-400">
            {problem.difficulty}
          </span>
        </div>
        <h1 className="mb-6 text-2xl font-bold text-white">{problem.title}</h1>
        <div className="prose prose-invert max-w-none">
          <p className="text-slate-300 leading-relaxed">{problem.description}</p>
          <h3>Constraints</h3>
          <ul>
            {problem.constraints?.map((c: string, i: number) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      </div>

      {/* Right: Editor and Results */}
      <div className="flex flex-1 flex-col">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4 py-2">
            <div className="flex items-center gap-2 text-slate-400">
              <Code2 size={16} />
              <span className="text-xs font-bold uppercase tracking-wider">Editor</span>
            </div>
            <select 
              value={selectedLanguage} 
              onChange={(e) => setLanguage(e.target.value as any)}
              className="bg-transparent text-sm font-medium text-slate-300 outline-none"
            >
              <option value="python">Python</option>
              <option value="cpp">C++</option>
              <option value="java">Java</option>
              <option value="javascript">JavaScript</option>
            </select>
            <div className="flex gap-2">
              <button 
                onClick={handleRunCheck}
                disabled={isRunning}
                className="flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-1.5 text-sm font-semibold hover:bg-slate-700 disabled:opacity-50"
              >
                <Play size={14} /> Run
              </button>
              <button 
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-semibold text-slate-950 hover:bg-brand-400 disabled:opacity-50"
              >
                <Send size={14} /> Submit
              </button>
            </div>
          </div>
          <div className="flex-1">
            <Editor
              height="100%"
              theme="vs-dark"
              language={selectedLanguage}
              value={code}
              onChange={(v) => setCode(v || '')}
              options={{ minimap: { enabled: false }, fontSize: 14 }}
            />
          </div>
        </div>

        {/* Results Panel */}
        <div className="h-1/3 overflow-y-auto border-t border-slate-800 bg-slate-900 custom-scrollbar">
          <div className="sticky top-0 bg-slate-900 p-4 pb-2">
          <div className="mb-4 flex items-center gap-2 text-slate-400">
            <Terminal size={16} />
            <span className="text-xs font-bold uppercase tracking-wider">Results</span>
          </div>
          </div>
          <div className="px-2 pb-4">
            {results.map((res) => (
              <Check50Result key={res.id} result={res} />
            ))}
            {results.length === 0 && !isRunning && (
              <div className="flex flex-col items-center justify-center py-8 opacity-20">
                <Terminal size={48} />
                <p className="mt-2 text-sm">Run code to see public checks.</p>
              </div>
            )}
            {isRunning && <p className="p-4 text-center text-sm text-brand-400 animate-pulse">Running check50...</p>}
        </div>
      </div>
    </div>
  );
}