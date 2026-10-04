import React, { useEffect, useRef } from 'react';

interface MayaCoreCanvasProps {
  state: 'IDLE' | 'LISTENING' | 'THINKING' | 'EXECUTING' | 'RESPONDING';
  subState?: 'ANALYZE' | 'PLAN' | 'EXECUTE' | 'VERIFY';
  statusText?: string;
}

export const MayaCoreCanvas: React.FC<MayaCoreCanvasProps> = ({
  state = 'EXECUTING',
  subState = 'EXECUTE',
  statusText = 'Working on it...'
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let angle = 0;
    let time = 0;

    // Particle system
    const numParticles = 45;
    const particles = Array.from({ length: numParticles }, (_, i) => ({
      orbitRadius: 75 + (i % 5) * 16,
      angle: (i / numParticles) * Math.PI * 2,
      speed: 0.015 + ((i % 3) * 0.008),
      size: 1.5 + (i % 3),
      tilt: (i % 2 === 0 ? 1 : -1) * 0.45,
      hue: i % 2 === 0 ? 195 : 260
    }));

    const resize = () => {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };

    resize();
    window.addEventListener('resize', resize);

    const render = () => {
      time += 0.035;
      angle += 0.02;

      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      const cx = w / 2;
      const cy = h / 2;

      ctx.clearRect(0, 0, w, h);

      // 1. Draw Horizontal Flowing Audio/Energy Waveforms across the width
      ctx.lineWidth = 2;
      const waveFreq = state === 'THINKING' || state === 'EXECUTING' ? 0.018 : 0.012;
      const waveSpeed = state === 'THINKING' || state === 'EXECUTING' ? time * 2.5 : time * 1.2;
      const waveAmp = state === 'EXECUTING' ? 24 : (state === 'LISTENING' ? 32 : 14);

      // Outer violet glow wave
      ctx.beginPath();
      for (let x = 0; x <= w; x += 3) {
        // Distance from center factor (tapering at far edges and around orb)
        const distFromCenter = Math.abs(x - cx);
        const envelope = Math.sin(Math.PI * (x / w));
        const orbAvoidance = distFromCenter < 90 ? Math.pow(distFromCenter / 90, 2) : 1;
        
        const y = cy + Math.sin(x * waveFreq + waveSpeed) * waveAmp * envelope * orbAvoidance * 1.2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = 'rgba(129, 140, 248, 0.35)';
      ctx.stroke();

      // Main Electric Blue wave
      ctx.beginPath();
      for (let x = 0; x <= w; x += 3) {
        const distFromCenter = Math.abs(x - cx);
        const envelope = Math.sin(Math.PI * (x / w));
        const orbAvoidance = distFromCenter < 90 ? Math.pow(distFromCenter / 90, 2) : 1;
        
        const y = cy + Math.sin(x * waveFreq * 1.4 - waveSpeed * 1.2) * (waveAmp * 0.8) * envelope * orbAvoidance;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = 'rgba(34, 211, 238, 0.75)';
      ctx.shadowColor = 'rgba(34, 211, 238, 0.8)';
      ctx.shadowBlur = 10;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // 2. Draw Concentric 3D Energy Rings around Orb
      const numRings = 4;
      for (let r = 0; r < numRings; r++) {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(angle * (r % 2 === 0 ? 0.6 : -0.8) + r * (Math.PI / 4));
        ctx.scale(1, 0.38 + (r * 0.08));

        ctx.beginPath();
        const radius = 68 + r * 14;
        ctx.arc(0, 0, radius, 0, Math.PI * 2);

        if (r === 0) {
          ctx.strokeStyle = 'rgba(56, 189, 248, 0.7)';
          ctx.lineWidth = 2.2;
        } else if (r === 1) {
          ctx.strokeStyle = 'rgba(168, 85, 247, 0.45)';
          ctx.lineWidth = 1.6;
        } else {
          ctx.strokeStyle = 'rgba(34, 211, 238, 0.3)';
          ctx.lineWidth = 1.2;
        }

        ctx.shadowColor = 'rgba(56, 189, 248, 0.8)';
        ctx.shadowBlur = 12;
        ctx.stroke();
        ctx.restore();
      }

      // 3. Central Luminous Plasma Orb
      const orbRadius = 48 + Math.sin(time * 3) * 2;
      
      // Outer glow
      const outerGlow = ctx.createRadialGradient(cx, cy, 10, cx, cy, orbRadius * 2.2);
      outerGlow.addColorStop(0, 'rgba(56, 189, 248, 0.5)');
      outerGlow.addColorStop(0.5, 'rgba(99, 102, 241, 0.25)');
      outerGlow.addColorStop(1, 'rgba(7, 11, 20, 0)');
      ctx.fillStyle = outerGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, orbRadius * 2.2, 0, Math.PI * 2);
      ctx.fill();

      // Deep sphere gradient
      const sphereGrad = ctx.createRadialGradient(cx - 12, cy - 12, 4, cx, cy, orbRadius);
      sphereGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
      sphereGrad.addColorStop(0.2, 'rgba(56, 189, 248, 0.9)');
      sphereGrad.addColorStop(0.5, 'rgba(79, 70, 229, 0.85)');
      sphereGrad.addColorStop(0.85, 'rgba(15, 23, 42, 0.95)');
      sphereGrad.addColorStop(1, 'rgba(6, 182, 212, 0.8)');

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, orbRadius, 0, Math.PI * 2);
      ctx.fillStyle = sphereGrad;
      ctx.shadowColor = 'rgba(34, 211, 238, 0.9)';
      ctx.shadowBlur = 24;
      ctx.fill();
      ctx.restore();

      // Swirling inner energy core
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-angle * 1.5);
      const innerGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, orbRadius * 0.7);
      innerGrad.addColorStop(0, 'rgba(255, 255, 255, 0.8)');
      innerGrad.addColorStop(0.5, 'rgba(147, 197, 253, 0.4)');
      innerGrad.addColorStop(1, 'rgba(30, 58, 138, 0)');
      ctx.fillStyle = innerGrad;
      ctx.beginPath();
      ctx.ellipse(0, 0, orbRadius * 0.7, orbRadius * 0.35, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // 4. Orbiting Cosmic Particles
      particles.forEach((p) => {
        p.angle += p.speed;
        const px = cx + Math.cos(p.angle) * p.orbitRadius;
        const py = cy + Math.sin(p.angle) * (p.orbitRadius * 0.42) * Math.cos(p.tilt);

        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.hue === 195 ? 'rgba(34, 211, 238, 0.85)' : 'rgba(192, 132, 252, 0.85)';
        ctx.shadowColor = p.hue === 195 ? 'rgba(34, 211, 238, 1)' : 'rgba(192, 132, 252, 1)';
        ctx.shadowBlur = 6;
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [state]);

  const stagesLeft = ['LISTENING', 'THINKING', 'EXECUTING', 'RESPONDING'];
  const stagesRight = ['ANALYZE', 'PLAN', 'EXECUTE', 'VERIFY'];

  return (
    <div className="relative w-full h-[320px] flex items-center justify-center my-1 select-none overflow-hidden">
      {/* Background HTML Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none"
      />

      {/* Left Stage Indicator Ladder (Matching Reference Image) */}
      <div className="absolute left-6 md:left-14 top-1/2 -translate-y-1/2 flex flex-col space-y-3 z-10 text-[11px] font-medium tracking-wider">
        {stagesLeft.map((st) => {
          const isActive = st === state;
          return (
            <div
              key={st}
              className={`flex items-center space-x-2 transition-all duration-300 ${
                isActive
                  ? 'text-cyan-300 font-semibold drop-shadow-[0_0_8px_rgba(34,211,238,0.7)]'
                  : 'text-slate-500'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  isActive
                    ? 'bg-cyan-400 ring-4 ring-cyan-500/30 shadow-[0_0_10px_#22d3ee]'
                    : 'bg-slate-700'
                }`}
              />
              <span>{st}</span>
            </div>
          );
        })}
      </div>

      {/* Right Stage Indicator Ladder (Matching Reference Image) */}
      <div className="absolute right-6 md:right-14 top-1/2 -translate-y-1/2 flex flex-col space-y-3 z-10 text-[11px] font-medium tracking-wider">
        {stagesRight.map((st) => {
          const isActive = st === subState;
          return (
            <div
              key={st}
              className={`flex items-center space-x-2 transition-all duration-300 ${
                isActive
                  ? 'text-cyan-300 font-semibold drop-shadow-[0_0_8px_rgba(34,211,238,0.7)]'
                  : 'text-slate-500'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  isActive
                    ? 'bg-cyan-400 ring-4 ring-cyan-500/30 shadow-[0_0_10px_#22d3ee]'
                    : 'bg-slate-700'
                }`}
              />
              <span>{st}</span>
            </div>
          );
        })}
      </div>

      {/* Floating Status Pill Top (Matching Reference Image) */}
      <div className="absolute top-6 right-20 md:right-28 px-3.5 py-1.5 rounded-md glass-panel-subtle text-[10px] uppercase tracking-widest text-slate-300 border border-slate-700/50 shadow-lg">
        Processing Your Request...
      </div>

      {/* Floating Status Text Bottom (Matching Reference Image) */}
      <div className="absolute bottom-5 flex flex-col items-center z-10">
        <span className="text-xs text-slate-300 font-medium tracking-wide mb-1.5">
          {statusText}
        </span>
        <div className="flex space-x-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:-0.3s]"></span>
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:-0.15s]"></span>
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce"></span>
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:0.15s]"></span>
        </div>
      </div>
    </div>
  );
};
