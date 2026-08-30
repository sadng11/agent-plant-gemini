import { defineStore } from 'pinia';
import { ref } from 'vue';

import { chatApi } from '../api/chatApi';
import { usePlantStore } from './usePlantStore';
import type { ChatSessionInfo, UIMessage } from '../types/chat';

const ACTIVE_SESSION_KEY = 'phyto_active_session_id';

export const useChatStore = defineStore('chat', () => {
  const plantStore = usePlantStore();

  const welcomeMessage: UIMessage = {
    id: 'welcome-msg',
    sender: 'agent',
    text: 'سلام و درود 🌱 من «فیتوایجنت»، دستیار تخصصی گیاه‌پزشکی و برنامه‌ریزی تغذیه گیاهان شما هستم.\n\nمی‌توانید وضعیت یا مشکل گیاهتان (مانند زردی برگ، توقف رشد، برنامه کودی مناسب، نوع بستر و...) را مطرح کنید یا از باغچه خود یکی از گیاهان را برای مشاوره اختصاصی انتخاب نمایید.',
    timestamp: new Date(),
  };

  const messages = ref<UIMessage[]>([welcomeMessage]);
  const sessions = ref<ChatSessionInfo[]>([]);
  const sessionId = ref<string>(localStorage.getItem(ACTIVE_SESSION_KEY) || '');
  const selectedPlantId = ref<string | null>(null);
  const isLoading = ref<boolean>(false);
  const isLoadingSessions = ref<boolean>(false);
  const error = ref<string | null>(null);
  const activeQuickSlots = ref<string[]>([]);

  /**
   * Load all chat sessions for the active user
   */
  async function loadSessions(plantIdFilter?: string) {
    if (!plantStore.activeUserId) return;
    isLoadingSessions.value = true;
    try {
      const data = await chatApi.getSessions(plantStore.activeUserId, plantIdFilter);
      sessions.value = data;
    } catch (err: any) {
      console.error('Failed to load chat sessions:', err);
    } finally {
      isLoadingSessions.value = false;
    }
  }

  /**
   * Load message history from DB for a specific session ID
   */
  async function loadActiveSessionMessages(targetSessionId: string) {
    if (!targetSessionId) return;

    isLoading.value = true;
    error.value = null;
    try {
      const history = await chatApi.getSessionMessages(targetSessionId, plantStore.activeUserId);
      if (history && history.length > 0) {
        messages.value = history.map((m) => ({
          id: m.id,
          sender: m.sender,
          text: m.content,
          timestamp: m.created_at ? new Date(m.created_at) : new Date(),
          plant_id: m.payload?.plant_id || null,
          risk_level: m.payload?.risk_level || null,
          risk_type: m.payload?.risk_type || null,
          risk_message: m.payload?.risk_message || null,
          feasibility_status: m.payload?.feasibility_status || null,
          calculated_schedule: m.payload?.calculated_schedule || null,
          missing_slots: m.payload?.missing_slots || [],
          extracted_entities: m.payload?.extracted_entities || null,
        }));

        // Check if last message has missing slots
        const lastMsg = history[history.length - 1];
        if (lastMsg.sender === 'agent' && lastMsg.payload?.missing_slots?.length) {
          deriveQuickSlots(lastMsg.payload.missing_slots);
        } else {
          activeQuickSlots.value = [];
        }

        // Set plant context if session is associated with a plant
        const currentSession = sessions.value.find((s) => s.id === targetSessionId);
        if (currentSession && currentSession.plant_id) {
          selectedPlantId.value = currentSession.plant_id;
        }
      } else {
        messages.value = [welcomeMessage];
        activeQuickSlots.value = [];
      }

      sessionId.value = targetSessionId;
      localStorage.setItem(ACTIVE_SESSION_KEY, targetSessionId);
    } catch (err: any) {
      console.error('Failed to load session messages:', err);
      error.value = 'خطا در واکشی تاریخچه گفتگو از سرور';
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Send user message to agent and persist turn
   */
  async function sendMessage(text: string, plantIdOverride?: string) {
    if (!text.trim()) return;

    const targetPlantId = plantIdOverride !== undefined ? plantIdOverride : selectedPlantId.value;

    // Optimistically add user message to UI
    const userMsg: UIMessage = {
      id: 'user-' + Date.now(),
      sender: 'user',
      text: text.trim(),
      timestamp: new Date(),
      plant_id: targetPlantId,
    };
    messages.value.push(userMsg);

    isLoading.value = true;
    error.value = null;
    activeQuickSlots.value = [];

    try {
      const response = await chatApi.sendMessage({
        user_id: plantStore.activeUserId,
        message: text.trim(),
        session_id: sessionId.value || undefined,
        plant_id: targetPlantId || undefined,
      });

      // Update session ID if created or returned
      if (response.session_id) {
        sessionId.value = response.session_id;
        localStorage.setItem(ACTIVE_SESSION_KEY, response.session_id);
      }

      // Add agent message to UI
      const agentMsg: UIMessage = {
        id: 'agent-' + Date.now(),
        sender: 'agent',
        text: response.response,
        timestamp: new Date(),
        plant_id: response.plant_id || targetPlantId,
        risk_level: response.risk_level,
        risk_type: response.risk_type,
        risk_message: response.risk_message,
        feasibility_status: response.feasibility_status,
        calculated_schedule: response.calculated_schedule,
        missing_slots: response.missing_slots,
        extracted_entities: response.extracted_entities,
      };
      messages.value.push(agentMsg);

      // Determine quick slot chips if any slots missing or suggestions
      if (response.missing_slots && response.missing_slots.length > 0) {
        deriveQuickSlots(response.missing_slots);
      } else {
        activeQuickSlots.value = [];
      }

      // Refresh sessions list in background
      await loadSessions();

      // If backend updated or linked a plant, refresh plants
      if (response.plant_id) {
        await plantStore.fetchPlants();
      }
    } catch (err: any) {
      error.value = err.message || 'خطا در برقراری ارتباط با دستیار گیاه‌پزشک';
      const errorMsg: UIMessage = {
        id: 'agent-err-' + Date.now(),
        sender: 'agent',
        text: 'متأسفانه در پردازش درخواست شما خطایی رخ داد. لطفاً اتصال به سرور را بررسی کرده و مجدداً تلاش فرمایید.',
        timestamp: new Date(),
      };
      messages.value.push(errorMsg);
    } finally {
      isLoading.value = false;
    }
  }

  function deriveQuickSlots(missingSlots: string[]) {
    const suggestions: string[] = [];
    if (missingSlots.includes('trait_disambiguation') || missingSlots.includes('traits')) {
      suggestions.push('🌿 سبز ساده و معمولی');
      suggestions.push('🤍 ابلق (دارای بخش‌های سفید/کرم)');
    }
    if (missingSlots.includes('health_verification') || missingSlots.includes('health')) {
      suggestions.push('✅ کاملاً سالم و بدون آفت');
      suggestions.push('⚠️ دارای زردی برگ یا علائم آفت');
    }
    if (missingSlots.includes('substrate_type') || missingSlots.includes('substrate')) {
      suggestions.push('کوکوپیت و پرلیت');
      suggestions.push('خاک سبک و آروئید میکس');
      suggestions.push('خاک باغچه‌ای و سنگین');
    }
    if (missingSlots.includes('current_phase')) {
      suggestions.push('فاز رشد رویشی فعال');
      suggestions.push('فاز گل‌دهی یا باروری');
      suggestions.push('دوران رکود زمستانه');
    }
    activeQuickSlots.value = suggestions;
  }

  function sendQuickSlotAnswer(chipText: string) {
    sendMessage(chipText);
  }

  function setContextPlant(plantId: string | null) {
    selectedPlantId.value = plantId;
  }

  /**
   * Start a brand new chat session
   */
  function startNewSession(plantIdOverride?: string | null) {
    sessionId.value = '';
    localStorage.removeItem(ACTIVE_SESSION_KEY);
    messages.value = [
      {
        id: 'welcome-msg-new-' + Date.now(),
        sender: 'agent',
        text: 'گفتگوی جدید آغاز شد 🌱 آماده پاسخگویی به سوالات تشخیصی و تغذیه گیاهان شما هستم.',
        timestamp: new Date(),
      },
    ];
    activeQuickSlots.value = [];
    if (plantIdOverride !== undefined) {
      selectedPlantId.value = plantIdOverride;
    }
  }

  /**
   * Delete a session and refresh list
   */
  async function deleteSession(targetSessionId: string) {
    try {
      await chatApi.deleteSession(targetSessionId, plantStore.activeUserId);
      sessions.value = sessions.value.filter((s) => s.id !== targetSessionId);
      if (sessionId.value === targetSessionId) {
        startNewSession();
      }
    } catch (err: any) {
      console.error('Failed to delete session:', err);
      error.value = 'خطا در حذف گفتگو';
    }
  }

  /**
   * Initialize chat store on app start / component mount
   */
  async function init() {
    await loadSessions();
    if (sessionId.value) {
      // Check if session still exists in sessions
      const exists = sessions.value.some((s) => s.id === sessionId.value);
      if (exists) {
        await loadActiveSessionMessages(sessionId.value);
      } else if (sessions.value.length > 0) {
        // Load the latest session
        await loadActiveSessionMessages(sessions.value[0].id);
      } else {
        startNewSession();
      }
    } else if (sessions.value.length > 0) {
      await loadActiveSessionMessages(sessions.value[0].id);
    }
  }

  return {
    messages,
    sessions,
    sessionId,
    selectedPlantId,
    isLoading,
    isLoadingSessions,
    error,
    activeQuickSlots,
    loadSessions,
    loadActiveSessionMessages,
    sendMessage,
    sendQuickSlotAnswer,
    setContextPlant,
    startNewSession,
    deleteSession,
    init,
  };
});

