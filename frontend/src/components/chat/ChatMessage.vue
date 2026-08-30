<script setup lang="ts">
import { computed } from 'vue';
import { User, Sprout, AlertTriangle } from 'lucide-vue-next';
import type { UIMessage } from '../../types/chat';
import RiskTriageBanner from './RiskTriageBanner.vue';
import FourWeekScheduleCard from './FourWeekScheduleCard.vue';
import { usePlantStore } from '../../stores/usePlantStore';

const props = defineProps<{
  message: UIMessage;
}>();

const plantStore = usePlantStore();

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

// Format message text with paragraphs
const formattedLines = computed(() => {
  return props.message.text.split('\n');
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
      :class="
        isAgent
          ? 'bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-emerald-600/20'
          : 'bg-slate-700 text-white shadow-slate-700/20'
      "
    >
      <Sprout v-if="isAgent" class="w-5 h-5" />
      <User v-else class="w-5 h-5" />
    </div>

    <!-- Message Body -->
    <div
      class="max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 shadow-sm"
      :class="
        isAgent
          ? 'bg-white text-slate-800 border border-slate-200/90 rounded-tr-none'
          : 'bg-emerald-600 text-white rounded-tl-none'
      "
    >
      <!-- Meta Header for Agent -->
      <div v-if="isAgent" class="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-slate-100 text-xs">
        <div class="flex items-center gap-1.5 font-bold text-emerald-800">
          <span>دستیار گیاه‌پزشک (PhytoAgent)</span>
          <span v-if="plantName" class="text-slate-400 font-normal">| پرونده: {{ plantName }}</span>
        </div>
        <span class="text-slate-400 text-[11px]">{{ formattedTime }}</span>
      </div>

      <!-- User Timestamp -->
      <div v-else class="flex items-center justify-end text-[11px] text-emerald-100 mb-1">
        <span>{{ formattedTime }}</span>
      </div>

      <!-- Main Message Text with RTL styling -->
      <div class="text-sm leading-relaxed space-y-2 whitespace-pre-wrap font-normal" :class="isAgent ? 'text-slate-800' : 'text-emerald-50'">
        <p v-for="(line, idx) in formattedLines" :key="idx" class="min-h-[1rem]">
          {{ line }}
        </p>
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

      <!-- CRITICAL BLOCKER Substrate Triage Banner -->
      <RiskTriageBanner
        v-if="isAgent && message.risk_level === 'CRITICAL_BLOCKER'"
      />

      <!-- 4-Week Dynamic Nutrition Schedule Widget -->
      <FourWeekScheduleCard
        v-if="isAgent && message.calculated_schedule"
        :schedule="message.calculated_schedule"
        :plant-id="message.plant_id"
      />

      <!-- Parsed Extracted Entities Badges -->
      <div
        v-if="isAgent && message.extracted_entities && Object.keys(message.extracted_entities).length > 0"
        class="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap items-center gap-1.5 text-[11px]"
      >
        <span class="text-slate-400 font-medium">پارامترهای شناسایی‌شده:</span>
        <span
          v-if="message.extracted_entities.species_id"
          class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md"
        >
          گونه: {{ message.extracted_entities.species_id }}
        </span>
        <span
          v-if="message.extracted_entities.substrate_type"
          class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md"
        >
          بستر: {{ message.extracted_entities.substrate_type }}
        </span>
        <span
          v-if="message.extracted_entities.current_phase"
          class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md"
        >
          فاز: {{ message.extracted_entities.current_phase }}
        </span>
      </div>
    </div>
  </div>
</template>
