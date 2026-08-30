<script setup lang="ts">
import { AlertOctagon, ShieldAlert, ArrowLeft } from 'lucide-vue-next';
import { useChatStore } from '../../stores/useChatStore';

defineProps<{
  customMessage?: string;
}>();

const chatStore = useChatStore();

function handleRepotGuide() {
  chatStore.sendMessage('لطفاً راهنمای کامل و گام‌به‌گام تعویض گلدان، ترکیب بستر استاندارد (آروئید میکس) و مراقبت پس از تعویض را ارائه دهید.');
}
</script>

<template>
  <div class="my-4 p-4 rounded-2xl bg-rose-50 border-2 border-rose-400 text-rose-900 shadow-sm animate-fade-in">
    <div class="flex items-start space-x-3 space-x-reverse">
      <div class="p-2 rounded-xl bg-rose-500 text-white shrink-0 shadow-sm">
        <ShieldAlert class="w-6 h-6 animate-pulse" />
      </div>

      <div class="flex-1">
        <div class="flex items-center justify-between">
          <h4 class="text-base font-bold text-rose-900 flex items-center gap-2">
            <span>⛔ توقف تغذیه و هشدار بحرانی بستر</span>
          </h4>
          <span class="px-2 py-0.5 text-xs font-semibold bg-rose-200 text-rose-800 rounded-md">
            ریسک بحرانی (CRITICAL_BLOCKER)
          </span>
        </div>

        <p class="mt-2 text-sm text-rose-800 leading-relaxed font-normal">
          {{
            customMessage ||
            'بستر انتخابی (خاک رسی و سنگین باغچه‌ای) به دلیل چگالی بالا و عدم تخلخل، منجر به خفگی فیزیکی ریشه‌ها، انباشت رطوبت ماندگار و پوسیدگی حتمی طوقه می‌شود. در این وضعیت، مصرف هرگونه کود شیمیایی باعث سمیت اسمزی و تسریع تخریب ریشه خواهد شد.'
          }}
        </p>

        <div class="mt-4 pt-3 border-t border-rose-200/80 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2 text-xs font-medium text-rose-700">
            <AlertOctagon class="w-4 h-4 text-rose-600 shrink-0" />
            <span>اقدام ضروری: توقف کامل کوددهی و تعویض بستر به آروئید میکس متخلخل</span>
          </div>

          <button
            @click="handleRepotGuide"
            class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white text-xs font-semibold shadow-sm transition-all duration-150"
          >
            <span>راهنمای تعویض گلدان و بستر مناسب</span>
            <ArrowLeft class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
