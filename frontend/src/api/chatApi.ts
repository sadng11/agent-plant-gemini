import { apiClient } from './client';
import type { ChatRequest, ChatResponse } from '../types/chat';

export const chatApi = {
  /**
   * Send a user query to the LangGraph plant diagnostic agent
   */
  async sendMessage(req: ChatRequest): Promise<ChatResponse> {
    const res = await apiClient.post<ChatResponse>('/chat', req);
    return res.data;
  },
};
