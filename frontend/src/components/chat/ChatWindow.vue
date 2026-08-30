<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import { Send, Trash2, Sprout, Loader2, Flower2 } from 'lucide-vue-next';
import { useChatStore } from '../../stores/useChatStore';
import { usePlantStore } from '../../stores/usePlantStore';
import ChatMessage from './ChatMessage.vue';
import QuickSlotChips from './QuickSlotChips.vue';

const chatStore = useChatStore();
const plantStore = usePlantStore();

const inputText = ref('');
const messagesContainer = ref<HTMLElement | null>(null);

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

watch(
  () => chatStore.messages.length,
  () => {
    scrollToBottom();
  }
);

watch(
  () => chatStore.isLoading,
  (loading) => {
    if (loading) scrollToBottom();
  }
);

onMounted(() => {
  scrollToBottom();
});

function handleSend() {
  if (!inputText.value.trim() || chatStore.isLoading) return;
  const text = inputText.value;
  inputText.value = '';
  chatStore.sendMessage(text);
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}

function handleClear() {
  if (confirm('آیا از پاک کردن تاریخچه گفتگوی جاری اطمینان دارید؟')) {
    chatStore.clearHistory();
  }
}

function handlePlantContextChange(e: Event) {
  const target = e.target as HTMLSelectElement;
  chatStore.setContextPlant(target.value ? target.value : null);
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-8rem)] bg-slate-50/50 rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
    <!-- Chat Header Bar -->
    <div class="px-4 py-3 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0">
      <!-- Plant Context Selector -->
      <div class="flex items-center space-x-2 space-x-reverse">
        <Flower2 class="w-5 h-5 text-emerald-600 shrink-0" />
        <label for="plant-context-select" class="text-xs font-semibold text-slate-700 shrink-0">
          کانتکست پرونده گیاه:
        </label>
        <select
          id="plant-context-select"
          :value="chatStore.selectedPlantId || ''"
          @change="handlePlantContextChange"
          class="text-xs rounded-xl border-slate-300 bg-slate-50 py-1.5 px-3 font-medium text-slate-800 focus:border-emerald-500 focus:ring-emerald-500 transition-colors"
        >
          <option value="">🌿 مشاوره عمومی / گیاه جدید</option>
          <option
            v-for="plant in plantStore.plants"
            :key="plant.id"
            :value="plant.id"
          >
            🪴 {{ plant.nickname }} ({{ plant.species_id }})
          </option>
        </select>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center gap-2">
        <button
          @click="handleClear"
          title="شروع گفتگوی جدید"
          class="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Messages Scrollable Body -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4"
    >
      <ChatMessage
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- Botanical Reasoning Loading Indicator -->
      <div
        v-if="chatStore.isLoading"
        class="flex items-start space-x-3 space-x-reverse animate-fade-in"
      >
        <div class="w-9 h-9 rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-700 text-white flex items-center justify-center shrink-0 shadow-sm shadow-emerald-600/20">
          <Sprout class="w-5 h-5 animate-pulse-subtle" />
        </div>
        <div class="bg-white border border-emerald-200/80 rounded-2xl rounded-tr-none p-4 shadow-sm text-slate-700 text-xs flex items-center space-x-3 space-x-reverse">
          <Loader2 class="w-4 h-4 text-emerald-600 animate-spin" />
          <div class="flex flex-col gap-0.5">
            <span class="font-bold text-slate-900">در حال تحلیل گراف تشخیصی اگرونومی...</span>
            <span class="text-[11px] text-slate-500">ارزیابی سازگاری بستر، فاز فنولوژیکی و محاسبه دوز بهینه</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Slot Chips Bar -->
    <QuickSlotChips />

    <!-- Chat Input Area -->
    <div class="p-3 sm:p-4 bg-white border-t border-slate-200 shrink-0">
      <div class="max-w-4xl mx-auto flex items-end space-x-2 space-x-reverse">
        <div class="flex-1 relative">
          <textarea
            v-model="inputText"
            @keydown="handleKeydown"
            rows="2"
            placeholder="پیام یا وضعیت گیاه خود را اینجا بنویسید (مثلاً: برگ‌انجیری من در خاک رسی قرار دارد، برنامه کود چیست؟)..."
            class="w-full resize-none rounded-2xl border-slate-300 bg-slate-50/70 p-3 pr-3 pl-10 text-sm placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-emerald-500 transition-all font-normal leading-relaxed"
          ></textarea>
        </div>

        <button
          @click="handleSend"
          :disabled="!inputText.trim() || chatStore.isLoading"
          class="h-11 px-5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm flex items-center justify-center space-x-2 space-x-reverse shadow-md shadow-emerald-600/20 transition-all duration-150 shrink-0"
        >
          <span>ارسال</span>
          <Send class="w-4 h-4 -rotate-90" />
        </button>
      </div>
    </div>
  </div>
</template>
