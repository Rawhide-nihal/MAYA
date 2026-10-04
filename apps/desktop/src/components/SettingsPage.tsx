import React, { useState, useEffect } from 'react';
import { Settings, Shield, Lock, Eye, Volume2, Cpu, CheckCircle2, RefreshCw } from 'lucide-react';
import { MayaApi } from '../services/api';

export const SettingsPage: React.FC = () => {
  const [permissionLevel, setPermissionLevel] = useState<number>(2);
  const [offlineOnly, setOfflineOnly] = useState<boolean>(true);
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(true);
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    // Load persisted settings
    MayaApi.getSettings().then((res) => {
      if (res && res.settings) {
        if (res.settings.permission_level !== undefined) {
          setPermissionLevel(Number(res.settings.permission_level));
        }
        if (res.settings.offline_only !== undefined) {
          setOfflineOnly(Boolean(res.settings.offline_only));
        }
        if (res.settings.voice_enabled !== undefined) {
          setVoiceEnabled(Boolean(res.settings.voice_enabled));
        }
      }
    }).catch(console.error);

    // Load live model and hardware telemetry
    MayaApi.getStatus().then((status) => {
      if (status && status.model) {
        setModelInfo(status.model);
      }
    }).catch(console.error);
  }, []);

  const handleUpdateSetting = async (key: string, value: any) => {
    setSaving(true);
    try {
      await MayaApi.updateSettings({ [key]: value });
      setStatusMessage(`Setting "${key}" updated successfully.`);
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err: any) {
      setStatusMessage(`Failed to update setting: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handlePermissionChange = (level: number) => {
    setPermissionLevel(level);
    handleUpdateSetting('permission_level', level);
  };

  const handleOfflineToggle = (checked: boolean) => {
    setOfflineOnly(checked);
    handleUpdateSetting('offline_only', checked);
  };

  const handleVoiceToggle = (checked: boolean) => {
    setVoiceEnabled(checked);
    handleUpdateSetting('voice_enabled', checked);
  };

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <Settings className="text-cyan-400" />
            <span>MAYA Settings & Safety Policy</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Deterministic permission tiers, local AI model parameters, and offline privacy guardrails.
          </p>
        </div>

        {statusMessage && (
          <div className="px-3.5 py-1.5 rounded-xl bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 text-xs flex items-center space-x-2">
            <CheckCircle2 size={13} />
            <span>{statusMessage}</span>
          </div>
        )}
      </div>

      <div className="space-y-5 max-w-3xl">
        {/* Model & Runtime Status */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Cpu size={18} className="text-cyan-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">MAYA AI Engine & Local Model Stack</h3>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 pt-1">
            <div className="p-3 rounded-xl glass-panel-subtle">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Active Foundation</div>
              <div className="text-xs font-bold text-white mt-1 truncate">{modelInfo?.base_model || 'Qwen2.5-Coder-1.5B'}</div>
            </div>

            <div className="p-3 rounded-xl glass-panel-subtle">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Trained LoRA Adapter</div>
              <div className="text-xs font-bold text-cyan-400 mt-1 truncate">{modelInfo?.name || 'maya-v1 (Custom LoRA)'}</div>
            </div>

            <div className="p-3 rounded-xl glass-panel-subtle">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Execution Runtime</div>
              <div className="text-xs font-bold text-slate-200 mt-1 truncate">{modelInfo?.runtime || 'Local MayaRuntime'}</div>
            </div>

            <div className="p-3 rounded-xl glass-panel-subtle">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">GPU Acceleration</div>
              <div className="text-xs font-bold text-white mt-1 truncate">{modelInfo?.gpu_model || 'NVIDIA RTX 4050'}</div>
            </div>

            <div className="p-3 rounded-xl glass-panel-subtle">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Allocated VRAM</div>
              <div className="text-xs font-bold text-slate-200 mt-1 truncate">{modelInfo?.vram_allocated_mb ? `${modelInfo.vram_allocated_mb} MB` : 'Dynamic'}</div>
            </div>

            <div className="p-3 rounded-xl glass-panel-subtle">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Context Window</div>
              <div className="text-xs font-bold text-slate-200 mt-1 truncate">{modelInfo?.context_window ? `${modelInfo.context_window} tokens` : '8,192 tokens'}</div>
            </div>
          </div>
        </div>

        {/* Permission Tier Configuration */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Shield size={18} className="text-cyan-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Action Permission Tier</h3>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Deterministic security policy. High-impact operations strictly enforce this gate before tools execute.
          </p>

          <div className="space-y-2 pt-1">
            {[
              { level: 0, title: 'LEVEL 0 — Pure Conversation', desc: 'No PC access. Maya acts solely as a conversational dialogue assistant.' },
              { level: 1, title: 'LEVEL 1 — Observation Only', desc: 'Read system info, process telemetry, search files, read logs. Zero mutations.' },
              { level: 2, title: 'LEVEL 2 — Safe Actions (Recommended Default)', desc: 'Launch applications, safe file checks, inspect projects, run read-only diagnostics.' },
              { level: 3, title: 'LEVEL 3 — Modification', desc: 'Edit files, move files, terminate processes, clean temp files with rollback ledger.' },
              { level: 4, title: 'LEVEL 4 — Unrestricted / Critical', desc: 'Always requires signed user approval for critical registry or system modifications.' },
            ].map((tier) => (
              <label
                key={tier.level}
                onClick={() => handlePermissionChange(tier.level)}
                className={`p-3 rounded-xl glass-panel-subtle flex items-start space-x-3 cursor-pointer transition-colors border ${
                  permissionLevel === tier.level ? 'border-cyan-400/60 bg-blue-950/40 shadow-[0_0_12px_rgba(34,211,238,0.15)]' : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="permission"
                  checked={permissionLevel === tier.level}
                  onChange={() => handlePermissionChange(tier.level)}
                  className="mt-1 accent-cyan-400 cursor-pointer"
                />
                <div>
                  <div className="text-xs font-bold text-slate-200">{tier.title}</div>
                  <div className="text-[11px] text-slate-400">{tier.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Privacy & Model Options */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Lock size={18} className="text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Privacy & Local Guardrails</h3>
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl glass-panel-subtle">
            <div>
              <div className="text-xs font-bold text-slate-200">Offline-First Local Privacy</div>
              <div className="text-[11px] text-slate-400">Never transmit PC data, file paths, or commands to external cloud APIs.</div>
            </div>
            <input
              type="checkbox"
              checked={offlineOnly}
              onChange={(e) => handleOfflineToggle(e.target.checked)}
              className="accent-cyan-400 w-4 h-4 cursor-pointer"
            />
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl glass-panel-subtle">
            <div>
              <div className="text-xs font-bold text-slate-200">Voice Synthesis (pyttsx3 / SAPI5)</div>
              <div className="text-[11px] text-slate-400">Stream verbal responses through the local voice synthesizer engine.</div>
            </div>
            <input
              type="checkbox"
              checked={voiceEnabled}
              onChange={(e) => handleVoiceToggle(e.target.checked)}
              className="accent-cyan-400 w-4 h-4 cursor-pointer"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
export default SettingsPage;
