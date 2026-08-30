<script setup lang="ts">
import { computed } from 'vue';
import { AlertOctagon, ShieldAlert, ArrowLeft, Bug } from 'lucide-vue-next';
import { useChatStore } from '../../stores/useChatStore';

const props = withDefaults(
  defineProps<{
    riskType?: 'PATHOLOGY' | 'SUBSTRATE' | string | null;
    customMessage?: string | null;
  }>(),
  {
    riskType: 'SUBSTRATE',
    customMessage: '',
  }
);

const chatStore = useChatStore();

const isPathology = computed(() => props.riskType === 'PATHOLOGY');

const title = computed(() => {
  return isPathology.value
    ? '⛔ توقف کوددهی و هشدار سلامت گیاه'
    : '⛔ توقف تغذیه و هشدار بحرانی بستر';
});

const defaultDescription = computed(() => {
  if (isPathology.value) {
    return 'گیاه دارای علائم بیماری، زردی برگ یا آفت است. به دلیل آسیب به بافت‌ها و ریشه‌های مویین، مصرف هرگونه کود شیمیایی تا زمان درمان کامل و رفع علائم اکیداً ممنوع است.';
  }
  return 'بستر انتخابی (خاک رسی و سنگین باغچه‌ای) به دلیل چگالی بالا و عدم تخلخل، منجر به خفگی فیزیکی ریشه‌ها، انباشت رطوبت ماندگار و پوسیدگی حتمی طوقه می‌شود. در این وضعیت، مصرف هرگونه کود شیمیایی باعث سمیت اسمزی و تسریع تخریب ریشه خواهد شد.';
});

const actionLabel = computed(() => {
  return isPathology.value
    ? 'اقدام ضروری: توقف کامل کوددهی، ایزولاسیون گیاه و کنترل آفت یا تنظیم آبیاری'
    : 'اقدام ضروری: توقف کامل کوددهی و تعویض بستر به آروئید میکس متخلخل';
});

const buttonLabel = computed(() => {
  return isPathology.value
    ? 'راهنمای درمان آفت و احیای سلامت'
    : 'راهنمای تعویض گلدان و بستر مناسب';
});

function handleAction() {
  if (isPathology.value) {
    chatStore.sendMessage('لطفاً راهنمای کامل درمان آفت، رفع زردی برگ و احیای سلامت گیاه را ارائه دهید.');
  } else {
    chatStore.sendMessage('لطفاً راهنمای کامل و گام‌به‌گام تعویض گلدان، ترکیب بستر استاندارد (آروئید میکس) و مراقبت پس از تعویض را ارائه دهید.');
  }
}
</script>

<template>
  <div class="my-4 p-4 rounded-2xl bg-rose-50 border-2 border-rose-400 text-rose-900 shadow-sm animate-fade-in">
    <div class="flex items-start space-x-3 space-x-reverse">
      <div class="p-2 rounded-xl bg-rose-500 text-white shrink-0 shadow-sm">
        <Bug v-if="isPathology" class="w-6 h-6 animate-pulse" />
        <ShieldAlert v-else class="w-6 h-6 animate-pulse" />
      </div>

      <div class="flex-1">
        <div class="flex items-center justify-between">
          <h4 class="text-base font-bold text-rose-900 flex items-center gap-2">
            <span>{{ title }}</span>
          </h4>
          <span class="px-2 py-0.5 text-xs font-semibold bg-rose-200 text-rose-800 rounded-md">
            {{ isPathology ? 'هشدار بیماری/آفت' : 'ریسک بحرانی (CRITICAL_BLOCKER)' }}
          </span>
        </div>

        <p class="mt-2 text-sm text-rose-800 leading-relaxed font-normal">
          {{ customMessage || defaultDescription }}
        </p>

        <div class="mt-4 pt-3 border-t border-rose-200/80 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2 text-xs font-medium text-rose-700">
            <AlertOctagon class="w-4 h-4 text-rose-600 shrink-0" />
            <span>{{ actionLabel }}</span>
          </div>

          <button
            @click="handleAction"
            class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white text-xs font-semibold shadow-sm transition-all duration-150"
          >
            <span>{{ buttonLabel }}</span>
            <ArrowLeft class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
