<script setup lang="ts">
import { computed } from 'vue';
import { User, Sprout, AlertTriangle, AlertCircle, RotateCcw } from 'lucide-vue-next';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import type { UIMessage } from '../../types/chat';
import RiskTriageBanner from './RiskTriageBanner.vue';
import FourWeekScheduleCard from './FourWeekScheduleCard.vue';
import { usePlantStore } from '../../stores/usePlantStore';
import { useChatStore } from '../../stores/useChatStore';

const props = defineProps<{
  message: UIMessage;
}>();

const plantStore = usePlantStore();
const chatStore = useChatStore();

const isAgent = computed(() => props.message.sender === 'agent');

const formattedTime = computed(() => {
  const d = new Date(props.message.timestamp);
  return d.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
});

const plantName = computed(() => {
  if (!props.message.plant_id) return null;
  const plant = plantStore.getPlantById(props.message.plant_id);
  return plant ? plant.nickname : null;
});

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true,
});

// Parse markdown securely with DOMPurify
const parsedMarkdown = computed(() => {
  if (!props.message.text) return '';
  const rawHtml = marked.parse(props.message.text) as string;
  return DOMPurify.sanitize(rawHtml);
});
</script>

<template>
  <div
    class="flex items-start space-x-3 space-x-reverse transition-all duration-200"
    :class="isAgent ? 'justify-start' : 'justify-start flex-row-reverse space-x-reverse'"
  >
    <!-- Avatar -->
    <div
      class="w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 shadow-sm"
      :class="[
        isAgent
          ? message.is_error
            ? 'bg-gradient-to-br from-rose-500 to-rose-700 text-white shadow-rose-600/20'
            : 'bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-emerald-600/20'
          : message.is_failed
            ? 'bg-gradient-to-br from-rose-600 to-rose-800 text-white shadow-rose-600/20'
            : 'bg-slate-700 text-white shadow-slate-700/20'
      ]"
    >
      <AlertCircle v-if="(isAgent && message.is_error) || (!isAgent && message.is_failed)" class="w-5 h-5" />
      <Sprout v-else-if="isAgent" class="w-5 h-5" />
      <User v-else class="w-5 h-5" />
    </div>

    <!-- Message Body -->
    <div
      class="max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 shadow-sm"
      :class="[
        isAgent
          ? message.is_error
            ? 'bg-rose-50/80 text-slate-800 border border-rose-200 rounded-tr-none'
            : 'bg-white text-slate-800 border border-slate-200/90 rounded-tr-none'
          : message.is_failed
            ? 'bg-rose-700 text-white rounded-tl-none border border-rose-500 shadow-rose-700/10'
            : 'bg-emerald-600 text-white rounded-tl-none'
      ]"
    >
      <!-- Meta Header for Agent -->
      <div v-if="isAgent" class="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-slate-100 text-xs">
        <div class="flex items-center gap-1.5 font-bold" :class="message.is_error ? 'text-rose-800' : 'text-emerald-800'">
          <span>{{ message.is_error ? 'خطا در پردازش درخواست' : 'دستیار گیاه‌پزشک (PhytoAgent)' }}</span>
          <span v-if="plantName" class="text-slate-400 font-normal">| پرونده: {{ plantName }}</span>
        </div>
        <span class="text-slate-400 text-[11px]">{{ formattedTime }}</span>
      </div>

      <!-- User Timestamp & Failed Status -->
      <div v-else class="flex items-center justify-between text-[11px] mb-1.5" :class="message.is_failed ? 'text-rose-200' : 'text-emerald-100'">
        <span v-if="message.is_failed" class="font-semibold flex items-center gap-1 text-amber-200">
          <AlertTriangle class="w-3.5 h-3.5" />
          ارسال به سرور با خطا مواجه شد
        </span>
        <span v-else></span>
        <span>{{ formattedTime }}</span>
      </div>

      <!-- Streaming Thinking State (when waiting for first token) -->
      <div v-if="isAgent && message.is_streaming && !message.text" class="flex items-center gap-2 py-1 text-slate-500 text-sm">
        <span class="flex gap-1 items-center">
          <span class="w-2 h-2 rounded-full bg-emerald-600 animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 rounded-full bg-emerald-600 animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 rounded-full bg-emerald-600 animate-bounce" style="animation-delay: 300ms"></span>
        </span>
        <span class="text-xs text-slate-400 font-medium">در حال بررسی و تنظیم نسخه گیاه‌پزشکی...</span>
      </div>

      <!-- Main Message Text with Markdown rendering and RTL styling -->
      <div
        v-else
        class="text-sm leading-relaxed font-normal markdown-body inline"
        :class="isAgent ? 'markdown-agent text-slate-800' : 'markdown-user text-white'"
      >
        <span v-html="parsedMarkdown" />
        <span
          v-if="isAgent && message.is_streaming"
          class="inline-block w-1.5 h-4 -mb-0.5 mr-1 bg-emerald-600 rounded-xs animate-pulse"
        />
      </div>

      <!-- User Message Retry Action Button -->
      <div
        v-if="!isAgent && message.is_failed"
        class="mt-3 pt-2.5 border-t border-rose-600/80 flex items-center justify-between gap-2"
      >
        <span class="text-xs text-rose-100 font-medium">عدم دریافت پاسخ از سرور</span>
        <button
          @click="chatStore.retryUserMessage(message.id)"
          :disabled="chatStore.isLoading"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-rose-50 active:bg-rose-100 text-rose-700 text-xs font-bold rounded-xl shadow-sm transition-all hover:shadow-md disabled:opacity-50 cursor-pointer"
        >
          <RotateCcw class="w-3.5 h-3.5" :class="{ 'animate-spin': chatStore.isLoading }" />
          <span>ارسال مجدد</span>
        </button>
      </div>

      <!-- Feasibility Warning Banner if UNREALISTIC -->
      <div
        v-if="isAgent && message.feasibility_status === 'UNREALISTIC'"
        class="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-start gap-2 animate-fade-in"
      >
        <AlertTriangle class="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <span class="font-bold">سنجش واقع‌گرایی بیولوژیکی:</span>
          هدف مطرح‌شده با وضعیت فیزیولوژیکی و محیط آپارتمانی گیاه ناسازگار است. رسیدن به این هدف نیازمند تکامل بلوغ رویشی و تنظیم دقیق نور و رطوبت بوده و صرفاً با کودهای فسفر بالا حاصل نمی‌شود.
        </div>
      </div>

      <!-- CRITICAL BLOCKER Risk Triage Banner (Pathology or Substrate) -->
      <RiskTriageBanner
        v-if="isAgent && message.risk_level === 'CRITICAL_BLOCKER'"
        :risk-type="message.risk_type"
        :custom-message="message.risk_message"
      />

      <!-- 4-Week Dynamic Nutrition Schedule Widget -->
      <FourWeekScheduleCard
        v-if="isAgent && message.calculated_schedule"
        :schedule="message.calculated_schedule"
        :plant-id="message.plant_id"
      />

      <!-- Parsed Extracted Entities Badges -->
      <div
        v-if="isAgent && message.extracted_entities && (message.extracted_entities.species_query || message.extracted_entities.species_id || message.extracted_entities.substrate_query || message.extracted_entities.substrate_type || (message.extracted_entities.health_status && message.extracted_entities.health_status !== 'UNKNOWN'))"
        class="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-1.5 text-[11px]"
      >
        <span class="text-slate-400 dark:text-slate-500 font-medium">پارامترهای شناسایی‌شده:</span>
        <span
          v-if="message.extracted_entities.species_query || message.extracted_entities.species_id"
          class="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 rounded-md font-medium"
        >
          گونه: {{ message.extracted_entities.species_query || message.extracted_entities.species_id }}
        </span>
        <span
          v-if="message.extracted_entities.substrate_query || message.extracted_entities.substrate_type"
          class="px-2 py-0.5 bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 rounded-md font-medium"
        >
          بستر: {{ message.extracted_entities.substrate_query || message.extracted_entities.substrate_type }}
        </span>
        <span
          v-if="message.extracted_entities.health_status === 'HEALTHY'"
          class="px-2 py-0.5 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 rounded-md font-medium"
        >
          وضعیت: سالم
        </span>
        <span
          v-else-if="message.extracted_entities.health_status === 'SICK_OR_SYMPTOMATIC'"
          class="px-2 py-0.5 bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 rounded-md font-medium"
        >
          وضعیت: دارای علائم بیماری / تنش
        </span>
      </div>

      <!-- Retry Button for Failed Message -->
      <div
        v-if="isAgent && message.is_error"
        class="mt-3 pt-2.5 border-t border-rose-200/80 flex items-center justify-between gap-2"
      >
        <span class="text-xs text-rose-700 font-medium">خطا در دریافت پاسخ</span>
        <button
          @click="chatStore.retryMessage(message.id)"
          :disabled="chatStore.isLoading"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white text-xs font-semibold rounded-xl shadow-sm transition-all hover:shadow-md disabled:opacity-50 cursor-pointer"
        >
          <RotateCcw class="w-3.5 h-3.5" :class="{ 'animate-spin': chatStore.isLoading }" />
          <span>تلاش مجدد</span>
        </button>
      </div>
    </div>
  </div>
</template>
