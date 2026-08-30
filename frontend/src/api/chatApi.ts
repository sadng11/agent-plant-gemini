import { apiClient } from './client';
import type {
  ChatMessageData,
  ChatRequest,
  ChatResponse,
  ChatSessionInfo,
} from '../types/chat';

export const chatApi = {
  /**
   * Send a user query to the LangGraph plant diagnostic agent
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

