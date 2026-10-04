import React, { useEffect, useState } from 'react';
import { Activity, RotateCcw, CheckCircle2, XCircle, Code2, Trash2, FileSearch, Settings } from 'lucide-react';
import { MayaApi, ActionItem } from '../services/api';

export const ActivityPage: React.FC = () => {
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [rollbackStatus, setRollbackStatus] = useState<string | null>(null);

  const fetchActions = () => {
    MayaApi.getActivity().then(data => {
      setActions(data.actions || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchActions();
  }, []);

  const handleRollback = async (actionId?: string) => {
    setRollbackStatus('Rolling back action...');
    try {
      const res = await MayaApi.rollbackAction(actionId);
      setRollbackStatus(res.message || 'Action rolled back.');
      fetchActions();
    } catch (e: any) {
      setRollbackStatus(`Rollback failed: ${e.message}`);
    }
  };

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <Activity className="text-cyan-400" />
            <span>Action Ledger & Audit Trail</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Deterministic record of every state-changing operation with rollback capability.
          </p>
        </div>

        <button
          onClick={() => handleRollback()}
          className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md flex items-center space-x-1.5 transition-colors"
        >
          <RotateCcw size={13} />
          <span>Rollback Last Action</span>
        </button>
      </div>

      {rollbackStatus && (
        <div className="mb-4 p-3 rounded-xl bg-blue-950/60 border border-blue-500/30 text-cyan-300 text-xs flex items-center justify-between">
          <span>{rollbackStatus}</span>
          <button onClick={() => setRollbackStatus(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
          Loading audit ledger...
        </div>
      ) : actions.length === 0 ? (
        <div className="text-xs text-slate-400">No actions recorded yet.</div>
      ) : (
        <div className="space-y-2.5">
          {actions.map((act) => (
            <div
              key={act.action_id}
              className="p-3.5 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between"
            >
              <div className="flex items-center space-x-3.5">
                <div className="w-8 h-8 rounded-xl bg-slate-800/80 flex items-center justify-center text-slate-300">
                  {act.tool_name.includes('application') ? (
                    <Code2 size={16} className="text-blue-400" />
                  ) : act.tool_name.includes('project') ? (
                    <FileSearch size={16} className="text-indigo-400" />
                  ) : act.tool_name.includes('temp') ? (
                    <Trash2 size={16} className="text-cyan-400" />
                  ) : (
                    <Settings size={16} className="text-slate-400" />
                  )}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-white">{act.summary}</span>
                    <span className="text-[10px] text-slate-500 font-mono">#{act.action_id}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Tool: {act.tool_name} • {new Date(act.timestamp * 1000).toLocaleTimeString()}
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                {act.undo_available && (
                  <button
                    onClick={() => handleRollback(act.action_id)}
                    className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-medium border border-slate-700 flex items-center space-x-1"
                  >
                    <RotateCcw size={11} />
                    <span>Undo</span>
                  </button>
                )}

                <div className="flex items-center space-x-1 text-xs">
                  {act.status === 'success' ? (
                    <span className="flex items-center space-x-1 text-emerald-400 font-medium">
                      <CheckCircle2 size={14} />
                      <span>Success</span>
                    </span>
                  ) : act.status === 'undone' ? (
                    <span className="text-slate-400 font-medium">Undone</span>
                  ) : (
                    <span className="flex items-center space-x-1 text-red-400 font-medium">
                      <XCircle size={14} />
                      <span>Failed</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
