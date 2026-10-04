import React, { useEffect, useState } from 'react';
import { Sparkles, Shield, Check, ToggleLeft, ToggleRight } from 'lucide-react';
import { MayaApi } from '../services/api';

export const SkillsPage: React.FC = () => {
  const [skillsList, setSkillsList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    MayaApi.getSkills().then(data => {
      setSkillsList(data.skills || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="flex-1 h-full p-6 overflow-y-auto select-none">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <Sparkles className="text-cyan-400" />
            <span>Extensible Skills Registry</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Modular toolsets and capabilities declared with deterministic permissions.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
          Loading skills...
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {skillsList.map((skill) => (
            <div key={skill.id} className="p-4 rounded-2xl glass-panel border border-slate-800 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold text-cyan-400 uppercase tracking-widest">
                    {skill.category} • v{skill.version}
                  </span>
                  <span className="flex items-center space-x-1 text-emerald-400 text-[11px] font-medium">
                    <Check size={12} />
                    <span>Active</span>
                  </span>
                </div>
                <h3 className="text-sm font-bold text-white mt-1">{skill.name}</h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">{skill.description}</p>
              </div>

              <div className="pt-2 border-t border-slate-800/80">
                <span className="text-[10px] text-slate-500 uppercase font-semibold block mb-1.5">Declared Tools:</span>
                <div className="flex flex-wrap gap-1.5">
                  {skill.tools && skill.tools.map((t: string) => (
                    <span key={t} className="px-2 py-0.5 rounded-md bg-slate-900 text-slate-300 text-[10px] font-mono border border-slate-800">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
