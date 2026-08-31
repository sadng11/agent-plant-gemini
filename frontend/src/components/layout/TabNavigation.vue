<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Flower2, MessageSquareText } from 'lucide-vue-next';
import { usePlantStore } from '../../stores/usePlantStore';
import { useChatStore } from '../../stores/useChatStore';

const route = useRoute();
const router = useRouter();
const plantStore = usePlantStore();
const chatStore = useChatStore();

const isGardenActive = computed(() => route.path.startsWith('/garden') || route.path === '/');
const isChatActive = computed(() => route.path.startsWith('/chat'));

const plantCount = computed(() => plantStore.plants.length);
const attentionCount = computed(() =>
  plantStore.plants.filter(
    (p) =>
      p.health_status === 'ROOT_ROT_RISK' ||
      p.health_status === 'CRITICAL' ||
      p.health_status === 'SICK_OR_SYMPTOMATIC' ||
      p.health_status === 'PATHOLOGY' ||
      p.health_status === 'SUB_OPTIMAL' ||
      p.health_status === 'WARNING' ||
      p.health_status === 'SICK'
  ).length
);

function navigateTo(path: string) {
  router.push(path);
}
</script>

<template>
  <div class="bg-white border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <nav class="flex space-x-2 space-x-reverse py-2 overflow-x-auto" aria-label="Tabs">
        <!-- Garden Tab -->
        <button
          @click="navigateTo('/garden')"
          class="flex items-center space-x-2 space-x-reverse px-4 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 whitespace-nowrap cursor-pointer"
          :class="
            isGardenActive
              ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/30'
              : 'text-slate-600 hover:text-emerald-700 hover:bg-emerald-50'
          "
        >
          <Flower2 class="w-4 h-4" />
          <span>🪴 باغچه من</span>
          <span
            class="px-2 py-0.5 text-xs font-semibold rounded-full"
            :class="isGardenActive ? 'bg-emerald-700 text-emerald-100' : 'bg-slate-200 text-slate-700'"
          >
            {{ plantCount }}
          </span>
          <span
            v-if="attentionCount > 0"
            class="flex items-center text-xs px-1.5 py-0.5 rounded-full bg-rose-500 text-white animate-pulse"
            title="گیاهان نیازمند توجه فوری"
          >
            {{ attentionCount }} ⚠️
          </span>
        </button>

        <!-- Diagnostic Chat Tab -->
        <button
          @click="navigateTo('/chat')"
          class="flex items-center space-x-2 space-x-reverse px-4 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 whitespace-nowrap cursor-pointer"
          :class="
            isChatActive
              ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/30'
              : 'text-slate-600 hover:text-emerald-700 hover:bg-emerald-50'
          "
        >
          <MessageSquareText class="w-4 h-4" />
          <span>💬 کلینیک و چت تشخیصی</span>
          <span
            v-if="chatStore.selectedPlantId"
            class="px-2 py-0.5 text-[11px] font-medium rounded-full"
            :class="isChatActive ? 'bg-emerald-700 text-emerald-100' : 'bg-emerald-100 text-emerald-800'"
          >
            مشاوره اختصاصی
          </span>
        </button>

        <!-- Knowledge Base Tab (Hidden/Disabled temporarily from UI per user request, code preserved) -->
        <!--
        <button
          @click="navigateTo('/kb')"
          class="flex items-center space-x-2 space-x-reverse px-4 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 whitespace-nowrap"
          :class="
            route.path.startsWith('/kb')
              ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/30'
              : 'text-slate-600 hover:text-emerald-700 hover:bg-emerald-50'
          "
        >
          <BookOpen class="w-4 h-4" />
          <span>📚 دانشنامه و پایگاه دانش</span>
        </button>
        -->
      </nav>
    </div>
  </div>
</template>

