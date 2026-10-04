import React, { useState } from 'react';
import { Settings, Shield, Lock, Eye, Volume2, Cpu } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [permissionLevel, setPermissionLevel] = useState<number>(2);
  const [offlineOnly, setOfflineOnly] = useState<boolean>(true);
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(true);

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <Settings className="text-cyan-400" />
            <span>MAYA Settings & Safety Policy</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Configure permission tiers, model routing, local privacy, and voice engine.
          </p>
        </div>
      </div>

      <div className="space-y-5 max-w-2xl">
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
              { level: 0, title: 'LEVEL 0 — Conversation', desc: 'No PC access. Pure conversational assistant.' },
              { level: 1, title: 'LEVEL 1 — Observation', desc: 'Read system info, process telemetry, search files, read logs.' },
              { level: 2, title: 'LEVEL 2 — Safe Actions (Default)', desc: 'Launch applications, safe file checks, compile diagnostics.' },
              { level: 3, title: 'LEVEL 3 — Modification', desc: 'Edit files, move files, terminate processes, clean temp files.' },
              { level: 4, title: 'LEVEL 4 — Critical', desc: 'Always requires explicit user confirmation. Permanent file deletion, registry.' },
            ].map((tier) => (
              <label
                key={tier.level}
                onClick={() => setPermissionLevel(tier.level)}
                className={`p-3 rounded-xl glass-panel-subtle flex items-start space-x-3 cursor-pointer transition-colors border ${
                  permissionLevel === tier.level ? 'border-cyan-400/60 bg-blue-950/40' : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="permission"
                  checked={permissionLevel === tier.level}
                  onChange={() => setPermissionLevel(tier.level)}
                  className="mt-1 accent-cyan-400"
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
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Privacy & Inference Stack</h3>
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl glass-panel-subtle">
            <div>
              <div className="text-xs font-bold text-slate-200">Offline-First Local Privacy</div>
              <div className="text-[11px] text-slate-400">Never transmit PC data, file paths, or commands to external cloud APIs.</div>
            </div>
            <input
              type="checkbox"
              checked={offlineOnly}
              onChange={(e) => setOfflineOnly(e.target.checked)}
              className="accent-cyan-400 w-4 h-4 cursor-pointer"
            />
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl glass-panel-subtle">
            <div>
              <div className="text-xs font-bold text-slate-200">Voice Synthesis (pyttsx3)</div>
              <div className="text-[11px] text-slate-400">Stream verbal responses through the local voice synthesizer.</div>
            </div>
            <input
              type="checkbox"
              checked={voiceEnabled}
              onChange={(e) => setVoiceEnabled(e.target.checked)}
              className="accent-cyan-400 w-4 h-4 cursor-pointer"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
