<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useKbStore } from '../../stores/useKbStore';

const kbStore = useKbStore();
const activeKbSubTab = ref<'species' | 'substrates' | 'traits' | 'phases'>('species');

onMounted(async () => {
  if (!kbStore.isLoaded) {
    await kbStore.fetchAllKb();
  }
});
</script>

<template>
  <div class="space-y-6">
    <!-- KB Subtabs -->
    <div class="bg-white rounded-2xl border border-slate-200 p-2 shadow-sm flex items-center space-x-2 space-x-reverse overflow-x-auto">
      <button
        @click="activeKbSubTab = 'species'"
        class="px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap"
        :class="activeKbSubTab === 'species' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'"
      >
        🌿 شناسنامه گونه‌ها ({{ kbStore.speciesList.length }})
      </button>
      <button
        @click="activeKbSubTab = 'substrates'"
        class="px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap"
        :class="activeKbSubTab === 'substrates' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'"
      >
        🪴 بسترها و ضرایب تغذیه ({{ kbStore.substrateList.length }})
      </button>
      <button
        @click="activeKbSubTab = 'traits'"
        class="px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap"
        :class="activeKbSubTab === 'traits' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'"
      >
        ✨ صفات و گاردریل‌ها ({{ kbStore.traitList.length }})
      </button>
      <button
        @click="activeKbSubTab = 'phases'"
        class="px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap"
        :class="activeKbSubTab === 'phases' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'"
      >
        🌱 فازهای فنولوژیکی ({{ kbStore.phaseList.length }})
      </button>
    </div>

    <!-- Species View -->
    <div v-if="activeKbSubTab === 'species'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="sp in kbStore.speciesList"
        :key="sp.species_id"
        class="bg-white rounded-2xl border border-slate-200 p-5 shadow-card space-y-3"
      >
        <div class="flex items-start justify-between">
          <div>
            <h4 class="text-base font-bold text-slate-900">{{ sp.persian_name }}</h4>
            <p class="text-xs text-emerald-700 italic font-mono">{{ sp.scientific_name }}</p>
          </div>
          <span class="px-2.5 py-1 text-[11px] font-semibold bg-emerald-50 text-emerald-800 rounded-full border border-emerald-200">
            خانواده: {{ sp.family }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-100">
          <div class="p-2 bg-slate-50 rounded-xl">
            <span class="text-slate-400 block text-[10px]">بستر ایده‌آل:</span>
            <span class="font-bold text-slate-800">{{ sp.ideal_mix_label }}</span>
          </div>
          <div class="p-2 bg-slate-50 rounded-xl">
            <span class="text-slate-400 block text-[10px]">فرمول NPK استاندارد:</span>
            <span class="font-bold text-emerald-700">{{ sp.default_npk_ratio }}</span>
          </div>
          <div class="p-2 bg-slate-50 rounded-xl">
            <span class="text-slate-400 block text-[10px]">دوز استاندارد EC:</span>
            <span class="font-bold text-slate-800">{{ sp.standard_dose_ec }} mS/cm</span>
          </div>
          <div class="p-2 bg-slate-50 rounded-xl">
            <span class="text-slate-400 block text-[10px]">سرعت رشد رویشی:</span>
            <span class="font-bold text-slate-800">{{ sp.growth_rate }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Substrates View -->
    <div v-if="activeKbSubTab === 'substrates'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="sub in kbStore.substrateList"
        :key="sub.substrate_id"
        class="bg-white rounded-2xl border border-slate-200 p-5 shadow-card space-y-3"
      >
        <div class="flex items-center justify-between">
          <h4 class="text-sm font-bold text-slate-900">{{ sub.label }}</h4>
          <span class="text-xs text-slate-400 font-mono">{{ sub.substrate_id }}</span>
        </div>

        <div class="grid grid-cols-3 gap-2 text-xs pt-2 border-t border-slate-100">
          <div class="p-2 bg-slate-50 rounded-xl text-center">
            <span class="text-slate-400 block text-[10px]">ضریب دوز کود:</span>
            <span class="font-bold text-emerald-700">{{ sub.dose_multiplier }}x</span>
          </div>
          <div class="p-2 bg-slate-50 rounded-xl text-center">
            <span class="text-slate-400 block text-[10px]">ضریب دور آبیاری:</span>
            <span class="font-bold text-emerald-700">{{ sub.interval_multiplier }}x</span>
          </div>
          <div class="p-2 bg-slate-50 rounded-xl text-center">
            <span class="text-slate-400 block text-[10px]">محدوده هدف pH:</span>
            <span class="font-bold text-slate-800">{{ sub.target_ph_range.join(' - ') }}</span>
          </div>
        </div>

        <div v-if="sub.mandatory_supplements && sub.mandatory_supplements.length > 0" class="pt-2 border-t border-slate-100">
          <span class="text-[11px] font-bold text-slate-700 block mb-1">مکمل‌های الزامی بستر:</span>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="sup in sub.mandatory_supplements"
              :key="sup.id"
              class="px-2 py-0.5 text-[10px] font-medium bg-blue-50 text-blue-800 rounded-md border border-blue-200"
            >
              {{ sup.name }} ({{ sup.dose }})
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Traits View -->
    <div v-if="activeKbSubTab === 'traits'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="tr in kbStore.traitList"
        :key="tr.trait_id"
        class="bg-white rounded-2xl border border-slate-200 p-5 shadow-card space-y-3"
      >
        <div class="flex items-center justify-between">
          <h4 class="text-sm font-bold text-slate-900">✨ {{ tr.label }}</h4>
          <span class="text-xs text-slate-400 font-mono">{{ tr.trait_id }}</span>
        </div>

        <div class="text-xs space-y-2 pt-2 border-t border-slate-100">
          <div v-if="tr.override_npk_ratio" class="p-2 bg-emerald-50 rounded-xl flex items-center justify-between">
            <span class="text-emerald-800 font-semibold">فرمول کودی جایگزین:</span>
            <span class="font-bold text-emerald-900">{{ tr.override_npk_ratio }}</span>
          </div>

          <div v-if="tr.banned_fertilizers && tr.banned_fertilizers.length > 0" class="p-2 bg-rose-50 rounded-xl flex items-center justify-between text-rose-800">
            <span class="font-semibold">کودهای ممنوعه:</span>
            <span class="font-bold">{{ tr.banned_fertilizers.join('، ') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Phases View -->
    <div v-if="activeKbSubTab === 'phases'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="ph in kbStore.phaseList"
        :key="ph.phase_id"
        class="bg-white rounded-2xl border border-slate-200 p-5 shadow-card space-y-3"
      >
        <div class="flex items-center justify-between">
          <h4 class="text-sm font-bold text-slate-900">🌱 {{ ph.label }}</h4>
          <span class="text-xs text-slate-400 font-mono">{{ ph.phase_id }}</span>
        </div>

        <div class="text-xs space-y-2 pt-2 border-t border-slate-100">
          <div v-if="ph.override_npk_ratio" class="p-2 bg-emerald-50 rounded-xl flex items-center justify-between">
            <span class="text-emerald-800 font-semibold">فرمول کودی فاز:</span>
            <span class="font-bold text-emerald-900">{{ ph.override_npk_ratio }}</span>
          </div>

          <div v-if="ph.suppress_high_nitrogen" class="p-2 bg-amber-50 rounded-xl flex items-center justify-between text-amber-800">
            <span class="font-semibold">محدودیت نیتروژن:</span>
            <span class="font-bold">توقف مصرف کودهای ازت بالا</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
