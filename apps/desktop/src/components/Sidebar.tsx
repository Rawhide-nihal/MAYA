import React from 'react';
import {
  MessageSquare,
  FolderKanban,
  Monitor,
  Box,
  Sparkles,
  Activity,
  Settings,
  Crown,
  ChevronRight
} from 'lucide-react';

export type NavTab = 'chat' | 'projects' | 'pc_control' | 'memory' | 'skills' | 'activity' | 'settings';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  isOnline?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  isOnline = true
}) => {
  const navItems = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'projects', label: 'Projects', icon: FolderKanban },
    { id: 'pc_control', label: 'PC Control', icon: Monitor },
    { id: 'memory', label: 'Memory', icon: Box },
    { id: 'skills', label: 'Skills', icon: Sparkles },
    { id: 'activity', label: 'Activity', icon: Activity },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-[240px] h-full flex flex-col justify-between p-4 bg-[#070b14]/90 border-r border-slate-800/60 select-none">
      {/* Top Branding */}
      <div>
        <div className="flex items-center space-x-3 px-2 py-3 mb-6">
          {/* Glowing Maya circular avatar */}
          <div className="relative flex items-center justify-center w-10 h-10 rounded-full bg-[#0a1224] border-2 border-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.5)]">
            <div className="w-4 h-4 rounded-full bg-cyan-300 shadow-[0_0_8px_#22d3ee]" />
          </div>
          <div>
            <div className="text-base font-bold text-white tracking-wide">Maya</div>
            <div className="flex items-center space-x-1.5 text-xs text-slate-400">
              <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-slate-500'}`} />
              <span className="text-[11px] font-medium">{isOnline ? 'Online' : 'Offline'}</span>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id as NavTab)}
                className={`w-full flex items-center space-x-3.5 px-3.5 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-blue-600/25 text-cyan-300 border border-blue-500/40 shadow-[0_0_15px_rgba(37,99,235,0.25)] font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                }`}
              >
                <Icon
                  size={18}
                  className={isActive ? 'text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.6)]' : 'text-slate-400'}
                />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Pro / System Card (Matching Reference Image) */}
      <div className="p-3.5 rounded-2xl glass-panel-subtle border border-slate-700/40 bg-gradient-to-br from-[#0c162c] to-[#070b14] relative overflow-hidden">
        <div className="flex items-center space-x-2 mb-1.5">
          <Crown size={15} className="text-amber-400" />
          <span className="text-xs font-bold text-white">Maya Pro</span>
        </div>
        <p className="text-[10px] text-slate-400 leading-tight mb-2.5">
          Your AI companion for a more capable PC.
        </p>

        {/* Usage Progress Bar */}
        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden mb-2">
          <div className="bg-gradient-to-r from-blue-500 to-cyan-400 h-1.5 rounded-full w-[72%]" />
        </div>

        <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
          <span>72% used</span>
          <ChevronRight size={13} className="text-slate-500" />
        </div>
      </div>
    </aside>
  );
};
