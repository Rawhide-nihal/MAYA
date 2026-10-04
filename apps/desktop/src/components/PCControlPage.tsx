import React, { useEffect, useState } from 'react';
import { Monitor, RefreshCw, Trash2, ShieldCheck, Activity, Cpu, HardDrive } from 'lucide-react';
import { MayaApi } from '../services/api';

export const PCControlPage: React.FC = () => {
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoading(true);
    try {
      const data = await MayaApi.getDiagnostics();
      setDiagnostics(data);
    } catch (e: any) {
      setStatusMessage(`Failed to run diagnostics: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiagnostics();
  }, []);

  const handleCleanTemp = async () => {
    setStatusMessage('Cleaning temporary files...');
    try {
      const res = await MayaApi.sendChatMessage('Clean up temporary files');
      setStatusMessage(res.reply);
      fetchDiagnostics();
    } catch (e: any) {
      setStatusMessage(`Error: ${e.message}`);
    }
  };

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <Monitor className="text-cyan-400" />
            <span>Windows PC Control & Diagnostics</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real operating system telemetry, process management, and diagnostic prioritization.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchDiagnostics}
            disabled={loading}
            className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold border border-slate-700 flex items-center space-x-1.5 transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Rescan System</span>
          </button>

          <button
            onClick={handleCleanTemp}
            className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md flex items-center space-x-1.5 transition-colors"
          >
            <Trash2 size={13} />
            <span>Clean Temp Files</span>
          </button>
        </div>
      </div>

      {statusMessage && (
        <div className="mb-4 p-3 rounded-xl bg-blue-950/60 border border-blue-500/30 text-cyan-300 text-xs flex items-center justify-between">
          <span>{statusMessage}</span>
          <button onClick={() => setStatusMessage(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {loading && !diagnostics ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
          Running diagnostic scan...
        </div>
      ) : diagnostics ? (
        <div className="space-y-5">
          {/* Diagnostic Findings */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">Categorized Findings</h3>
              <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                diagnostics.status === 'Healthy' ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/40' : 'bg-amber-950 text-amber-400 border border-amber-500/40'
              }`}>
                Status: {diagnostics.status}
              </span>
            </div>

            <div className="space-y-2 mt-2">
              {diagnostics.findings && diagnostics.findings.map((f: any, idx: number) => (
                <div key={idx} className="p-3 rounded-xl glass-panel-subtle flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <span className={`w-2 h-2 rounded-full mt-1.5 ${
                      f.severity === 'Healthy' ? 'bg-emerald-400' : (f.severity === 'Warning' ? 'bg-amber-400' : 'bg-red-500')
                    }`} />
                    <div>
                      <div className="text-xs font-semibold text-slate-200">{f.message}</div>
                      <div className="text-[10px] text-slate-500 uppercase">{f.category}</div>
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-400 font-medium px-2 py-0.5 rounded bg-slate-800">
                    {f.severity}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Installed Developer Environment Tools */}
          {diagnostics.dev_tools && (
            <div className="p-5 rounded-2xl glass-panel border border-slate-800">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3">Development Environment</h3>
              <div className="grid grid-cols-3 gap-3">
                {Object.entries(diagnostics.dev_tools).map(([tool, version]: any) => (
                  <div key={tool} className="p-3 rounded-xl glass-panel-subtle">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">{tool}</div>
                    <div className="text-xs font-bold text-slate-200 mt-0.5 truncate">{version}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};
