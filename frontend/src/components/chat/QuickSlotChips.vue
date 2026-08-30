<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next';
import { useChatStore } from '../../stores/useChatStore';

const chatStore = useChatStore();

function handleSelect(chip: string) {
  chatStore.sendQuickSlotAnswer(chip);
}
</script>

<template>
  <div v-if="chatStore.activeQuickSlots.length > 0" class="p-3 bg-emerald-50/70 border-t border-emerald-100 animate-fade-in">
    <div class="max-w-4xl mx-auto flex items-center space-x-2 space-x-reverse overflow-x-auto py-1">
      <div class="flex items-center gap-1.5 text-xs font-semibold text-emerald-800 shrink-0">
        <Sparkles class="w-4 h-4 text-emerald-600 animate-spin-slow" />
        <span>انتخاب سریع:</span>
      </div>

      <div class="flex items-center gap-2 flex-wrap sm:flex-nowrap">
        <button
          v-for="chip in chatStore.activeQuickSlots"
          :key="chip"
          @click="handleSelect(chip)"
          class="px-3 py-1.5 rounded-full text-xs font-medium bg-white text-emerald-800 border border-emerald-300 hover:bg-emerald-600 hover:text-white hover:border-emerald-600 transition-all duration-150 shadow-sm shrink-0 active:scale-95 flex items-center gap-1"
        >
          <span>{{ chip }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
