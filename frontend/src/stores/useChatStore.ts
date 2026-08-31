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
    text: 'سلام و درود 🌱 من «فیتو»، دستیار تخصصی گیاه‌پزشکی و برنامه‌ریزی تغذیه گیاهان شما هستم.\n\nمی‌توانید وضعیت یا مشکل گیاهتان (مانند زردی برگ، توقف رشد، برنامه کودی مناسب، نوع بستر و...) را مطرح کنید یا از باغچه خود یکی از گیاهان را برای مشاوره اختصاصی انتخاب نمایید.',
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
   * Send user message to agent and stream response turn
   */
  async function sendMessage(text: string, plantIdOverride?: string) {
    if (!text.trim()) return;

    const targetPlantId = plantIdOverride !== undefined ? plantIdOverride : selectedPlantId.value;

    // 1. Optimistically add user message to UI
    const userMsgId = 'user-' + Date.now();
    const userMsg: UIMessage = {
      id: userMsgId,
      sender: 'user',
      text: text.trim(),
      timestamp: new Date(),
      plant_id: targetPlantId,
      is_sending: true,
      is_failed: false,
    };
    messages.value.push(userMsg);

    // 2. Add placeholder agent message with streaming state
    const agentMsgId = 'agent-' + (Date.now() + 1);
    const agentMsg: UIMessage = {
      id: agentMsgId,
      sender: 'agent',
      text: '',
      timestamp: new Date(),
      plant_id: targetPlantId,
      is_streaming: true,
    };
    messages.value.push(agentMsg);

    const getUserMsg = () => messages.value.find((m) => m.id === userMsgId);
    const getAgentMsg = () => messages.value.find((m) => m.id === agentMsgId);

    isLoading.value = true;
    error.value = null;
    activeQuickSlots.value = [];

    try {
      await chatApi.streamMessage(
        {
          user_id: plantStore.activeUserId,
          message: text.trim(),
          session_id: sessionId.value || undefined,
          plant_id: targetPlantId || undefined,
        },
        {
          onStart(payload) {
            const u = getUserMsg();
            if (u) {
              u.is_sending = false;
              u.is_failed = false;
            }
            if (payload.session_id) {
              sessionId.value = payload.session_id;
              localStorage.setItem(ACTIVE_SESSION_KEY, payload.session_id);
            }
            const a = getAgentMsg();
            if (a && payload.plant_id) {
              a.plant_id = payload.plant_id;
            }
          },
          onToken(token) {
            const u = getUserMsg();
            if (u) u.is_sending = false;

            const a = getAgentMsg();
            if (a) {
              a.text += token;
            }
          },
          onDone(response) {
            const u = getUserMsg();
            if (u) {
              u.is_sending = false;
              u.is_failed = false;
            }

            const a = getAgentMsg();
            if (a) {
              a.is_streaming = false;
              if (response.response) {
                a.text = response.response;
              }
              a.plant_id = response.plant_id || targetPlantId;
              a.risk_level = response.risk_level;
              a.risk_type = response.risk_type;
              a.risk_message = response.risk_message;
              a.feasibility_status = response.feasibility_status;
              a.calculated_schedule = response.calculated_schedule;
              a.missing_slots = response.missing_slots;
              a.extracted_entities = response.extracted_entities;
            }

            if (response.missing_slots && response.missing_slots.length > 0) {
              deriveQuickSlots(response.missing_slots);
            } else {
              activeQuickSlots.value = [];
            }
          },
          onError(err) {
            throw err;
          },
        }
      );

      const uFinal = getUserMsg();
      if (uFinal) {
        uFinal.is_sending = false;
        uFinal.is_failed = false;
      }
      const aFinal = getAgentMsg();
      if (aFinal) {
        aFinal.is_streaming = false;
      }

      // Refresh sessions list in background
      await loadSessions();

      // If backend updated or linked a plant, refresh plants
      const curAgent = getAgentMsg();
      if (curAgent && curAgent.plant_id) {
        await plantStore.fetchPlants();
      }
    } catch (err: any) {
      const uErr = getUserMsg();
      if (uErr) {
        uErr.is_sending = false;
        uErr.is_failed = true;
      }
      const aErr = getAgentMsg();
      if (aErr) {
        aErr.is_streaming = false;
        // If nothing was streamed yet, clean up empty placeholder
        if (!aErr.text.trim()) {
          const agentIdx = messages.value.findIndex((m) => m.id === agentMsgId);
          if (agentIdx !== -1) {
            messages.value.splice(agentIdx, 1);
          }
        }
      }

      error.value = err.message || 'خطا در برقراری ارتباط با دستیار گیاه‌پزشک';
      const errorMsg: UIMessage = {
        id: 'agent-err-' + Date.now(),
        sender: 'agent',
        text: 'متأسفانه در پردازش درخواست شما خطایی رخ داد. لطفاً اتصال به سرور را بررسی کرده و مجدداً تلاش فرمایید.',
        timestamp: new Date(),
        is_error: true,
        failed_text: text.trim(),
        plant_id: targetPlantId,
      };
      messages.value.push(errorMsg);
    } finally {
      isLoading.value = false;
      const aDone = getAgentMsg();
      if (aDone) {
        aDone.is_streaming = false;
      }
    }
  }

  /**
   * Retry sending a failed user message
   */
  async function retryUserMessage(userMessageId: string) {
    const userMsgIdx = messages.value.findIndex((m) => m.id === userMessageId && m.sender === 'user');
    if (userMsgIdx === -1) return;

    const userMsg = messages.value[userMsgIdx];
    const textToResend = userMsg.text;
    const plantId = userMsg.plant_id || undefined;

    // Remove any following error message matching this text
    const followingMsg = messages.value[userMsgIdx + 1];
    if (followingMsg && followingMsg.is_error && followingMsg.failed_text === textToResend) {
      messages.value.splice(userMsgIdx + 1, 1);
    }

    // Remove the old failed user message
    messages.value.splice(userMsgIdx, 1);

    // Resend cleanly
    await sendMessage(textToResend, plantId);
  }

  /**
   * Retry a failed message from error bubble or default
   */
  async function retryMessage(errorMessageId?: string) {
    let failedMsg: UIMessage | undefined;
    if (errorMessageId) {
      const idx = messages.value.findIndex((m) => m.id === errorMessageId);
      if (idx !== -1) {
        failedMsg = messages.value[idx];
        messages.value.splice(idx, 1);
      }
    } else {
      const lastErrorIdx = [...messages.value].reverse().findIndex((m) => m.is_error);
      if (lastErrorIdx !== -1) {
        const actualIdx = messages.value.length - 1 - lastErrorIdx;
        failedMsg = messages.value[actualIdx];
        messages.value.splice(actualIdx, 1);
      }
    }

    if (failedMsg && failedMsg.failed_text) {
      // Also remove preceding failed user message if present
      const failedUserIdx = [...messages.value].reverse().findIndex(
        (m) => m.sender === 'user' && m.is_failed && m.text === failedMsg?.failed_text
      );
      if (failedUserIdx !== -1) {
        const actualUserIdx = messages.value.length - 1 - failedUserIdx;
        messages.value.splice(actualUserIdx, 1);
      }

      await sendMessage(failedMsg.failed_text, failedMsg.plant_id || undefined);
    }
  }

  function deriveQuickSlots(missingSlots: string[]) {
    const suggestions: string[] = [];
    if (missingSlots.includes('user_intent')) {
      suggestions.push('🌿 دریافت برنامه کودی و تغذیه تخصصی');
      suggestions.push('🩺 عیب‌یابی زردی، لکه برگی یا آفت');
      suggestions.push('💧 راهنمای آبیاری، نور و شرایط نگهداری');
      suggestions.push('🪴 راهنمای تعویض گلدان و بستر');
    }
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
    retryMessage,
    retryUserMessage,
    sendQuickSlotAnswer,
    setContextPlant,
    startNewSession,
    deleteSession,
    init,
  };
});


