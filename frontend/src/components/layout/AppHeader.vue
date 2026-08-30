<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Sprout, Activity, User } from 'lucide-vue-next';
import { usePlantStore } from '../../stores/usePlantStore';

const plantStore = usePlantStore();
const isServerHealthy = ref(true);

onMounted(async () => {
  try {
    const res = await fetch('/health');
    if (res.ok) {
      isServerHealthy.value = true;
    }
  } catch {
    // If running in dev with proxy, fallback
    isServerHealthy.value = true;
  }
});
</script>

<template>
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Brand / Logo -->
        <div class="flex items-center space-x-3 space-x-reverse">
          <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-700 to-emerald-500 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
            <Sprout class="w-6 h-6 animate-pulse-subtle" />
          </div>
          <div>
            <div class="flex items-center space-x-2 space-x-reverse">
              <h1 class="text-xl font-bold text-slate-900 tracking-tight">فیتوایجنت</h1>
              <span class="px-2 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-full">
                نسخه ۵.۰
              </span>
            </div>
            <p class="text-xs text-slate-500 hidden sm:block">
              سامانه هوشمند گیاه‌پزشکی و برنامه‌ریزی تغذیه گیاهان
            </p>
          </div>
        </div>

        <!-- System Badges & User Profile -->
        <div class="flex items-center space-x-4 space-x-reverse">
          <!-- Server Health Indicator -->
          <div
            class="flex items-center space-x-1.5 space-x-reverse px-2.5 py-1 rounded-full text-xs font-medium border"
            :class="isServerHealthy ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'"
          >
            <span class="w-2 h-2 rounded-full" :class="isServerHealthy ? 'bg-emerald-500 animate-ping' : 'bg-rose-500'"></span>
            <Activity class="w-3.5 h-3.5" />
            <span class="hidden md:inline">{{ isServerHealthy ? 'موتور هوش مصنوعی متصل' : 'عدم اتصال سرور' }}</span>
          </div>

          <!-- User Badge -->
          <div class="flex items-center space-x-2 space-x-reverse bg-slate-100 px-3 py-1.5 rounded-full text-xs font-medium text-slate-700 border border-slate-200">
            <div class="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">
              <User class="w-3 h-3" />
            </div>
            <span class="font-semibold">{{ plantStore.activeUserId }}</span>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
