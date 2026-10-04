import React, { useState, useEffect, useCallback } from 'react';
import { Search, Minus, Square, X } from 'lucide-react';
import { Sidebar, NavTab } from './components/Sidebar';
import { RightPanel, ActiveTaskItem } from './components/RightPanel';
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
  const [activeTasks, setActiveTasks] = useState<ActiveTaskItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isOnline, setIsOnline] = useState(true);

  // Maya Core Live State & RMS Amplitude
  const [coreState, setCoreState] = useState<'IDLE' | 'LISTENING' | 'UNDERSTANDING' | 'THINKING' | 'PLANNING' | 'EXECUTING' | 'VERIFYING' | 'SPEAKING' | 'SUCCESS' | 'WARNING' | 'ERROR'>('IDLE');
  const [subState, setSubState] = useState<'ANALYZE' | 'PLAN' | 'EXECUTE' | 'VERIFY'>('ANALYZE');
  const [statusText, setStatusText] = useState('Ready for your command.');
  const [audioAmplitude, setAudioAmplitude] = useState<number>(0);

  const fetchTelemetry = useCallback(async () => {
    try {
      const [status, act] = await Promise.all([
        MayaApi.getStatus(),
        MayaApi.getActivity()
      ]);
      setSystemStatus(status);
      setRecentActions(act.actions || []);
      setIsOnline(true);
    } catch {
      setIsOnline(false);
    }
  }, []);

  // Poll live telemetry and bootstrap session token
  useEffect(() => {
    MayaApi.bootstrapToken();
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3500);
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  // Subscribe to real-time SSE event bus
  useEffect(() => {
    const unsubscribe = MayaApi.subscribeToEvents((event, data) => {
      switch (event) {
        case 'maya.state':
          if (data?.state) setCoreState(data.state);
          if (data?.sub_state) setSubState(data.sub_state);
          if (data?.status_text) setStatusText(data.status_text);
          break;

        case 'maya.speaking.amplitude':
          if (typeof data?.amplitude === 'number') {
            setAudioAmplitude(data.amplitude);
          }
          break;

        case 'plan.created':
          if (data?.steps) {
            setActiveTasks(
              data.steps.map((s: any) => ({
                id: s.step_id,
                name: s.name,
                description: s.description,
                tool: s.tool,
                state: s.state || 'PENDING',
                verified: s.verified || false
              }))
            );
          }
          break;

        case 'plan.step.started':
          setActiveTasks((prev) =>
            prev.map((t) =>
              t.id === data?.step_id ? { ...t, state: 'RUNNING', description: data?.description || t.description } : t
            )
          );
          setCoreState('EXECUTING');
          break;

        case 'plan.step.completed':
          setActiveTasks((prev) =>
            prev.map((t) =>
              t.id === data?.step_id ? { ...t, state: 'COMPLETED', verified: data?.verified ?? true } : t
            )
          );
          break;

        case 'plan.completed':
          setActiveTasks((prev) =>
            prev.map((t) => ({ ...t, state: 'COMPLETED', verified: true }))
          );
          setTimeout(() => setActiveTasks([]), 8000);
          fetchTelemetry();
          break;

        case 'plan.failed':
          setActiveTasks((prev) =>
            prev.map((t) =>
              t.id === data?.step_id ? { ...t, state: 'FAILED' } : t
            )
          );
          break;

        case 'action.recorded':
        case 'action.rolled_back':
          fetchTelemetry();
          break;

        default:
          break;
      }
    });

    return () => unsubscribe();
  }, [fetchTelemetry]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setCurrentTab('chat');
  };

  return (
    <div className="w-screen h-screen flex flex-col bg-[#070b14] overflow-hidden text-slate-100 select-none">
      {/* Top Header / Titlebar */}
      <header className="h-11 w-full flex items-center justify-between px-4 bg-[#070b14]/90 border-b border-slate-800/40 z-20">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            MAYA • DESKTOP COMPANION
          </span>
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-500/30">
            PHASE 2 PRODUCTION
          </span>
        </div>

        {/* Right Search Bar & Window Controls */}
        <div className="flex items-center space-x-4">
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

          <div className="flex items-center space-x-2 text-slate-400">
            <button className="p-1.5 hover:text-white hover:bg-slate-800/60 rounded transition-colors cursor-pointer">
              <Minus size={13} />
            </button>
            <button className="p-1.5 hover:text-white hover:bg-slate-800/60 rounded transition-colors cursor-pointer">
              <Square size={11} />
            </button>
            <button className="p-1.5 hover:text-red-400 hover:bg-red-950/40 rounded transition-colors cursor-pointer">
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

        {/* Center Main Stage */}
        <main className="flex-1 flex flex-col h-full bg-[#070b14]/50 overflow-hidden relative">
          {currentTab === 'chat' && (
            <ChatStage
              coreState={coreState}
              subState={subState}
              statusText={statusText}
              audioAmplitude={audioAmplitude}
              onTasksUpdate={(tasks) => setActiveTasks(tasks)}
              onActionCompleted={fetchTelemetry}
            />
          )}
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
          activeTasks={activeTasks}
          onNavigateToPCControl={() => setCurrentTab('pc_control')}
          onActionClick={() => setCurrentTab('activity')}
        />
      </div>
    </div>
  );
};
export default App;
