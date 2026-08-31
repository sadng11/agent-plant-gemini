<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  Droplets,
  MessageSquarePlus,
  FileText,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Sprout,
  Sun,
  Layers,
} from 'lucide-vue-next';
import type { PlantResponse } from '../../types/plant';
import { usePlantStore } from '../../stores/usePlantStore';
import { useKbStore } from '../../stores/useKbStore';

const props = defineProps<{
  plant: PlantResponse;
}>();

const emit = defineEmits<{
  (e: 'open-history', plant: PlantResponse): void;
  (e: 'start-chat', plant: PlantResponse): void;
}>();

const plantStore = usePlantStore();
const kbStore = useKbStore();

const isWatering = ref(false);
const justWatered = ref(false);

const speciesName = computed(() => {
  return kbStore.getSpeciesName(props.plant.species_id);
});

const substrateLabel = computed(() => {
  return kbStore.getSubstrateLabel(props.plant.substrate_type);
});

const phaseLabel = computed(() => {
  return kbStore.getPhaseLabel(props.plant.current_phase);
});

const healthBadge = computed(() => {
  const status = props.plant.health_status;
  if (status === 'ROOT_ROT_RISK') {
    return {
      label: '⛔ خطر پوسیدگی ریشه (بستر نامناسب)',
      bgClass: 'bg-rose-100 text-rose-800 border-rose-200',
      icon: AlertTriangle,
    };
  }
  if (
    status === 'SICK_OR_SYMPTOMATIC' ||
    status === 'CRITICAL' ||
    status === 'PATHOLOGY' ||
    status === 'SICK'
  ) {
    return {
      label: '🩺 دارای علائم تنش / بیماری / آفت',
      bgClass: 'bg-red-100 text-red-800 border-red-200',
      icon: AlertTriangle,
    };
  }
  if (status === 'SUB_OPTIMAL' || status === 'WARNING') {
    return {
      label: '⚠️ هشدار تغذیه‌ای',
      bgClass: 'bg-amber-100 text-amber-800 border-amber-200',
      icon: AlertTriangle,
    };
  }
  return {
    label: 'سالم و پایدار',
    bgClass: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    icon: CheckCircle2,
  };
});

async function handleWatering() {
  isWatering.value = true;
  try {
    await plantStore.logCareEvent(props.plant.id, 'WATERING', {
      note: 'ثبت سریع آبیاری از داشبورد باغچه',
      date: new Date().toISOString(),
    });
    justWatered.value = true;
    setTimeout(() => (justWatered.value = false), 3000);
  } catch (err) {
    alert('خطا در ثبت آبیاری');
  } finally {
    isWatering.value = false;
  }
}

async function handleDelete() {
  if (confirm(`آیا از حذف گیاه «${props.plant.nickname}» و تمام پرونده‌های آن اطمینان دارید؟`)) {
    try {
      await plantStore.removePlant(props.plant.id);
    } catch (err) {
      alert('خطا در حذف گیاه');
    }
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl border border-slate-200 p-5 shadow-card hover:shadow-lg transition-all duration-200 flex flex-col justify-between group">
    <div>
      <!-- Header with Nickname and Health Badge -->
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-center space-x-3 space-x-reverse">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-100 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0 group-hover:scale-105 transition-transform">
            <Sprout class="w-6 h-6" />
          </div>
          <div>
            <h3 class="text-base font-bold text-slate-900 leading-snug">
              {{ plant.nickname }}
            </h3>
            <p class="text-xs text-slate-500 font-medium mt-0.5">
              {{ speciesName }}
            </p>
          </div>
        </div>

        <!-- Health Status Badge -->
        <span
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border shrink-0"
          :class="healthBadge.bgClass"
        >
          <component :is="healthBadge.icon" class="w-3.5 h-3.5" />
          <span>{{ healthBadge.label }}</span>
        </span>
      </div>

      <!-- Botanical Properties Grid -->
      <div class="mt-4 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
        <div class="flex items-center gap-1.5 text-slate-600 bg-slate-50 p-2 rounded-xl">
          <Layers class="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <div class="truncate">
            <span class="text-slate-400 block text-[10px]">بستر کشت:</span>
            <span class="font-medium truncate block" :title="substrateLabel">{{ substrateLabel }}</span>
          </div>
        </div>

        <div class="flex items-center gap-1.5 text-slate-600 bg-slate-50 p-2 rounded-xl">
          <Sun class="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <div class="truncate">
            <span class="text-slate-400 block text-[10px]">فاز رشدی:</span>
            <span class="font-medium truncate block" :title="phaseLabel">{{ phaseLabel }}</span>
          </div>
        </div>
      </div>

      <!-- Traits Tags if any -->
      <div v-if="plant.traits && plant.traits.length > 0" class="mt-2.5 flex flex-wrap gap-1">
        <span
          v-for="t in plant.traits"
          :key="t"
          class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
        >
          ✨ {{ kbStore.getTraitLabel(t) }}
        </span>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="mt-5 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
      <!-- Quick Watering Button -->
      <button
        @click="handleWatering"
        :disabled="isWatering"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150 shadow-sm"
        :class="
          justWatered
            ? 'bg-emerald-600 text-white'
            : 'bg-blue-50 text-blue-700 hover:bg-blue-100 active:scale-95 border border-blue-200'
        "
      >
        <Droplets class="w-3.5 h-3.5" :class="justWatered ? 'text-white' : 'text-blue-600'" />
        <span>{{ justWatered ? 'آبیاری ثبت شد ✓' : isWatering ? 'در حال ثبت...' : '💧 ثبت آبیاری امروز' }}</span>
      </button>

      <div class="flex items-center gap-1.5">
        <!-- Start Chat Button -->
        <button
          @click="emit('start-chat', plant)"
          title="شروع مشاوره تشخیصی اختصاصی"
          class="p-2 rounded-xl bg-emerald-50 text-emerald-700 hover:bg-emerald-600 hover:text-white transition-colors duration-150"
        >
          <MessageSquarePlus class="w-4 h-4" />
        </button>

        <!-- View History Button -->
        <button
          @click="emit('open-history', plant)"
          title="مشاهده پرونده و تایم‌لاین مراقبت"
          class="p-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors duration-150"
        >
          <FileText class="w-4 h-4" />
        </button>

        <!-- Delete Button -->
        <button
          @click="handleDelete"
          title="حذف گیاه از باغچه"
          class="p-2 rounded-xl bg-slate-50 text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors duration-150"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
