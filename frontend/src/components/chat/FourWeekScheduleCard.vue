<script setup lang="ts">
import { ref } from 'vue';
import { Calendar, CheckCircle2, AlertTriangle, Sparkles } from 'lucide-vue-next';
import type { CalculatedSchedule } from '../../types/chat';
import { usePlantStore } from '../../stores/usePlantStore';

const props = defineProps<{
  schedule: CalculatedSchedule;
  plantId?: string | null;
}>();

const plantStore = usePlantStore();
const loggedWeeks = ref<Record<number, boolean>>({});
const isLogging = ref<Record<number, boolean>>({});
const notification = ref<string | null>(null);

async function handleLogWeek(weekNum: number, actionText: string, supplements: string[]) {
  if (!props.plantId) {
    notification.value = 'برای ثبت این اقدام در پرونده، لطفاً ابتدا گیاه مورد نظر را از بالای صفحه انتخاب کنید.';
    setTimeout(() => (notification.value = null), 4000);
    return;
  }

  isLogging.value[weekNum] = true;
  try {
    await plantStore.logCareEvent(props.plantId, 'FERTILIZING', {
      week_num: weekNum,
      action: actionText,
      applied_ratio: props.schedule.applied_ratio,
      supplements: supplements,
      date: new Date().toISOString(),
    });
    loggedWeeks.value[weekNum] = true;
    notification.value = `نوبت هفته ${weekNum} با موفقیت در پرونده گیاه ثبت گردید ✨`;
    setTimeout(() => (notification.value = null), 3500);
  } catch (err: any) {
    notification.value = 'خطا در ثبت رویداد در پرونده گیاه';
    setTimeout(() => (notification.value = null), 4000);
  } finally {
    isLogging.value[weekNum] = false;
  }
}

function getSupplementColor(sup: string): string {
  if (sup.includes('Cal-Mag') || sup.includes('کلسیم') || sup.includes('منیزیم')) {
    return 'bg-blue-100 text-blue-800 border-blue-200';
  }
  if (sup.includes('سیلیکات') || sup.includes('سیلیکا')) {
    return 'bg-amber-100 text-amber-800 border-amber-200';
  }
  if (sup.includes('هیومیک') || sup.includes('فولویک')) {
    return 'bg-purple-100 text-purple-800 border-purple-200';
  }
  if (sup.includes('فروت‌ست') || sup.includes('روی') || sup.includes('بور')) {
    return 'bg-rose-100 text-rose-800 border-rose-200';
  }
  return 'bg-emerald-100 text-emerald-800 border-emerald-200';
}
</script>

<template>
  <div class="my-4 bg-white border border-emerald-200/90 rounded-2xl p-4 shadow-card animate-slide-up">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
      <div class="flex items-center space-x-2 space-x-reverse">
        <div class="p-2 bg-emerald-100 text-emerald-800 rounded-xl">
          <Calendar class="w-5 h-5" />
        </div>
        <div>
          <h4 class="text-sm font-bold text-slate-900">
            برنامه ۴ هفته‌ای تغذیه و سلامت گیاه
          </h4>
          <p class="text-xs text-slate-500">
            طراحی‌شده بر اساس گونه، بستر رشد و فاز فنولوژیکی
          </p>
        </div>
      </div>

      <!-- Applied NPK Ratio Badge -->
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-500 font-medium">فرمول مبنا:</span>
        <span class="px-2.5 py-1 text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg shadow-sm">
          {{ schedule.applied_ratio }}
        </span>
      </div>
    </div>

    <!-- Banned Elements Warning if any -->
    <div
      v-if="schedule.banned_elements && schedule.banned_elements.length > 0"
      class="mt-3 p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2"
    >
      <AlertTriangle class="w-4 h-4 text-amber-600 shrink-0" />
      <div>
        <span class="font-bold">محدودیت‌های اختصاصی:</span>
        مصرف {{ schedule.banned_elements.join('، ') }} در این شرایط ممنوع و آسیب‌زا است.
      </div>
    </div>

    <!-- Notification Toast inside card -->
    <div
      v-if="notification"
      class="mt-3 p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between animate-fade-in"
    >
      <div class="flex items-center gap-2">
        <Sparkles class="w-4 h-4 text-emerald-600 shrink-0" />
        <span>{{ notification }}</span>
      </div>
    </div>

    <!-- 4-Week Grid -->
    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
      <div
        v-for="week in schedule.weeks"
        :key="week.week_num"
        class="p-3.5 rounded-xl border transition-all duration-200 relative flex flex-col justify-between"
        :class="
          loggedWeeks[week.week_num]
            ? 'bg-emerald-50/70 border-emerald-300'
            : 'bg-slate-50/70 border-slate-200 hover:border-emerald-300 hover:bg-white'
        "
      >
        <div>
          <!-- Week Title & Dose Factor -->
          <div class="flex items-center justify-between mb-2">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-bold" :class="loggedWeeks[week.week_num] ? 'bg-emerald-200 text-emerald-900' : 'bg-slate-200 text-slate-800'">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
              هفته {{ week.week_num }}
            </span>
            <span v-if="week.dose_factor" class="text-[11px] font-medium text-slate-500">
              {{ week.dose_factor }}
            </span>
          </div>

          <!-- Action Description -->
          <p class="text-xs font-semibold text-slate-800 leading-relaxed">
            {{ week.action }}
          </p>

          <!-- Supplements Badges -->
          <div v-if="week.supplements && week.supplements.length > 0" class="mt-2.5 flex flex-wrap gap-1.5">
            <span
              v-for="sup in week.supplements"
              :key="sup"
              class="px-2 py-0.5 text-[11px] font-medium rounded-md border"
              :class="getSupplementColor(sup)"
            >
              {{ sup }}
            </span>
          </div>
        </div>

        <!-- Action Button -->
        <div class="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between">
          <span class="text-[11px] text-slate-400">
            {{ loggedWeeks[week.week_num] ? 'در پرونده ثبت شد' : 'ثبت اقدام' }}
          </span>

          <button
            @click="handleLogWeek(week.week_num, week.action, week.supplements)"
            :disabled="loggedWeeks[week.week_num] || isLogging[week.week_num]"
            class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition-all duration-150"
            :class="
              loggedWeeks[week.week_num]
                ? 'bg-emerald-600 text-white cursor-default'
                : 'bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-300 shadow-sm active:scale-95'
            "
          >
            <CheckCircle2 class="w-3.5 h-3.5" :class="loggedWeeks[week.week_num] ? 'text-white' : 'text-emerald-600'" />
            <span>{{ loggedWeeks[week.week_num] ? 'ثبت شد ✓' : isLogging[week.week_num] ? 'در حال ثبت...' : 'ثبت انجام در پرونده' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
