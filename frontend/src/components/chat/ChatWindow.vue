<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import {
  Send,
  Trash2,
  Sprout,
  Loader2,
  Flower2,
  Plus,
  History,
  MessageSquare,
  X,
} from 'lucide-vue-next';

import { useChatStore } from '../../stores/useChatStore';
import { usePlantStore } from '../../stores/usePlantStore';
import ChatMessage from './ChatMessage.vue';
import QuickSlotChips from './QuickSlotChips.vue';

const route = useRoute();
const chatStore = useChatStore();
const plantStore = usePlantStore();

const inputText = ref('');
const messagesContainer = ref<HTMLElement | null>(null);
const showSessionsSidebar = ref(false);

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
  () => {
    const last = chatStore.messages[chatStore.messages.length - 1];
    return last ? last.text : '';
  },
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

onMounted(async () => {
  if (route.query.plantId && typeof route.query.plantId === 'string') {
    chatStore.setContextPlant(route.query.plantId);
  }
  await chatStore.init();
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

function handleNewChat() {
  chatStore.startNewSession(chatStore.selectedPlantId);
  showSessionsSidebar.value = false;
}

async function handleSelectSession(sessionId: string) {
  await chatStore.loadActiveSessionMessages(sessionId);
  showSessionsSidebar.value = false;
  scrollToBottom();
}

async function handleDeleteSession(e: Event, sessionId: string) {
  e.stopPropagation();
  if (confirm('آیا از حذف این گفتگو از دیتابیس اطمینان دارید؟')) {
    await chatStore.deleteSession(sessionId);
  }
}

function handlePlantContextChange(e: Event) {
  const target = e.target as HTMLSelectElement;
  chatStore.setContextPlant(target.value ? target.value : null);
}

function formatSessionDate(dateStr?: string | null) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('fa-IR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
</script>

<template>
  <div class="relative flex h-[calc(100vh-8rem)] bg-slate-50/50 rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
    <!-- Sessions Sidebar Drawer for Large Screens & Slide-over for Mobile -->
    <div
      v-if="showSessionsSidebar"
      @click="showSessionsSidebar = false"
      class="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-20 md:hidden transition-opacity"
    ></div>

    <aside
      class="fixed md:static inset-y-0 right-0 z-30 w-72 sm:w-80 bg-white border-l border-slate-200 flex flex-col transition-transform duration-200 ease-in-out shrink-0"
      :class="showSessionsSidebar ? 'translate-x-0' : 'translate-x-full md:translate-x-0 md:w-72 lg:w-80'"
    >
      <!-- Sidebar Header -->
      <div class="p-3.5 border-b border-slate-100 flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 text-slate-800 font-bold text-sm">
          <History class="w-4 h-4 text-emerald-600" />
          <span>تاریخچه گفتگوها</span>
        </div>
        <div class="flex items-center gap-1">
          <button
            @click="handleNewChat"
            class="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-emerald-50 text-emerald-700 hover:bg-emerald-100 text-xs font-semibold transition-colors"
            title="گفتگوی جدید"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>جدید</span>
          </button>
          <button
            @click="showSessionsSidebar = false"
            class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 md:hidden"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Sessions List -->
      <div class="flex-1 overflow-y-auto p-2 space-y-1.5 divide-y divide-slate-50">
        <div
          v-if="chatStore.isLoadingSessions"
          class="p-6 text-center text-xs text-slate-400 flex flex-col items-center gap-2"
        >
          <Loader2 class="w-5 h-5 text-emerald-600 animate-spin" />
          <span>در حال واکشی سوابق از دیتابیس...</span>
        </div>

        <div
          v-else-if="chatStore.sessions.length === 0"
          class="p-6 text-center text-xs text-slate-400"
        >
          <MessageSquare class="w-8 h-8 mx-auto mb-2 text-slate-300 opacity-60" />
          <span>هنوز گفتگویی ثبت نشده است.</span>
        </div>

        <div
          v-for="sess in chatStore.sessions"
          :key="sess.id"
          role="button"
          tabindex="0"
          @click="handleSelectSession(sess.id)"
          @keydown.enter="handleSelectSession(sess.id)"
          class="w-full text-right p-2.5 rounded-xl transition-all group flex items-start justify-between gap-2 relative cursor-pointer"
          :class="
            chatStore.sessionId === sess.id
              ? 'bg-emerald-50/80 border border-emerald-200/90 text-emerald-950 font-medium'
              : 'hover:bg-slate-50 text-slate-700 border border-transparent'
          "
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5 text-xs font-semibold truncate mb-1">
              <span
                class="w-2 h-2 rounded-full shrink-0"
                :class="chatStore.sessionId === sess.id ? 'bg-emerald-500' : 'bg-slate-300'"
              ></span>
              <span class="truncate">{{ sess.title || 'گفتگوی تشخیصی' }}</span>
            </div>

            <p
              v-if="sess.last_message"
              class="text-[11px] text-slate-400 truncate leading-tight font-normal"
            >
              {{ sess.last_message }}
            </p>

            <div class="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
              <span>{{ formatSessionDate(sess.updated_at || sess.created_at) }}</span>
              <span v-if="sess.message_count" class="px-1.5 py-0.2 bg-slate-100 rounded-md text-slate-600">
                {{ sess.message_count }} پیام
              </span>
            </div>
          </div>

          <!-- Delete Session Action -->
          <button
            type="button"
            @click="(e) => handleDeleteSession(e, sess.id)"
            title="حذف گفتگو"
            class="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all shrink-0 cursor-pointer"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Chat Content Container -->
    <div class="flex-1 flex flex-col min-w-0 bg-white">
      <!-- Chat Header Bar -->
      <div class="px-4 py-3 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div class="flex items-center gap-2">
          <!-- Mobile Sidebar Toggle -->
          <button
            @click="showSessionsSidebar = !showSessionsSidebar"
            class="p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 md:hidden"
            title="نمایش تاریخچه"
          >
            <History class="w-4 h-4 text-emerald-600" />
          </button>

          <!-- Plant Context Selector -->
          <div class="flex items-center space-x-2 space-x-reverse">
            <Flower2 class="w-5 h-5 text-emerald-600 shrink-0" />
            <label for="plant-context-select" class="text-xs font-semibold text-slate-700 shrink-0">
              پرونده گیاه:
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
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center gap-2">
          <button
            @click="handleNewChat"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium shadow-xs transition-colors"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>گفتگوی جدید</span>
          </button>
        </div>
      </div>

      <!-- Messages Scrollable Body -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-slate-50/40"
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
              <span class="text-[11px] text-slate-500">ارزیابی سازگاری بستر، فاز فنولوژیکی و استخراج داده‌ها از دیتابیس</span>
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
  </div>
</template>

