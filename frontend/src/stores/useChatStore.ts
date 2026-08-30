import { defineStore } from 'pinia';
import { ref } from 'vue';
import { chatApi } from '../api/chatApi';
import { usePlantStore } from './usePlantStore';
import type { UIMessage } from '../types/chat';

export const useChatStore = defineStore('chat', () => {
  const plantStore = usePlantStore();

  const messages = ref<UIMessage[]>([
    {
      id: 'welcome-msg',
      sender: 'agent',
      text: 'سلام و درود 🌱 من «فیتوایجنت»، دستیار تخصصی گیاه‌پزشکی و برنامه‌ریزی تغذیه گیاهان شما هستم.\n\nمی‌توانید وضعیت یا مشکل گیاهتان (مانند زردی برگ، توقف رشد، برنامه کودی مناسب، نوع بستر و...) را مطرح کنید یا از باغچه خود یکی از گیاهان را برای مشاوره اختصاصی انتخاب نمایید.',
      timestamp: new Date(),
    },
  ]);

  const sessionId = ref<string>('');
  const selectedPlantId = ref<string | null>(null);
  const isLoading = ref<boolean>(false);
  const error = ref<string | null>(null);
  const activeQuickSlots = ref<string[]>([]);

  async function sendMessage(text: string, plantIdOverride?: string) {
    if (!text.trim()) return;

    const targetPlantId = plantIdOverride !== undefined ? plantIdOverride : selectedPlantId.value;

    // Add user message to UI
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

      // Update session ID if returned
      if (response.session_id) {
        sessionId.value = response.session_id;
      }

      // Add agent message
      const agentMsg: UIMessage = {
        id: 'agent-' + Date.now(),
        sender: 'agent',
        text: response.response,
        timestamp: new Date(),
        plant_id: response.plant_id || targetPlantId,
        risk_level: response.risk_level,
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
    if (missingSlots.includes('substrate_type')) {
      suggestions.push('خاک سبک و آروئید میکس');
      suggestions.push('کوکوپیت و پرلیت');
      suggestions.push('خاک باغچه‌ای و سنگین');
    }
    if (missingSlots.includes('traits')) {
      suggestions.push('دارای برگ‌های ابلق');
      suggestions.push('برگ‌های کاملاً سبز ساده');
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

  function clearHistory() {
    sessionId.value = '';
    messages.value = [
      {
        id: 'welcome-msg-reset',
        sender: 'agent',
        text: 'گفتگوی جدید آغاز شد 🌱 آماده پاسخگویی به سوالات تشخیصی و تغذیه گیاهان شما هستم.',
        timestamp: new Date(),
      },
    ];
    activeQuickSlots.value = [];
  }

  return {
    messages,
    sessionId,
    selectedPlantId,
    isLoading,
    error,
    activeQuickSlots,
    sendMessage,
    sendQuickSlotAnswer,
    setContextPlant,
    clearHistory,
  };
});
