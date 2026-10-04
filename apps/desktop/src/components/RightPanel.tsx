import React from 'react';
import {
  Monitor,
  Settings as GearIcon,
  Code2,
  FileSearch,
  Activity as PulseIcon,
  Trash2,
  RefreshCw,
  CheckCircle2,
  ChevronRight
} from 'lucide-react';
import { SystemStatus, ActionItem } from '../services/api';

interface RightPanelProps {
  systemStatus: SystemStatus | null;
  recentActions: ActionItem[];
  onActionClick?: (action: ActionItem) => void;
  onNavigateToPCControl?: () => void;
}

export const RightPanel: React.FC<RightPanelProps> = ({
  systemStatus,
  recentActions,
  onActionClick,
  onNavigateToPCControl
}) => {
  const metrics = systemStatus?.metrics || {
    cpu_percent: 18,
    ram_percent: 42,
    storage_percent: 63,
    gpu_percent: 28
  };

  return (
    <aside className="w-[320px] h-full flex flex-col justify-between p-4 bg-[#070b14]/90 border-l border-slate-800/60 overflow-y-auto select-none">
      <div>
        {/* Section 1: PC Control Header */}
        <div className="flex items-center justify-between mb-3 px-1">
          <div className="flex items-center space-x-2">
            <Monitor size={16} className="text-cyan-400" />
            <span className="text-sm font-bold text-white tracking-wide">PC Control</span>
          </div>
          <button
            onClick={onNavigateToPCControl}
            className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center space-x-0.5"
          >
            <span>See All</span>
            <ChevronRight size={12} />
          </button>
        </div>

        {/* Active Task Cards (Matching Reference Image) */}
        <div className="space-y-2 mb-6">
          {/* Card 1: Scanning system (78%) */}
          <div className="p-3 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between glass-card-hover">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-xl bg-blue-950/60 flex items-center justify-center text-cyan-400 border border-blue-500/20">
                <GearIcon size={16} />
              </div>
              <div className="max-w-[170px]">
                <div className="text-xs font-semibold text-slate-100">Scanning system</div>
                <div className="text-[10px] text-slate-400 truncate">
                  Checking performance, storage, and system health...
                </div>
              </div>
            </div>
            {/* Circular Progress (78%) */}
            <div className="relative flex items-center justify-center w-8 h-8">
              <svg className="w-8 h-8 transform -rotate-90">
                <circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="2.5" className="text-slate-800" fill="transparent" />
                <circle
                  cx="16"
                  cy="16"
                  r="13"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeDasharray={81.68}
                  strokeDashoffset={81.68 * (1 - 0.78)}
                  strokeLinecap="round"
                  className="text-cyan-400 drop-shadow-[0_0_4px_#22d3ee]"
                  fill="transparent"
                />
              </svg>
              <span className="absolute text-[8px] font-bold text-white">78%</span>
            </div>
          </div>

          {/* Card 2: Opening VS Code (Completed checkmark) */}
          <div className="p-3 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between glass-card-hover">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-xl bg-blue-900/40 flex items-center justify-center text-blue-400 border border-blue-500/20">
                <Code2 size={16} />
              </div>
              <div className="max-w-[190px]">
                <div className="text-xs font-semibold text-slate-100">Opening VS Code</div>
                <div className="text-[10px] text-slate-400 truncate">Launching application...</div>
              </div>
            </div>
            <div className="w-5 h-5 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
              <CheckCircle2 size={13} />
            </div>
          </div>

          {/* Card 3: Checking errors (Spinner) */}
          <div className="p-3 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between glass-card-hover">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-xl bg-indigo-950/60 flex items-center justify-center text-indigo-400 border border-indigo-500/20">
                <FileSearch size={16} />
              </div>
              <div className="max-w-[190px]">
                <div className="text-xs font-semibold text-slate-100">Checking errors</div>
                <div className="text-[10px] text-slate-400 truncate">Scanning project files...</div>
              </div>
            </div>
            <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
          </div>

          {/* Card 4: Running diagnostics (Spinner) */}
          <div className="p-3 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between glass-card-hover">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-xl bg-purple-950/60 flex items-center justify-center text-purple-400 border border-purple-500/20">
                <PulseIcon size={16} />
              </div>
              <div className="max-w-[190px]">
                <div className="text-xs font-semibold text-slate-100">Running diagnostics</div>
                <div className="text-[10px] text-slate-400 truncate">Analyzing system state...</div>
              </div>
            </div>
            <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
          </div>
        </div>

        {/* Section 2: Recent Actions (Matching Reference Image) */}
        <div className="flex items-center justify-between mb-2.5 px-1">
          <span className="text-xs font-bold text-white tracking-wide">Recent actions</span>
          <button
            onClick={onNavigateToPCControl}
            className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center space-x-0.5"
          >
            <span>See All</span>
            <ChevronRight size={12} />
          </button>
        </div>

        <div className="space-y-2 mb-6">
          {recentActions && recentActions.length > 0 ? (
            recentActions.slice(0, 5).map((act, i) => (
              <div
                key={act.action_id || i}
                onClick={() => onActionClick && onActionClick(act)}
                className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/40 cursor-pointer transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-lg bg-slate-800/80 flex items-center justify-center text-slate-300">
                    {act.tool_name.includes('application') ? (
                      <Code2 size={14} className="text-blue-400" />
                    ) : act.tool_name.includes('project') ? (
                      <FileSearch size={14} className="text-indigo-400" />
                    ) : act.tool_name.includes('temp') ? (
                      <Trash2 size={14} className="text-cyan-400" />
                    ) : (
                      <GearIcon size={14} className="text-slate-400" />
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-200">{act.summary}</div>
                    <div className="text-[10px] text-slate-500">Just now</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={11} />
                </div>
              </div>
            ))
          ) : (
            <>
              {/* Default Mock List Matching Reference Image */}
              <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/40 cursor-pointer">
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-lg bg-blue-950/60 flex items-center justify-center text-blue-400">
                    <Code2 size={14} />
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-200">Opened VS Code</div>
                    <div className="text-[10px] text-slate-500">2 min ago</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={11} />
                </div>
              </div>

              <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/40 cursor-pointer">
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-lg bg-indigo-950/60 flex items-center justify-center text-indigo-400">
                    <FileSearch size={14} />
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-200">Scanned project for errors</div>
                    <div className="text-[10px] text-slate-500">2 min ago</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={11} />
                </div>
              </div>

              <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/40 cursor-pointer">
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-lg bg-slate-800/60 flex items-center justify-center text-slate-400">
                    <GearIcon size={14} />
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-200">Checked system performance</div>
                    <div className="text-[10px] text-slate-500">12 min ago</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={11} />
                </div>
              </div>

              <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/40 cursor-pointer">
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-lg bg-red-950/40 flex items-center justify-center text-cyan-400">
                    <Trash2 size={14} />
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-200">Cleared 1.2 GB of temp files</div>
                    <div className="text-[10px] text-slate-500">28 min ago</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={11} />
                </div>
              </div>

              <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800/40 cursor-pointer">
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-lg bg-slate-800/60 flex items-center justify-center text-cyan-400">
                    <RefreshCw size={14} />
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-200">Updated 3 applications</div>
                    <div className="text-[10px] text-slate-500">1 hour ago</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={11} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Section 3: System Status (Real Metrics with Sparkline Waves) */}
      <div className="pt-3 border-t border-slate-800/60">
        <div className="flex items-center justify-between mb-3 px-1">
          <span className="text-xs font-bold text-white tracking-wide">System Status</span>
          <div className="flex items-center space-x-1.5 text-xs text-emerald-400 font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
            <span className="text-[11px]">Healthy</span>
          </div>
        </div>

        {/* 4 Sparkline Metric Cards (CPU, RAM, Storage, GPU) */}
        <div className="grid grid-cols-4 gap-2">
          {/* CPU Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">CPU</div>
            <div className="text-xs font-bold text-white my-1">{metrics.cpu_percent}%</div>
            {/* Sparkline Wave */}
            <svg className="w-full h-5 text-blue-400" viewBox="0 0 40 16" fill="none">
              <path d="M0 12 Q 10 4, 20 10 T 40 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>

          {/* RAM Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">RAM</div>
            <div className="text-xs font-bold text-white my-1">{metrics.ram_percent}%</div>
            {/* Sparkline Wave */}
            <svg className="w-full h-5 text-purple-400" viewBox="0 0 40 16" fill="none">
              <path d="M0 8 Q 10 14, 20 6 T 40 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>

          {/* Storage Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">Storage</div>
            <div className="text-xs font-bold text-white my-1">{metrics.storage_percent}%</div>
            {/* Sparkline Wave */}
            <svg className="w-full h-5 text-cyan-400" viewBox="0 0 40 16" fill="none">
              <path d="M0 10 Q 10 5, 20 9 T 40 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>

          {/* GPU Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">GPU</div>
            <div className="text-xs font-bold text-white my-1">{metrics.gpu_percent}%</div>
            {/* Sparkline Wave */}
            <svg className="w-full h-5 text-teal-400" viewBox="0 0 40 16" fill="none">
              <path d="M0 6 Q 10 12, 20 5 T 40 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        </div>
      </div>
    </aside>
  );
};
