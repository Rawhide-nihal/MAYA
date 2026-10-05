import React, { useState, useRef, useEffect } from 'react';
import {
  Paperclip,
  Mic,
  ArrowUp,
  Settings as UserIcon,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  X,
  Play
} from 'lucide-react';
import { MayaCoreCanvas } from './MayaCoreCanvas';
import { MayaApi, ChatResponse } from '../services/api';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'maya';
  text: string;
  time: string;
  waveform?: boolean;
  details?: any;
  tasks?: any[];
  requiresConfirmation?: boolean;
  confirmationId?: string;
  confirmationHandled?: boolean;
  planId?: string;
}

interface ChatStageProps {
  coreState?: 'IDLE' | 'LISTENING' | 'UNDERSTANDING' | 'THINKING' | 'PLANNING' | 'EXECUTING' | 'VERIFYING' | 'SPEAKING' | 'SUCCESS' | 'WARNING' | 'ERROR';
  subState?: 'ANALYZE' | 'PLAN' | 'EXECUTE' | 'VERIFY';
  statusText?: string;
  audioAmplitude?: number;
  onTasksUpdate?: (tasks: any[]) => void;
  onActionCompleted?: () => void;
}

export const ChatStage: React.FC<ChatStageProps> = ({
  coreState: externalCoreState,
  subState: externalSubState,
  statusText: externalStatusText,
  audioAmplitude = 0,
  onTasksUpdate,
  onActionCompleted
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'maya',
      text: "Hello! I'm MAYA, your personal AI desktop companion. I have full local awareness of your PC, active projects, and system health. How can I assist you today?",
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      waveform: false
    }
  ]);

  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPTTActive, setIsPTTActive] = useState(false);
  const [internalCoreState, setInternalCoreState] = useState<'IDLE' | 'LISTENING' | 'UNDERSTANDING' | 'THINKING' | 'PLANNING' | 'EXECUTING' | 'VERIFYING' | 'SPEAKING' | 'SUCCESS' | 'WARNING' | 'ERROR'>('IDLE');
  const [internalSubState, setInternalSubState] = useState<'ANALYZE' | 'PLAN' | 'EXECUTE' | 'VERIFY'>('ANALYZE');
  const [internalStatusText, setInternalStatusText] = useState('Ready for your command.');
  const [expandedDetails, setExpandedDetails] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Float32Array[]>([]);
  const sourceSampleRateRef = useRef<number>(48000);

  const encodeWav16Mono = (chunks: Float32Array[], sourceRate: number, targetRate = 16000): Blob => {
    const total = chunks.reduce((n, c) => n + c.length, 0);
    const merged = new Float32Array(total);
    let offset = 0;
    chunks.forEach(c => { merged.set(c, offset); offset += c.length; });

    const ratio = sourceRate / targetRate;
    const outLength = Math.max(1, Math.floor(merged.length / ratio));
    const resampled = new Float32Array(outLength);
    for (let i = 0; i < outLength; i++) {
      const srcPos = i * ratio;
      const left = Math.floor(srcPos);
      const right = Math.min(left + 1, merged.length - 1);
      const frac = srcPos - left;
      resampled[i] = merged[left] * (1 - frac) + merged[right] * frac;
    }

    const buffer = new ArrayBuffer(44 + resampled.length * 2);
    const view = new DataView(buffer);
    const writeAscii = (pos: number, text: string) => {
      for (let i = 0; i < text.length; i++) view.setUint8(pos + i, text.charCodeAt(i));
    };
    writeAscii(0, 'RIFF');
    view.setUint32(4, 36 + resampled.length * 2, true);
    writeAscii(8, 'WAVE');
    writeAscii(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, targetRate, true);
    view.setUint32(28, targetRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeAscii(36, 'data');
    view.setUint32(40, resampled.length * 2, true);

    let p = 44;
    for (let i = 0; i < resampled.length; i++, p += 2) {
      const x = Math.max(-1, Math.min(1, resampled[i]));
      view.setInt16(p, x < 0 ? x * 0x8000 : x * 0x7fff, true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
  };

  const startPTT = async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) return;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const context = new AudioCtx();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);

      audioChunksRef.current = [];
      sourceSampleRateRef.current = context.sampleRate;
      processor.onaudioprocess = (event: AudioProcessingEvent) => {
        const input = event.inputBuffer.getChannelData(0);
        audioChunksRef.current.push(new Float32Array(input));
      };
      source.connect(processor);
      processor.connect(context.destination);

      audioContextRef.current = context;
      audioProcessorRef.current = processor;
      audioSourceRef.current = source;
      mediaStreamRef.current = stream;

      setIsPTTActive(true);
      setInternalCoreState('LISTENING');
      setInternalStatusText('Listening... (release to send)');
    } catch (err) {
      console.warn('Microphone access denied or unavailable', err);
      setInternalCoreState('ERROR');
      setInternalStatusText('Microphone unavailable.');
    }
  };

  const stopPTT = async () => {
    if (!isPTTActive) return;
    setIsPTTActive(false);

    try {
      audioProcessorRef.current?.disconnect();
      audioSourceRef.current?.disconnect();
      mediaStreamRef.current?.getTracks().forEach(t => t.stop());

      const blob = encodeWav16Mono(
        audioChunksRef.current,
        sourceSampleRateRef.current,
        16000
      );

      if (audioContextRef.current) {
        await audioContextRef.current.close();
      }

      audioContextRef.current = null;
      audioProcessorRef.current = null;
      audioSourceRef.current = null;
      mediaStreamRef.current = null;

      setInternalCoreState('UNDERSTANDING');
      setInternalStatusText('Transcribing speech...');

      const reader = new FileReader();
      reader.onloadend = async () => {
        try {
          const resStr = reader.result as string;
          const base64 = resStr.includes(',') ? resStr.split(',')[1] : resStr;
          const res = await MayaApi.sendPttAudio(base64);
          if (res.success && res.transcript) {
            setInternalStatusText(`Heard: "${res.transcript}"`);
            await handleSend(res.transcript);
          } else {
            setInternalCoreState('IDLE');
            setInternalStatusText(res.error || 'No speech detected.');
          }
        } catch (err) {
          setInternalCoreState('ERROR');
          setInternalStatusText('Speech transcription failed.');
        }
      };
      reader.readAsDataURL(blob);
    } catch (err) {
      setInternalCoreState('ERROR');
      setInternalStatusText('Could not process microphone audio.');
    }
  };

  // Sync external props if provided
  const activeCoreState = externalCoreState || internalCoreState;
  const activeSubState = externalSubState || internalSubState;
  const activeStatusText = externalStatusText || internalStatusText;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeStatusText]);

  const toggleDetails = (id: string) => {
    setExpandedDetails(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSend = async (textToSend?: string, permissionToken?: string) => {
    const text = textToSend || inputMessage.trim();
    if (!text || isProcessing) return;

    if (!textToSend) {
      setInputMessage('');
    }

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Add user message if new
    if (!textToSend) {
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        sender: 'user',
        text,
        time: timeStr
      };
      setMessages(prev => [...prev, userMsg]);
    }

    setIsProcessing(true);
    setInternalCoreState('THINKING');
    setInternalSubState('PLAN');
    setInternalStatusText('Formulating plan...');

    try {
      const resp: ChatResponse = await MayaApi.sendChatMessage(text, permissionToken);

      if (resp.tasks && resp.tasks.length > 0) {
        onTasksUpdate?.(resp.tasks);
      }

      if (resp.requires_confirmation) {
        setInternalCoreState('WARNING');
        setInternalStatusText('Authorization required for execution.');

        const confirmMsg: ChatMessage = {
          id: `maya-confirm-${Date.now()}`,
          sender: 'maya',
          text: resp.reply,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          requiresConfirmation: true,
          confirmationId: resp.confirmation_id,
          planId: resp.plan_id,
          details: resp.details,
          tasks: resp.tasks
        };
        setMessages(prev => [...prev, confirmMsg]);
        setIsProcessing(false);
        return;
      }

      const mayaMsg: ChatMessage = {
        id: `maya-${Date.now()}`,
        sender: 'maya',
        text: resp.reply,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        details: resp.details,
        tasks: resp.tasks,
        waveform: true
      };
      setMessages(prev => [...prev, mayaMsg]);
      onActionCompleted?.();

      setInternalCoreState('IDLE');
      setInternalSubState('VERIFY');
      setInternalStatusText('Ready for your command.');
      setIsProcessing(false);

    } catch (err: any) {
      setInternalCoreState('ERROR');
      setInternalStatusText('Service error.');
      setIsProcessing(false);
      setMessages(prev => [
        ...prev,
        {
          id: `maya-err-${Date.now()}`,
          sender: 'maya',
          text: `I encountered an issue connecting to Maya Core: ${err.message || 'Make sure maya_server.py is running.'}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    }
  };

  const handleConfirmAction = async (msgId: string, confirmationId: string, approved: boolean, planId?: string) => {
    // Mark confirmation handled in UI
    setMessages(prev =>
      prev.map(m => (m.id === msgId ? { ...m, confirmationHandled: true } : m))
    );

    if (!approved) {
      try {
        await MayaApi.confirmAction(confirmationId, false);
      } catch (e) {
        console.error(e);
      }
      setMessages(prev => [
        ...prev,
        {
          id: `maya-denied-${Date.now()}`,
          sender: 'maya',
          text: 'Understood. The action was denied and cancelled.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      setInternalCoreState('IDLE');
      setInternalStatusText('Action denied by user.');
      return;
    }

    // Approved: fetch single-use token and resume exact suspended plan
    try {
      setInternalCoreState('EXECUTING');
      setInternalStatusText('Resuming authorized plan...');
      const res = await MayaApi.confirmAction(confirmationId, true);
      if (res.success && res.permission_token) {
        if (planId) {
          const resumeResult = await MayaApi.resumePlan(planId, confirmationId, res.permission_token);
          if (resumeResult.tasks && resumeResult.tasks.length > 0) {
            onTasksUpdate?.(resumeResult.tasks);
          }
          const mayaMsg: ChatMessage = {
            id: `maya-resume-${Date.now()}`,
            sender: 'maya',
            text: resumeResult.summary || resumeResult.message || 'Plan resumed and executed successfully.',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            details: resumeResult.details,
            tasks: resumeResult.tasks,
            waveform: true
          };
          setMessages(prev => [...prev, mayaMsg]);
          onActionCompleted?.();
          setInternalCoreState('SUCCESS');
          setInternalStatusText('Verified and complete.');
          setTimeout(() => {
            setInternalCoreState('IDLE');
            setInternalStatusText('Ready for your command.');
            setIsProcessing(false);
          }, 2200);
        } else {
          await handleSend('Proceed with confirmed action', res.permission_token);
        }
      } else {
        setMessages(prev => [
          ...prev,
          {
            id: `maya-fail-${Date.now()}`,
            sender: 'maya',
            text: 'Authorization token could not be verified or expired.',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
        setInternalCoreState('ERROR');
      }
    } catch (err: any) {
      setInternalCoreState('ERROR');
      setInternalStatusText(`Authorization error: ${err.message}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col justify-between px-6 py-4 overflow-hidden relative">
      {/* Scrollable Conversation Stream */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg) => {
          if (msg.sender === 'user') {
            return (
              <div key={msg.id} className="flex items-start space-x-3 max-w-xl">
                <div className="w-8 h-8 rounded-full bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-300 mt-1 shrink-0">
                  <UserIcon size={15} />
                </div>
                <div className="flex-1">
                  <div className="p-3.5 rounded-2xl glass-panel text-slate-100 text-[13px] leading-relaxed border border-slate-700/40 shadow-md">
                    {msg.text}
                  </div>
                  <span className="text-[10px] text-slate-500 font-medium ml-1 mt-1 block">
                    {msg.time}
                  </span>
                </div>
              </div>
            );
          }

          // Maya Messages
          return (
            <div key={msg.id} className="flex items-start space-x-3 max-w-xl ml-8">
              {/* Maya Glowing Avatar */}
              <div className="w-8 h-8 rounded-full bg-[#09152b] border border-cyan-400/80 flex items-center justify-center text-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.4)] mt-1 shrink-0">
                <div className="w-3.5 h-3.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]" />
              </div>

              <div className="flex-1">
                <div className="p-3.5 rounded-2xl glass-panel text-slate-100 text-[13px] leading-relaxed border border-blue-500/25 shadow-[0_0_15px_rgba(37,99,235,0.1)]">
                  <p className="whitespace-pre-wrap">{msg.text}</p>

                  {/* Interactive Permission Authorization Card */}
                  {msg.requiresConfirmation && !msg.confirmationHandled && msg.confirmationId && (
                    <div className="mt-3 p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/50 space-y-2.5">
                      <div className="flex items-center space-x-2 text-amber-300 font-semibold text-xs">
                        <ShieldAlert size={15} className="text-amber-400 shrink-0" />
                        <span>Security Confirmation Required</span>
                      </div>
                      <p className="text-[11px] text-slate-300">
                        This action modifies files, terminates processes, or runs privileged commands on your system.
                      </p>
                      <div className="flex items-center space-x-2 pt-1">
                        <button
                          onClick={() => handleConfirmAction(msg.id, msg.confirmationId!, true, msg.planId)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md flex items-center space-x-1.5 transition-colors cursor-pointer"
                        >
                          <CheckCircle2 size={13} />
                          <span>Authorize Once</span>
                        </button>
                        <button
                          onClick={() => handleConfirmAction(msg.id, msg.confirmationId!, false, msg.planId)}
                          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors cursor-pointer"
                        >
                          <X size={13} />
                          <span>Deny</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Optional Voice Waveform inside bubble */}
                  {msg.waveform && (
                    <div className="flex items-center space-x-1 mt-2.5 pt-2 border-t border-slate-700/40">
                      {[12, 18, 28, 16, 24, 32, 20, 14, 26, 30, 18, 12].map((height, i) => (
                        <span
                          key={i}
                          style={{ height: `${height * 0.55}px` }}
                          className="w-1 bg-cyan-400 rounded-full animate-pulse"
                        />
                      ))}
                    </div>
                  )}

                  {/* Diagnostic / Task Details Accordion */}
                  {msg.details && (
                    <div className="mt-2.5 pt-2 border-t border-slate-700/40">
                      <button
                        onClick={() => toggleDetails(msg.id)}
                        className="flex items-center space-x-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-medium px-2 py-1 rounded-lg bg-blue-950/40 border border-blue-500/20 cursor-pointer"
                      >
                        <span>Show Details</span>
                        {expandedDetails[msg.id] ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>

                      {expandedDetails[msg.id] && (
                        <div className="mt-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs font-mono">
                          {msg.details.issues && msg.details.issues.length > 0 ? (
                            msg.details.issues.map((iss: any, idx: number) => (
                              <div key={idx} className="flex items-start space-x-2 text-slate-300">
                                <AlertTriangle size={13} className="text-amber-400 shrink-0 mt-0.5" />
                                <div>
                                  <span className="font-semibold text-white">{iss.file || iss.title}:</span> {iss.message || iss.description}
                                </div>
                              </div>
                            ))
                          ) : (
                            <pre className="text-[11px] text-slate-300 overflow-x-auto">
                              {JSON.stringify(msg.details, null, 2)}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-slate-500 font-medium ml-1 mt-1 block">
                  {msg.time}
                </span>
              </div>
            </div>
          );
        })}

        {/* Central MAYA Core Canvas Display */}
        <div className="my-2">
          <MayaCoreCanvas
            state={activeCoreState}
            subState={activeSubState}
            statusText={activeStatusText}
            audioAmplitude={audioAmplitude}
          />
        </div>

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Floating Input Bar */}
      <div className="pt-2">
        <div className="relative flex items-center px-4 py-2.5 rounded-full glass-panel border border-cyan-500/30 shadow-[0_0_25px_rgba(34,211,238,0.15)] bg-[#0a1224]/80">
          {/* Paperclip attachment */}
          <button className="text-slate-400 hover:text-slate-200 transition-colors mr-3 p-1 cursor-pointer">
            <Paperclip size={18} />
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Maya... (e.g. 'Open VS Code', 'Check my project', 'Check system diagnostics')"
            className="flex-1 bg-transparent border-none outline-none text-slate-100 placeholder-slate-400 text-sm font-normal"
          />

          {/* Microphone Push-to-Talk */}
          <button
            onMouseDown={startPTT}
            onMouseUp={stopPTT}
            onTouchStart={startPTT}
            onTouchEnd={stopPTT}
            title="Push to talk (Hold to speak)"
            className={`transition-all duration-200 mx-2 p-1.5 rounded-full cursor-pointer ${
              isPTTActive
                ? 'bg-cyan-500/20 text-cyan-300 shadow-[0_0_15px_#22d3ee] scale-110'
                : 'text-slate-400 hover:text-cyan-400'
            }`}
          >
            <Mic size={18} />
          </button>

          {/* Voice Waveform visualizer mini bars */}
          <div className="flex items-center space-x-1 mx-2">
            <span className="w-0.5 h-3 bg-cyan-400 rounded-full" />
            <span className="w-0.5 h-5 bg-cyan-400 rounded-full" />
            <span className="w-0.5 h-2 bg-cyan-400 rounded-full" />
            <span className="w-0.5 h-4 bg-cyan-400 rounded-full" />
          </div>

          {/* Send Button */}
          <button
            onClick={() => handleSend()}
            disabled={!inputMessage.trim() || isProcessing}
            className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200 ml-1 ${
              inputMessage.trim() && !isProcessing
                ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_15px_#2563eb] cursor-pointer'
                : 'bg-blue-900/50 text-slate-400 cursor-not-allowed'
            }`}
          >
            <ArrowUp size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
export default ChatStage;
