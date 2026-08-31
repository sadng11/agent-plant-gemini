<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import {
  Plus,
  Search,
  Flower2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
} from 'lucide-vue-next';
import type { PlantResponse } from '../../types/plant';
import { usePlantStore } from '../../stores/usePlantStore';
import { useKbStore } from '../../stores/useKbStore';
import { useChatStore } from '../../stores/useChatStore';
import PlantCard from './PlantCard.vue';
import AddPlantModal from './AddPlantModal.vue';
import PlantHistoryModal from './PlantHistoryModal.vue';

const router = useRouter();
const emit = defineEmits<{
  (e: 'navigate-to-chat'): void;
}>();

const plantStore = usePlantStore();
const kbStore = useKbStore();
const chatStore = useChatStore();

const searchQuery = ref('');
const filterStatus = ref<'ALL' | 'HEALTHY' | 'ATTENTION'>('ALL');
const showAddModal = ref(false);
const selectedPlantForHistory = ref<PlantResponse | null>(null);

onMounted(async () => {
  await Promise.all([
    plantStore.fetchPlants(),
    kbStore.fetchAllKb(),
  ]);
});

const filteredPlants = computed(() => {
  return plantStore.plants.filter((p) => {
    // Search query match
    const speciesName = kbStore.getSpeciesName(p.species_id).toLowerCase();
    const nickname = p.nickname.toLowerCase();
    const query = searchQuery.value.trim().toLowerCase();
    const matchesSearch = !query || nickname.includes(query) || speciesName.includes(query);

    // Status filter match
    if (filterStatus.value === 'HEALTHY') {
      return matchesSearch && (p.health_status === 'HEALTHY' || p.health_status === 'OPTIMAL');
    }
    if (filterStatus.value === 'ATTENTION') {
      return (
        matchesSearch &&
        (p.health_status === 'ROOT_ROT_RISK' ||
          p.health_status === 'CRITICAL' ||
          p.health_status === 'SUB_OPTIMAL' ||
          p.health_status === 'SICK_OR_SYMPTOMATIC' ||
          p.health_status === 'PATHOLOGY' ||
          p.health_status === 'WARNING' ||
          p.health_status === 'SICK')
      );
    }
    return matchesSearch;
  });
});

const stats = computed(() => {
  const total = plantStore.plants.length;
  const healthy = plantStore.plants.filter((p) => p.health_status === 'HEALTHY' || p.health_status === 'OPTIMAL').length;
  const attention = plantStore.plants.filter(
    (p) =>
      p.health_status === 'ROOT_ROT_RISK' ||
      p.health_status === 'CRITICAL' ||
      p.health_status === 'SUB_OPTIMAL' ||
      p.health_status === 'SICK_OR_SYMPTOMATIC' ||
      p.health_status === 'PATHOLOGY' ||
      p.health_status === 'WARNING' ||
      p.health_status === 'SICK'
  ).length;
  return { total, healthy, attention };
});

function handleOpenHistory(plant: PlantResponse) {
  selectedPlantForHistory.value = plant;
}

function handleStartChat(plant: PlantResponse) {
  chatStore.setContextPlant(plant.id);
  router.push({ path: '/chat', query: { plantId: plant.id } });
  emit('navigate-to-chat');
}
</script>

<template>
  <div class="space-y-6">
    <!-- Quick Statistics Summary Bar -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <!-- Total Plants -->
      <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex items-center justify-between">
        <div>
          <span class="text-xs font-semibold text-slate-500 block">تعداد کل گیاهان باغچه</span>
          <span class="text-2xl font-extrabold text-slate-900 mt-1 block">{{ stats.total }}</span>
        </div>
        <div class="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <Flower2 class="w-6 h-6" />
        </div>
      </div>

      <!-- Healthy Plants -->
      <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex items-center justify-between">
        <div>
          <span class="text-xs font-semibold text-slate-500 block">وضعیت سالم و پایدار</span>
          <span class="text-2xl font-extrabold text-emerald-600 mt-1 block">{{ stats.healthy }}</span>
        </div>
        <div class="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <CheckCircle2 class="w-6 h-6" />
        </div>
      </div>

      <!-- Attention Required -->
      <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex items-center justify-between">
        <div>
          <span class="text-xs font-semibold text-slate-500 block">نیازمند توجه و اصلاح بستر</span>
          <span class="text-2xl font-extrabold text-rose-600 mt-1 block">{{ stats.attention }}</span>
        </div>
        <div class="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center">
          <AlertTriangle class="w-6 h-6" />
        </div>
      </div>
    </div>

    <!-- Controls Bar: Search, Filters, Add Button -->
    <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex flex-wrap items-center justify-between gap-3">
      <!-- Search Input -->
      <div class="flex-1 min-w-[240px] relative">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="جستجوی نام یا گونه گیاه..."
          class="w-full rounded-xl border-slate-200 bg-slate-50/70 py-2 pr-10 pl-4 text-xs placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-emerald-500 transition-all"
        />
        <Search class="w-4 h-4 text-slate-400 absolute right-3 top-2.5" />
      </div>

      <!-- Status Filter Tabs -->
      <div class="flex items-center space-x-1.5 space-x-reverse bg-slate-100 p-1 rounded-xl text-xs font-medium">
        <button
          @click="filterStatus = 'ALL'"
          class="px-3 py-1.5 rounded-lg transition-all"
          :class="filterStatus === 'ALL' ? 'bg-white text-slate-900 shadow-sm font-bold' : 'text-slate-600 hover:text-slate-900'"
        >
          همه ({{ stats.total }})
        </button>
        <button
          @click="filterStatus = 'HEALTHY'"
          class="px-3 py-1.5 rounded-lg transition-all"
          :class="filterStatus === 'HEALTHY' ? 'bg-white text-emerald-700 shadow-sm font-bold' : 'text-slate-600 hover:text-emerald-700'"
        >
          سالم ({{ stats.healthy }})
        </button>
        <button
          @click="filterStatus = 'ATTENTION'"
          class="px-3 py-1.5 rounded-lg transition-all"
          :class="filterStatus === 'ATTENTION' ? 'bg-white text-rose-700 shadow-sm font-bold' : 'text-slate-600 hover:text-rose-700'"
        >
          هشدار ({{ stats.attention }})
        </button>
      </div>

      <!-- Add Plant Button -->
      <button
        @click="showAddModal = true"
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-bold text-xs shadow-md shadow-emerald-600/20 transition-all shrink-0"
      >
        <Plus class="w-4 h-4" />
        <span>افزودن گیاه جدید</span>
      </button>
    </div>

    <!-- Plants Grid -->
    <div v-if="filteredPlants.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <PlantCard
        v-for="plant in filteredPlants"
        :key="plant.id"
        :plant="plant"
        @open-history="handleOpenHistory"
        @start-chat="handleStartChat"
      />
    </div>

    <!-- Empty State -->
    <div
      v-else
      class="bg-white rounded-3xl border border-dashed border-slate-300 p-12 text-center flex flex-col items-center justify-center max-w-lg mx-auto"
    >
      <div class="w-16 h-16 rounded-3xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
        <Sparkles class="w-8 h-8" />
      </div>
      <h3 class="text-base font-bold text-slate-900 mb-1">
        {{ searchQuery ? 'گیاهی با این مشخصات یافت نشد' : 'باغچه دیجیتال شما هنوز گیاهی ندارد' }}
      </h3>
      <p class="text-xs text-slate-500 max-w-sm mb-5 leading-relaxed">
        {{
          searchQuery
            ? 'عبارت جستجو را تغییر دهید یا فیلترهای وضعیت را بازنشانی کنید.'
            : 'اولین گیاه خود را به باغچه اضافه کنید تا تقویم تغذیه، پایش وضعیت سلامت و پرونده پزشکی آن فعال شود.'
        }}
      </p>
      <button
        @click="showAddModal = true"
        class="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-md shadow-emerald-600/20 transition-all"
      >
        <Plus class="w-4 h-4" />
        <span>افزودن اولین گیاه به باغچه</span>
      </button>
    </div>

    <!-- Add Plant Modal -->
    <AddPlantModal
      v-if="showAddModal"
      @close="showAddModal = false"
      @created="plantStore.fetchPlants"
    />

    <!-- Plant History Modal -->
    <PlantHistoryModal
      v-if="selectedPlantForHistory"
      :plant="selectedPlantForHistory"
      @close="selectedPlantForHistory = null"
    />
  </div>
</template>
