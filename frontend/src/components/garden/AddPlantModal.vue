<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { X, Sprout, Plus, Loader2, AlertCircle } from 'lucide-vue-next';
import { usePlantStore } from '../../stores/usePlantStore';
import { useKbStore } from '../../stores/useKbStore';

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'created'): void;
}>();

const plantStore = usePlantStore();
const kbStore = useKbStore();

const isSubmitting = ref(false);
const errorMessage = ref<string | null>(null);

const form = reactive({
  nickname: '',
  species_id: '',
  substrate_type: '',
  pot_type_and_size: '',
  light_condition: '',
  ambient_humidity: 60,
  traits: [] as string[],
  current_phase: 'active_vegetative',
  health_status: 'HEALTHY',
});

onMounted(async () => {
  if (!kbStore.isLoaded) {
    await kbStore.fetchAllKb();
  }
  if (kbStore.speciesList.length > 0 && !form.species_id) {
    form.species_id = kbStore.speciesList[0].species_id;
  }
  if (kbStore.substrateList.length > 0 && !form.substrate_type) {
    form.substrate_type = kbStore.substrateList[0].substrate_id;
  }
  if (kbStore.phaseList.length > 0 && !form.current_phase) {
    form.current_phase = kbStore.phaseList[0].phase_id;
  }
});

function toggleTrait(traitId: string) {
  const index = form.traits.indexOf(traitId);
  if (index > -1) {
    form.traits.splice(index, 1);
  } else {
    form.traits.push(traitId);
  }
}

async function handleSubmit() {
  if (!form.nickname.trim()) {
    errorMessage.value = 'لطفاً نام مستعار گیاه را وارد نمایید.';
    return;
  }
  if (!form.species_id) {
    errorMessage.value = 'لطفاً گونه گیاه را انتخاب کنید.';
    return;
  }
  if (!form.substrate_type) {
    errorMessage.value = 'لطفاً نوع بستر کشت را مشخص نمایید.';
    return;
  }

  errorMessage.value = null;
  isSubmitting.value = true;

  try {
    await plantStore.addPlant({
      nickname: form.nickname.trim(),
      species_id: form.species_id,
      substrate_type: form.substrate_type,
      pot_type_and_size: form.pot_type_and_size || undefined,
      light_condition: form.light_condition || undefined,
      ambient_humidity: Number(form.ambient_humidity) || undefined,
      traits: form.traits,
      current_phase: form.current_phase,
      health_status: form.health_status,
    });
    emit('created');
    emit('close');
  } catch (err: any) {
    errorMessage.value = err.message || 'خطا در ثبت گیاه جدید';
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl max-w-xl w-full p-6 shadow-2xl border border-slate-100 animate-slide-up relative">
      <!-- Modal Header -->
      <div class="flex items-center justify-between pb-4 border-b border-slate-100">
        <div class="flex items-center space-x-2.5 space-x-reverse">
          <div class="w-10 h-10 rounded-2xl bg-emerald-100 text-emerald-800 flex items-center justify-center">
            <Sprout class="w-6 h-6" />
          </div>
          <div>
            <h3 class="text-base font-bold text-slate-900">افزودن گیاه جدید به باغچه</h3>
            <p class="text-xs text-slate-500">مشخصات پرونده زیستی و بستر رشد را وارد کنید</p>
          </div>
        </div>

        <button
          @click="emit('close')"
          class="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Error Alert -->
      <div
        v-if="errorMessage"
        class="mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2"
      >
        <AlertCircle class="w-4 h-4 text-rose-600 shrink-0" />
        <span>{{ errorMessage }}</span>
      </div>

      <!-- Form Body -->
      <form @submit.prevent="handleSubmit" class="mt-4 space-y-4 text-xs">
        <!-- Nickname -->
        <div>
          <label class="block font-bold text-slate-700 mb-1">
            نام مستعار گیاه <span class="text-rose-500">*</span>
          </label>
          <input
            v-model="form.nickname"
            type="text"
            placeholder="مثلاً: مونسترای سالن پذیرایی"
            class="w-full rounded-xl border-slate-300 p-2.5 text-xs text-slate-800 focus:border-emerald-500 focus:ring-emerald-500"
            required
          />
        </div>

        <!-- Species & Substrate Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Species -->
          <div>
            <label class="block font-bold text-slate-700 mb-1">
              گونه گیاهی <span class="text-rose-500">*</span>
            </label>
            <select
              v-model="form.species_id"
              class="w-full rounded-xl border-slate-300 p-2.5 text-xs text-slate-800 focus:border-emerald-500 focus:ring-emerald-500"
              required
            >
              <option
                v-for="sp in kbStore.speciesList"
                :key="sp.species_id"
                :value="sp.species_id"
              >
                {{ sp.persian_name }} ({{ sp.scientific_name }})
              </option>
            </select>
          </div>

          <!-- Substrate -->
          <div>
            <label class="block font-bold text-slate-700 mb-1">
              نوع بستر کشت <span class="text-rose-500">*</span>
            </label>
            <select
              v-model="form.substrate_type"
              class="w-full rounded-xl border-slate-300 p-2.5 text-xs text-slate-800 focus:border-emerald-500 focus:ring-emerald-500"
              required
            >
              <option
                v-for="sub in kbStore.substrateList"
                :key="sub.substrate_id"
                :value="sub.substrate_id"
              >
                {{ sub.label }}
              </option>
            </select>
          </div>
        </div>

        <!-- Growth Phase & Health Status -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Growth Phase -->
          <div>
            <label class="block font-bold text-slate-700 mb-1">فاز فنولوژیکی رشد</label>
            <select
              v-model="form.current_phase"
              class="w-full rounded-xl border-slate-300 p-2.5 text-xs text-slate-800 focus:border-emerald-500 focus:ring-emerald-500"
            >
              <option
                v-for="ph in kbStore.phaseList"
                :key="ph.phase_id"
                :value="ph.phase_id"
              >
                {{ ph.label }}
              </option>
            </select>
          </div>

          <!-- Health Status -->
          <div>
            <label class="block font-bold text-slate-700 mb-1">وضعیت فعلی سلامت</label>
            <select
              v-model="form.health_status"
              class="w-full rounded-xl border-slate-300 p-2.5 text-xs text-slate-800 focus:border-emerald-500 focus:ring-emerald-500"
            >
              <option value="HEALTHY">سالم و شاداب (HEALTHY)</option>
              <option value="ROOT_ROT_RISK">⚠️ در معرض پوسیدگی ریشه (ROOT_ROT_RISK)</option>
              <option value="SUB_OPTIMAL">نیازمند تنظیم تغذیه (SUB_OPTIMAL)</option>
            </select>
          </div>
        </div>

        <!-- Morphological Traits Checkboxes -->
        <div>
          <label class="block font-bold text-slate-700 mb-1.5">صفات مورفولوژیکی ویژه</label>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              v-for="t in kbStore.traitList"
              :key="t.trait_id"
              @click="toggleTrait(t.trait_id)"
              class="px-3 py-1.5 rounded-xl border text-xs font-medium transition-all"
              :class="
                form.traits.includes(t.trait_id)
                  ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-emerald-50'
              "
            >
              <span>{{ t.label }}</span>
            </button>
          </div>
        </div>

        <!-- Environment Details -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div>
            <label class="block font-medium text-slate-600 mb-1">نوع و سایز گلدان</label>
            <input
              v-model="form.pot_type_and_size"
              type="text"
              placeholder="مثلاً سفالی ۲۵ سانت"
              class="w-full rounded-xl border-slate-300 p-2 text-xs"
            />
          </div>
          <div>
            <label class="block font-medium text-slate-600 mb-1">شرایط نور</label>
            <input
              v-model="form.light_condition"
              type="text"
              placeholder="مثلاً فیلترشده ۴۰۰۰ لوکس"
              class="w-full rounded-xl border-slate-300 p-2 text-xs"
            />
          </div>
          <div>
            <label class="block font-medium text-slate-600 mb-1">رطوبت محیط (%)</label>
            <input
              v-model="form.ambient_humidity"
              type="number"
              min="0"
              max="100"
              class="w-full rounded-xl border-slate-300 p-2 text-xs"
            />
          </div>
        </div>

        <!-- Modal Actions -->
        <div class="mt-6 pt-4 border-t border-slate-100 flex items-center justify-end space-x-3 space-x-reverse">
          <button
            type="button"
            @click="emit('close')"
            class="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-medium text-xs transition-colors"
          >
            انصراف
          </button>
          <button
            type="submit"
            :disabled="isSubmitting"
            class="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-md shadow-emerald-600/20 disabled:opacity-50 transition-all"
          >
            <Loader2 v-if="isSubmitting" class="w-4 h-4 animate-spin" />
            <Plus v-else class="w-4 h-4" />
            <span>{{ isSubmitting ? 'در حال ثبت...' : 'ثبت گیاه در باغچه' }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
