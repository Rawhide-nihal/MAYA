/**
 * MAYA Backend API Client
 */

const API_BASE = 'http://127.0.0.1:5000/api';

export interface SystemStatus {
  status: string;
  maya_core: string;
  local_ai_ready: boolean;
  offline_only: boolean;
  metrics: {
    cpu_percent: number;
    ram_percent: number;
    ram_used_gb: number;
    ram_total_gb: number;
    storage_percent: number;
    storage_free_gb: number;
    storage_total_gb: number;
    gpu_percent: number;
  };
  active_project: string;
}

export interface ActionItem {
  action_id: string;
  tool_name: string;
  arguments: any;
  summary: string;
  status: string;
  timestamp: number;
  undo_available: boolean;
}

export interface ChatResponse {
  intent: string;
  reply: string;
  executed_tool?: string;
  plan_id?: string;
  tasks?: Array<{
    name: string;
    description: string;
    tool: string;
    status: string;
    result?: any;
  }>;
  details?: any;
  timestamp: number;
}

export const MayaApi = {
  async getStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/status`);
    return await res.json();
  },

  async getActivity(): Promise<{ actions: ActionItem[] }> {
    const res = await fetch(`${API_BASE}/activity`);
    return await res.json();
  },

  async getDiagnostics(): Promise<any> {
    const res = await fetch(`${API_BASE}/diagnostics`);
    return await res.json();
  },

  async getProjects(): Promise<any> {
    const res = await fetch(`${API_BASE}/projects`);
    return await res.json();
  },

  async getMemory(): Promise<any> {
    const res = await fetch(`${API_BASE}/memory`);
    return await res.json();
  },

  async getSkills(): Promise<any> {
    const res = await fetch(`${API_BASE}/skills`);
    return await res.json();
  },

  async sendChatMessage(message: string): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    return await res.json();
  },

  async rollbackAction(action_id?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/action/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id })
    });
    return await res.json();
  }
};
