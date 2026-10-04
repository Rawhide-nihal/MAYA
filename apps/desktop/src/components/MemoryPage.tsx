import React, { useEffect, useState } from 'react';
import { Box, Brain, User, Calendar, Database } from 'lucide-react';
import { MayaApi } from '../services/api';

export const MemoryPage: React.FC = () => {
  const [memoryData, setMemoryData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    MayaApi.getMemory().then(data => {
      setMemoryData(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const semantic = memoryData?.memories?.semantic || [];
  const episodic = memoryData?.memories?.episodic || [];

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <Box className="text-cyan-400" />
            <span>Persistent Memory System</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Transparent episodic, semantic, preference, and project memory.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
          Loading memory index...
        </div>
      ) : (
        <div className="space-y-6">
          {/* Semantic & Preference Memories */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Brain size={16} className="text-cyan-400" />
              <span>Learned Facts & Preferences</span>
            </h3>

            <div className="grid grid-cols-2 gap-3 mt-2">
              {semantic.map((s: any) => (
                <div key={s.id} className="p-3.5 rounded-xl glass-panel-subtle flex flex-col justify-between">
                  <div>
                    <span className="text-[10px] text-cyan-400 font-semibold uppercase tracking-wider">
                      {s.category} • {s.key}
                    </span>
                    <p className="text-xs text-slate-200 mt-1 font-medium">{s.content}</p>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-2">
                    Importance: {s.importance}/5.0
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Episodic Memories */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Calendar size={16} className="text-indigo-400" />
              <span>Episodic Events</span>
            </h3>

            <div className="space-y-2 mt-2">
              {episodic.map((e: any) => (
                <div key={e.id} className="p-3 rounded-xl glass-panel-subtle flex items-center justify-between">
                  <div className="text-xs text-slate-200">{e.content}</div>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {new Date(e.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
