import React, { useState, useRef, useEffect } from 'react';
import {
  Paperclip,
  Mic,
  ArrowUp,
  Settings as UserIcon,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle
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
}

export const ChatStage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-1',
      sender: 'user',
      text: 'Hey Maya, can you open VS Code and check if my project has any errors?',
      time: '10:24 AM'
    },
    {
      id: 'msg-2',
      sender: 'maya',
      text: "Sure! I'll open VS Code, scan your project, and check for any errors. Give me a moment...",
      time: '10:24 AM',
      waveform: true
    },
    {
      id: 'msg-3',
      sender: 'maya',
      text: "VS Code is now open and I've scanned your project. I found 2 minor issues. Here's what I found:",
      time: '10:25 AM',
      details: {
        issues: [
          { severity: 'minor', file: 'package.json', message: 'No build or test scripts defined in package.json.' },
          { severity: 'minor', file: 'pyproject.toml', message: 'Missing tool.poetry configuration section.' }
        ]
      }
    }
  ]);

  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [coreState, setCoreState] = useState<'IDLE' | 'LISTENING' | 'THINKING' | 'EXECUTING' | 'RESPONDING'>('EXECUTING');
  const [subState, setSubState] = useState<'ANALYZE' | 'PLAN' | 'EXECUTE' | 'VERIFY'>('EXECUTE');
  const [statusText, setStatusText] = useState('Working on it...');
  const [expandedDetails, setExpandedDetails] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const toggleDetails = (id: string) => {
    setExpandedDetails(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSend = async () => {
    if (!inputMessage.trim() || isProcessing) return;

    const userText = inputMessage.trim();
    setInputMessage('');
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Add user message
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: userText,
      time: timeStr
    };
    setMessages(prev => [...prev, userMsg]);

    // Update Maya core to THINKING -> EXECUTING
    setIsProcessing(true);
    setCoreState('THINKING');
    setSubState('PLAN');
    setStatusText('Planning execution...');

    try {
      setTimeout(() => {
        setCoreState('EXECUTING');
        setSubState('EXECUTE');
        setStatusText('Executing requested task...');
      }, 700);

      const resp = await MayaApi.sendChatMessage(userText);

      setCoreState('RESPONDING');
      setSubState('VERIFY');
      setStatusText('Task verified and complete.');

      const mayaMsg: ChatMessage = {
        id: `maya-${Date.now()}`,
        sender: 'maya',
        text: resp.reply,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        details: resp.details,
        tasks: resp.tasks
      };

      setMessages(prev => [...prev, mayaMsg]);

      setTimeout(() => {
        setCoreState('IDLE');
        setStatusText('Ready for your command.');
        setIsProcessing(false);
      }, 2500);

    } catch (err: any) {
      setCoreState('IDLE');
      setStatusText('Error connecting to Maya Core.');
      setIsProcessing(false);
      setMessages(prev => [
        ...prev,
        {
          id: `maya-err-${Date.now()}`,
          sender: 'maya',
          text: `I encountered an issue connecting to my core service: ${err.message || 'Check if maya_server.py is running.'}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
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
        {/* User Message 1 */}
        {messages.map((msg) => {
          if (msg.sender === 'user') {
            return (
              <div key={msg.id} className="flex items-start space-x-3 max-w-xl">
                <div className="w-8 h-8 rounded-full bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-300 mt-1">
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
                  <p>{msg.text}</p>

                  {/* Optional Voice Waveform inside bubble (Matching Reference Image) */}
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

                  {/* Show Details Accordion for diagnostics (Matching Reference Image) */}
                  {msg.details && (
                    <div className="mt-2.5 pt-2 border-t border-slate-700/40">
                      <button
                        onClick={() => toggleDetails(msg.id)}
                        className="flex items-center space-x-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-medium px-2 py-1 rounded-lg bg-blue-950/40 border border-blue-500/20"
                      >
                        <span>Show Details</span>
                        {expandedDetails[msg.id] ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>

                      {expandedDetails[msg.id] && (
                        <div className="mt-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs">
                          {msg.details.issues && msg.details.issues.length > 0 ? (
                            msg.details.issues.map((iss: any, idx: number) => (
                              <div key={idx} className="flex items-start space-x-2 text-slate-300">
                                <AlertTriangle size={13} className="text-amber-400 shrink-0 mt-0.5" />
                                <div>
                                  <span className="font-semibold text-white">{iss.file}:</span> {iss.message}
                                </div>
                              </div>
                            ))
                          ) : (
                            <div className="flex items-center space-x-2 text-emerald-400">
                              <CheckCircle2 size={13} />
                              <span>Workspace verified. All checks passing.</span>
                            </div>
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

        {/* Central MAYA Core Canvas Display (Replicating Reference Center) */}
        <div className="my-2">
          <MayaCoreCanvas
            state={coreState}
            subState={subState}
            statusText={statusText}
          />
        </div>

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Floating Input Bar (Matching Reference Image) */}
      <div className="pt-2">
        <div className="relative flex items-center px-4 py-2.5 rounded-full glass-panel border border-cyan-500/30 shadow-[0_0_25px_rgba(34,211,238,0.15)] bg-[#0a1224]/80">
          {/* Paperclip attachment */}
          <button className="text-slate-400 hover:text-slate-200 transition-colors mr-3 p-1">
            <Paperclip size={18} />
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Maya..."
            className="flex-1 bg-transparent border-none outline-none text-slate-100 placeholder-slate-400 text-sm font-normal"
          />

          {/* Microphone */}
          <button className="text-slate-400 hover:text-cyan-400 transition-colors mx-2 p-1">
            <Mic size={18} />
          </button>

          {/* Voice Waveform visualizer mini bars */}
          <div className="flex items-center space-x-1 mx-2">
            <span className="w-0.5 h-3 bg-cyan-400 rounded-full" />
            <span className="w-0.5 h-5 bg-cyan-400 rounded-full" />
            <span className="w-0.5 h-2 bg-cyan-400 rounded-full" />
            <span className="w-0.5 h-4 bg-cyan-400 rounded-full" />
          </div>

          {/* Send Button: Glowing Electric Blue Circle with Arrow Up */}
          <button
            onClick={handleSend}
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
