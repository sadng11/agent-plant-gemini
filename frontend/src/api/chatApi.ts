import { apiClient } from './client';
import type {
  ChatMessageData,
  ChatRequest,
  ChatResponse,
  ChatSessionInfo,
  StreamCallbacks,
} from '../types/chat';

export const chatApi = {
  /**
   * Stream a user query to the LangGraph plant diagnostic agent via SSE
   */
  async streamMessage(
    req: ChatRequest,
    callbacks: StreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const response = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
      signal,
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      throw new Error(`خطای ارتباط با سرور (${response.status}): ${errorText || response.statusText}`);
    }

    if (!response.body) {
      throw new Error('عدم دریافت محتوای استریم از سرور');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let currentEvent = 'message';
    let currentData = '';

    const dispatchEvent = (eventType: string, dataString: string) => {
      if (!dataString) return;
      try {
        const parsed = JSON.parse(dataString);
        const resolvedType = parsed.type || eventType;
        if (resolvedType === 'start') {
          callbacks.onStart?.(parsed);
        } else if (resolvedType === 'token') {
          callbacks.onToken?.(parsed.content ?? '');
        } else if (resolvedType === 'done') {
          callbacks.onDone?.(parsed);
        } else if (resolvedType === 'error') {
          callbacks.onError?.(new Error(parsed.error || 'خطا در حین استریم'));
        }
      } catch (parseErr) {
        console.warn('Failed to parse SSE JSON:', dataString, parseErr);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep trailing incomplete fragment in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            // Empty line dispatches current SSE message
            if (currentData) {
              dispatchEvent(currentEvent, currentData);
              currentEvent = 'message';
              currentData = '';
            }
            continue;
          }

          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.slice(6).trim();
          } else if (trimmed.startsWith('data:')) {
            const dataSlice = trimmed.slice(5).trim();
            currentData = currentData ? currentData + '\n' + dataSlice : dataSlice;
          }
        }
      }

      // Dispatch any remaining event in buffer
      if (buffer.trim()) {
        const trimmed = buffer.trim();
        if (trimmed.startsWith('data:')) {
          const dataSlice = trimmed.slice(5).trim();
          currentData = currentData ? currentData + '\n' + dataSlice : dataSlice;
        }
      }
      if (currentData) {
        dispatchEvent(currentEvent, currentData);
      }
    } finally {
      reader.releaseLock();
    }
  },

  /**
   * Send a user query to the LangGraph plant diagnostic agent (non-streaming)
   */
  async sendMessage(req: ChatRequest): Promise<ChatResponse> {
    const res = await apiClient.post<ChatResponse>('/chat', req);
    return res.data;
  },

  /**
   * Fetch all conversation sessions for a user (optionally filtered by plantId)
   */
  async getSessions(userId: string, plantId?: string): Promise<ChatSessionInfo[]> {
    const params: Record<string, string> = { user_id: userId };
    if (plantId) {
      params.plant_id = plantId;
    }
    const res = await apiClient.get<ChatSessionInfo[]>('/chat/sessions', { params });
    return res.data;
  },

  /**
   * Fetch message history for a specific session
   */
  async getSessionMessages(sessionId: string, userId?: string): Promise<ChatMessageData[]> {
    const params: Record<string, string> = {};
    if (userId) {
      params.user_id = userId;
    }
    const res = await apiClient.get<ChatMessageData[]>(`/chat/sessions/${sessionId}/messages`, { params });
    return res.data;
  },

  /**
   * Delete a conversation session and all its messages
   */
  async deleteSession(sessionId: string, userId?: string): Promise<void> {
    const params: Record<string, string> = {};
    if (userId) {
      params.user_id = userId;
    }
    await apiClient.delete(`/chat/sessions/${sessionId}`, { params });
  },
};

