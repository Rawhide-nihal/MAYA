/**
 * MAYA Backend API Client V2
 * Real-time SSE event bus streaming, session token authentication, and settings management.
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
    gpu_percent?: number | null;
    gpu_name?: string;
    gpu_available?: boolean;
    gpu_temperature_c?: number | null;
  };
  model?: {
    name: string;
    base_model: string;
    runtime: string;
    adapter_type?: string;
    quantization?: string;
    context_window?: number;
    status: string;
    vram_allocated_mb?: number;
    gpu_model?: string;
  };
  active_project: string;
}

export interface ActionItem {
  action_id: string;
  plan_id?: string;
  tool_name: string;
  arguments: any;
  summary: string;
  status: string;
  timestamp: number;
  verified?: boolean;
  undo_available: boolean;
}

export interface ChatResponse {
  intent: string;
  reply: string;
  executed_tool?: string;
  plan_id?: string;
  requires_confirmation?: boolean;
  confirmation_id?: string;
  tasks?: Array<{
    step_id?: number;
    name: string;
    description: string;
    tool: string;
    state?: string;
    status?: string;
    result?: any;
    verified?: boolean;
  }>;
  details?: any;
  timestamp: number;
}

let sessionToken: string | null = null;

export const MayaApi = {
  setToken(token: string) {
    sessionToken = token;
  },

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

  async getSettings(): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`);
    return await res.json();
  },

  async updateSettings(newSettings: any): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify(newSettings)
    });
    return await res.json();
  },

  async uploadAttachment(file: File): Promise<any> {
    const form = new FormData();
    form.append('file', file);

    const res = await fetch(`${API_BASE}/attachments`, {
      method: 'POST',
      headers: {
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: form
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok || data?.success === false) {
      throw new Error(data?.error || `Attachment upload failed with HTTP ${res.status}`);
    }
    return data;
  },

  async sendChatMessage(message: string, permissionToken?: string): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ message, permission_token: permissionToken })
    });
    return await res.json();
  },

  async sendChatMessageStream(
    message: string,
    permissionToken: string | undefined,
    onToken: (delta: string) => void
  ): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ message, permission_token: permissionToken })
    });

    if (!res.ok) {
      let messageText = `Maya Core returned HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data?.error) messageText = data.error;
      } catch {
        // Keep the HTTP status fallback.
      }
      throw new Error(messageText);
    }

    if (!res.body) {
      throw new Error('Streaming response body is unavailable in this browser.');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse: ChatResponse | null = null;

    const consumeLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      const event = JSON.parse(trimmed);

      if (event.type === 'token' && typeof event.delta === 'string') {
        onToken(event.delta);
      } else if (event.type === 'done' && event.result) {
        finalResponse = event.result as ChatResponse;
      } else if (event.type === 'error') {
        throw new Error(event.error || 'Maya streaming failed.');
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

      let newlineIndex = buffer.indexOf('\n');
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        consumeLine(line);
        newlineIndex = buffer.indexOf('\n');
      }

      if (done) break;
    }

    if (buffer.trim()) consumeLine(buffer);

    if (!finalResponse) {
      throw new Error('Maya stream ended before a final response was received.');
    }
    return finalResponse;
  },

  async confirmAction(confirmation_id: string, approved: boolean): Promise<{ success: boolean; permission_token?: string }> {
    const res = await fetch(`${API_BASE}/action/confirm`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ confirmation_id, approved })
    });
    return await res.json();
  },

  async resumePlan(plan_id: string, confirmation_id: string, permission_token: string): Promise<any> {
    const res = await fetch(`${API_BASE}/plans/${encodeURIComponent(plan_id)}/resume`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ confirmation_id, permission_token })
    });
    return await res.json();
  },

  async bootstrapToken(): Promise<string | null> {
    try {
      const res = await fetch(`${API_BASE}/auth/token`);
      const data = await res.json();
      if (data.token) {
        this.setToken(data.token);
        return data.token;
      }
    } catch (e) {
      console.warn('[Bootstrap token failed]', e);
    }
    return null;
  },

  async cancelTask(plan_id?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/action/cancel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ plan_id })
    });
    return await res.json();
  },

  async rollbackAction(action_id?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/action/rollback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ action_id })
    });
    return await res.json();
  },

  async sendPttAudio(audioBase64: string): Promise<any> {
    const res = await fetch(`${API_BASE}/voice/ptt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionToken ? { 'X-Maya-Token': sessionToken } : {})
      },
      body: JSON.stringify({ audio_base64: audioBase64 })
    });
    return await res.json();
  },

  subscribeToEvents(onEvent: (event: string, data: any) => void): () => void {
    const es = new EventSource(`${API_BASE}/events`);

    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        if (parsed.event === 'connected' && parsed.token) {
          this.setToken(parsed.token);
        }
        onEvent(parsed.event, parsed.data);
      } catch (err) {
        console.error('[SSE Error]', err);
      }
    };

    es.onerror = () => {
      // Reconnect automatically
    };

    return () => {
      es.close();
    };
  }
};
