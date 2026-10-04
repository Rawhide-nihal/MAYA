import React, { useEffect, useState } from 'react';
import { FolderKanban, Play, Terminal, ShieldCheck, GitBranch, Code } from 'lucide-react';
import { MayaApi } from '../services/api';

export const ProjectsPage: React.FC = () => {
  const [projectData, setProjectData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  useEffect(() => {
    MayaApi.getProjects().then(data => {
      setProjectData(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleOpenVSCode = async () => {
    setActionStatus('Launching VS Code...');
    try {
      const res = await MayaApi.sendChatMessage('Open VS Code');
      setActionStatus(res.reply);
    } catch (e: any) {
      setActionStatus(`Error: ${e.message}`);
    }
  };

  const handleScanProject = async () => {
    setActionStatus('Scanning project for errors...');
    try {
      const res = await MayaApi.sendChatMessage('Check my project for errors');
      setActionStatus(res.reply);
    } catch (e: any) {
      setActionStatus(`Error: ${e.message}`);
    }
  };

  const active = projectData?.active_project;

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <FolderKanban className="text-cyan-400" />
            <span>Developer Projects</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real workspace detection, build environment inspection, and diagnostics.
          </p>
        </div>
      </div>

      {actionStatus && (
        <div className="mb-4 p-3 rounded-xl bg-blue-950/60 border border-blue-500/30 text-cyan-300 text-xs flex items-center justify-between">
          <span>{actionStatus}</span>
          <button onClick={() => setActionStatus(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
          Inspecting workspace...
        </div>
      ) : active ? (
        <div className="space-y-4">
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-semibold text-cyan-400 uppercase tracking-widest">Active Workspace</span>
                <h3 className="text-lg font-bold text-white mt-1">{active.project_name}</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{active.project_path}</p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleOpenVSCode}
                  className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md flex items-center space-x-1.5 transition-colors"
                >
                  <Code size={14} />
                  <span>Open in VS Code</span>
                </button>
                <button
                  onClick={handleScanProject}
                  className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold border border-slate-700 flex items-center space-x-1.5 transition-colors"
                >
                  <Play size={14} />
                  <span>Run Error Scan</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 pt-2">
              <div className="p-3 rounded-xl glass-panel-subtle">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Languages</span>
                <div className="text-xs font-bold text-slate-200 mt-1">
                  {active.languages ? active.languages.join(', ') : 'Python / TypeScript'}
                </div>
              </div>

              <div className="p-3 rounded-xl glass-panel-subtle">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Build System</span>
                <div className="text-xs font-bold text-slate-200 mt-1">
                  {active.build_systems ? active.build_systems.join(', ') : 'Vite / Pip'}
                </div>
              </div>

              <div className="p-3 rounded-xl glass-panel-subtle">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Git Branch</span>
                <div className="text-xs font-bold text-slate-200 mt-1 flex items-center space-x-1">
                  <GitBranch size={12} className="text-cyan-400" />
                  <span>{active.git_branch || 'main'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-xs text-slate-400">No active project detected.</div>
      )}
    </div>
  );
};
