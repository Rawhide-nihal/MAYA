import React, { useState, useEffect } from 'react';
import { Search, Minus, Square, X } from 'lucide-react';
import { Sidebar, NavTab } from './components/Sidebar';
import { RightPanel } from './components/RightPanel';
import { ChatStage } from './components/ChatStage';
import { ProjectsPage } from './components/ProjectsPage';
import { PCControlPage } from './components/PCControlPage';
import { MemoryPage } from './components/MemoryPage';
import { SkillsPage } from './components/SkillsPage';
import { ActivityPage } from './components/ActivityPage';
import { SettingsPage } from './components/SettingsPage';
import { MayaApi, SystemStatus, ActionItem } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('chat');
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [recentActions, setRecentActions] = useState<ActionItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isOnline, setIsOnline] = useState(true);

  // Poll live telemetry and actions from Python server
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [status, act] = await Promise.all([
          MayaApi.getStatus(),
          MayaApi.getActivity()
        ]);
        setSystemStatus(status);
        setRecentActions(act.actions || []);
        setIsOnline(true);
      } catch (err) {
        setIsOnline(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 3500);
    return () => clearInterval(interval);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    // Dispatch search to chat
    setCurrentTab('chat');
  };

  return (
    <div className="w-screen h-screen flex flex-col bg-[#070b14] overflow-hidden text-slate-100 select-none">
      {/* Top Header / Titlebar Matching Reference Image */}
      <header className="h-11 w-full flex items-center justify-between px-4 bg-[#070b14]/90 border-b border-slate-800/40 z-20">
        {/* Left window spacing */}
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            MAYA • DESKTOP COMPANION
          </span>
        </div>

        {/* Right Search Bar & Window Controls (Matching Reference Image) */}
        <div className="flex items-center space-x-4">
          {/* Search Pill */}
          <form onSubmit={handleSearchSubmit} className="relative flex items-center">
            <Search size={13} className="absolute left-3 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search anything..."
              className="w-56 pl-8 pr-3 py-1 rounded-full bg-slate-900/80 border border-slate-700/60 text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-400/60 transition-all"
            />
          </form>

          {/* Window Control Buttons */}
          <div className="flex items-center space-x-2 text-slate-400">
            <button
              onClick={() => {}}
              className="p-1.5 hover:text-white hover:bg-slate-800/60 rounded transition-colors"
            >
              <Minus size={13} />
            </button>
            <button
              onClick={() => {}}
              className="p-1.5 hover:text-white hover:bg-slate-800/60 rounded transition-colors"
            >
              <Square size={11} />
            </button>
            <button
              onClick={() => {}}
              className="p-1.5 hover:text-red-400 hover:bg-red-950/40 rounded transition-colors"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      </header>

      {/* Main App Content Layout (Sidebar + Stage + RightPanel) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          isOnline={isOnline}
        />

        {/* Center Main Stage (Renders Chat or Other Tab Views) */}
        <main className="flex-1 flex flex-col h-full bg-[#070b14]/50 overflow-hidden relative">
          {currentTab === 'chat' && <ChatStage />}
          {currentTab === 'projects' && <ProjectsPage />}
          {currentTab === 'pc_control' && <PCControlPage />}
          {currentTab === 'memory' && <MemoryPage />}
          {currentTab === 'skills' && <SkillsPage />}
          {currentTab === 'activity' && <ActivityPage />}
          {currentTab === 'settings' && <SettingsPage />}
        </main>

        {/* Right PC Control Panel */}
        <RightPanel
          systemStatus={systemStatus}
          recentActions={recentActions}
          onNavigateToPCControl={() => setCurrentTab('pc_control')}
        />
      </div>
    </div>
  );
};
export default App;
