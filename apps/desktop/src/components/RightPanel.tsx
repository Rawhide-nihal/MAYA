import React, { useState, useEffect } from 'react';
import {
  Monitor,
  Settings as GearIcon,
  Code2,
  FileSearch,
  Activity as PulseIcon,
  Trash2,
  RefreshCw,
  CheckCircle2,
  ChevronRight,
  AlertTriangle,
  Play
} from 'lucide-react';
import { SystemStatus, ActionItem } from '../services/api';

export interface ActiveTaskItem {
  id?: string | number;
  step_id?: number;
  name: string;
  description: string;
  tool?: string;
  state?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | string;
  status?: string;
  verified?: boolean;
  progress?: number;
}

interface RightPanelProps {
  systemStatus: SystemStatus | null;
  recentActions: ActionItem[];
  activeTasks?: ActiveTaskItem[];
  onActionClick?: (action: ActionItem) => void;
  onNavigateToPCControl?: () => void;
}

function formatRelativeTime(timestamp: number): string {
  if (!timestamp) return 'Just now';
  const now = Date.now();
  const diffSec = Math.floor((now - timestamp * 1000) / 1000);
  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return new Date(timestamp * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export const RightPanel: React.FC<RightPanelProps> = ({
  systemStatus,
  recentActions,
  activeTasks = [],
  onActionClick,
  onNavigateToPCControl
}) => {
  const metrics = systemStatus?.metrics;

  // History buffer for sparklines
  const [cpuHistory, setCpuHistory] = useState<number[]>([15, 18, 16, 20, 18]);
  const [ramHistory, setRamHistory] = useState<number[]>([40, 41, 42, 42, 42]);

  useEffect(() => {
    if (metrics) {
      setCpuHistory((prev) => [...prev.slice(-9), metrics.cpu_percent]);
      setRamHistory((prev) => [...prev.slice(-9), metrics.ram_percent]);
    }
  }, [metrics?.cpu_percent, metrics?.ram_percent]);

  const getToolIcon = (toolName: string = '') => {
    const t = toolName.toLowerCase();
    if (t.includes('application') || t.includes('code') || t.includes('dev')) {
      return <Code2 size={16} className="text-blue-400" />;
    }
    if (t.includes('file') || t.includes('project') || t.includes('search')) {
      return <FileSearch size={16} className="text-indigo-400" />;
    }
    if (t.includes('temp') || t.includes('clean') || t.includes('delete')) {
      return <Trash2 size={16} className="text-cyan-400" />;
    }
    if (t.includes('diag') || t.includes('health') || t.includes('system')) {
      return <PulseIcon size={16} className="text-purple-400" />;
    }
    return <GearIcon size={16} className="text-slate-400" />;
  };

  // Sparkline generator helper
  const renderSparkline = (points: number[], colorClass: string) => {
    if (points.length < 2) {
      return (
        <svg className={`w-full h-5 ${colorClass}`} viewBox="0 0 40 16" fill="none">
          <line x1="0" y1="8" x2="40" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    }
    const max = Math.max(...points, 100);
    const min = Math.min(...points, 0);
    const range = max - min || 1;
    const pathD = points
      .map((val, idx) => {
        const x = (idx / (points.length - 1)) * 40;
        const y = 14 - ((val - min) / range) * 12;
        return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');

    return (
      <svg className={`w-full h-5 ${colorClass}`} viewBox="0 0 40 16" fill="none">
        <path d={pathD} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
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
            className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center space-x-0.5 cursor-pointer"
          >
            <span>See All</span>
            <ChevronRight size={12} />
          </button>
        </div>

        {/* Real Active Task Cards */}
        <div className="space-y-2 mb-6">
          {activeTasks && activeTasks.length > 0 ? (
            activeTasks.map((task, idx) => {
              const isRunning = task.state === 'RUNNING' || task.status === 'RUNNING';
              const isCompleted = task.state === 'COMPLETED' || task.status === 'COMPLETED' || task.verified;
              const isFailed = task.state === 'FAILED' || task.status === 'FAILED';

              return (
                <div
                  key={task.id || task.step_id || idx}
                  className="p-3 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between glass-card-hover"
                >
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-xl bg-blue-950/60 flex items-center justify-center border border-blue-500/20 shrink-0">
                      {getToolIcon(task.tool || task.name)}
                    </div>
                    <div className="max-w-[170px]">
                      <div className="text-xs font-semibold text-slate-100 truncate">{task.name}</div>
                      <div className="text-[10px] text-slate-400 truncate">
                        {task.description || 'Executing operation...'}
                      </div>
                    </div>
                  </div>

                  {/* Task Status Indicator */}
                  <div>
                    {isRunning ? (
                      task.progress !== undefined && task.progress > 0 ? (
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
                              strokeDashoffset={81.68 * (1 - task.progress / 100)}
                              strokeLinecap="round"
                              className="text-cyan-400 drop-shadow-[0_0_4px_#22d3ee]"
                              fill="transparent"
                            />
                          </svg>
                          <span className="absolute text-[8px] font-bold text-white">{Math.round(task.progress)}%</span>
                        </div>
                      ) : (
                        <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                      )
                    ) : isCompleted ? (
                      <div className="w-5 h-5 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40 shadow-[0_0_8px_rgba(52,211,153,0.3)]">
                        <CheckCircle2 size={13} />
                      </div>
                    ) : isFailed ? (
                      <div className="w-5 h-5 rounded-full bg-red-950/60 flex items-center justify-center text-red-400 border border-red-500/40">
                        <AlertTriangle size={13} />
                      </div>
                    ) : (
                      <div className="w-2.5 h-2.5 rounded-full bg-slate-600 animate-pulse" />
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-3 rounded-2xl glass-panel-subtle border border-slate-800/80 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-xl bg-slate-900/80 flex items-center justify-center text-slate-400 border border-slate-700/40">
                  <GearIcon size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-200">System Standby</div>
                  <div className="text-[10px] text-slate-400">No active background tasks</div>
                </div>
              </div>
              <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee] animate-pulse" />
            </div>
          )}
        </div>

        {/* Section 2: Recent Actions (Real Ledger) */}
        <div className="flex items-center justify-between mb-2.5 px-1">
          <span className="text-xs font-bold text-white tracking-wide">Recent actions</span>
          <button
            onClick={onNavigateToPCControl}
            className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center space-x-0.5 cursor-pointer"
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
                <div className="flex items-center space-x-3 min-w-0 pr-2">
                  <div className="w-7 h-7 rounded-lg bg-slate-800/80 flex items-center justify-center text-slate-300 shrink-0">
                    {getToolIcon(act.tool_name)}
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-slate-200 truncate">{act.summary}</div>
                    <div className="text-[10px] text-slate-500">{formatRelativeTime(act.timestamp)}</div>
                  </div>
                </div>
                <div className="w-4 h-4 rounded-full bg-emerald-950/60 flex items-center justify-center text-emerald-400 border border-emerald-500/40 shrink-0">
                  <CheckCircle2 size={11} />
                </div>
              </div>
            ))
          ) : (
            <div className="p-3 rounded-xl glass-panel-subtle text-center text-slate-400 text-xs">
              No recent actions recorded yet
            </div>
          )}
        </div>
      </div>

      {/* Section 3: System Status (Real Metrics with Dynamic Waves) */}
      <div className="pt-3 border-t border-slate-800/60">
        <div className="flex items-center justify-between mb-3 px-1">
          <span className="text-xs font-bold text-white tracking-wide">System Status</span>
          <div className="flex items-center space-x-1.5 text-xs text-emerald-400 font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
            <span className="text-[11px]">{systemStatus?.status === 'online' ? 'Healthy' : 'Connecting'}</span>
          </div>
        </div>

        {/* 4 Real Metric Cards (CPU, RAM, Storage, GPU) */}
        <div className="grid grid-cols-4 gap-2">
          {/* CPU Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">CPU</div>
            <div className="text-xs font-bold text-white my-1">
              {metrics ? `${metrics.cpu_percent}%` : 'Unavailable'}
            </div>
            {renderSparkline(cpuHistory, 'text-blue-400')}
          </div>

          {/* RAM Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">RAM</div>
            <div className="text-xs font-bold text-white my-1">
              {metrics ? `${metrics.ram_percent}%` : 'Unavailable'}
            </div>
            {renderSparkline(ramHistory, 'text-purple-400')}
          </div>

          {/* Storage Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">Storage</div>
            <div className="text-xs font-bold text-white my-1">
              {metrics ? `${metrics.storage_percent}%` : 'Unavailable'}
            </div>
            <svg className="w-full h-5 text-cyan-400" viewBox="0 0 40 16" fill="none">
              <path d="M0 10 Q 10 5, 20 9 T 40 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>

          {/* GPU Card */}
          <div className="p-2 rounded-xl glass-panel-subtle flex flex-col justify-between">
            <div className="text-[10px] text-slate-400 font-semibold uppercase">GPU</div>
            <div className="text-xs font-bold text-white my-1 truncate">
              {metrics && metrics.gpu_available && metrics.gpu_percent !== null && metrics.gpu_percent !== undefined
                ? `${metrics.gpu_percent}%`
                : 'Unavailable'}
            </div>
            <svg className="w-full h-5 text-teal-400" viewBox="0 0 40 16" fill="none">
              <path d="M0 8 Q 10 12, 20 6 T 40 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        </div>
      </div>
    </aside>
  );
};
export default RightPanel;
