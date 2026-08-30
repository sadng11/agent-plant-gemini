<script setup lang="ts">
import { ref, onMounted } from 'vue';
import {
  X,
  Clock,
  Droplets,
  FlaskConical,
  RefreshCw,
  AlertTriangle,
  FileText,
  Plus,
  Loader2,
  Calendar,
} from 'lucide-vue-next';
import type { PlantResponse, EventLogResponse } from '../../types/plant';
import { usePlantStore } from '../../stores/usePlantStore';
import { useKbStore } from '../../stores/useKbStore';

const props = defineProps<{
  plant: PlantResponse;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const plantStore = usePlantStore();
const kbStore = useKbStore();

const events = ref<EventLogResponse[]>([]);
const isLoggingEvent = ref(false);
const selectedEventType = ref<'WATERING' | 'FERTILIZING' | 'REPOTTING'>('WATERING');
const eventNote = ref('');

onMounted(async () => {
  events.value = await plantStore.fetchHistory(props.plant.id);
});

async function handleAddEvent() {
  if (!selectedEventType.value) return;
  isLoggingEvent.value = true;
  try {
    const newEv = await plantStore.logCareEvent(props.plant.id, selectedEventType.value, {
      note: eventNote.value || 'ثبت دستی از پرونده سلامت',
      date: new Date().toISOString(),
    });
    events.value.unshift(newEv);
    eventNote.value = '';
  } catch (err) {
    alert('خطا در ثبت رویداد جدید');
  } finally {
    isLoggingEvent.value = false;
  }
}

function formatPersianDate(dateStr?: string | null): string {
  if (!dateStr) return 'نامشخص';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('fa-IR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

function getEventStyle(eventType: string) {
  switch (eventType) {
    case 'WATERING':
      return {
        label: 'آبیاری',
        icon: Droplets,
        color: 'text-blue-600 bg-blue-100 border-blue-200',
      };
    case 'FERTILIZING':
      return {
        label: 'کوددهی و تغذیه',
        icon: FlaskConical,
        color: 'text-emerald-600 bg-emerald-100 border-emerald-200',
      };
    case 'REPOTTING':
      return {
        label: 'تعویض گلدان و خاک',
        icon: RefreshCw,
        color: 'text-purple-600 bg-purple-100 border-purple-200',
      };
    case 'DIAGNOSTIC_WARNING':
      return {
        label: 'هشدار تریاژ تشخیصی',
        icon: AlertTriangle,
        color: 'text-rose-600 bg-rose-100 border-rose-200',
      };
    default:
      return {
        label: eventType,
        icon: FileText,
        color: 'text-slate-600 bg-slate-100 border-slate-200',
      };
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-100 animate-slide-up relative flex flex-col max-h-[85vh]">
      <!-- Header -->
      <div class="flex items-center justify-between pb-4 border-b border-slate-100 shrink-0">
        <div class="flex items-center space-x-3 space-x-reverse">
          <div class="w-10 h-10 rounded-2xl bg-emerald-100 text-emerald-800 flex items-center justify-center">
            <Calendar class="w-5 h-5" />
          </div>
          <div>
            <h3 class="text-base font-bold text-slate-900">
              پرونده و تاریخچه مراقبت: {{ plant.nickname }}
            </h3>
            <p class="text-xs text-slate-500">
              {{ kbStore.getSpeciesName(plant.species_id) }} | بستر: {{ kbStore.getSubstrateLabel(plant.substrate_type) }}
            </p>
          </div>
        </div>

        <button
          @click="emit('close')"
          class="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Quick Add Event Form -->
      <div class="my-4 p-4 rounded-2xl bg-slate-50 border border-slate-200 shrink-0">
        <h4 class="text-xs font-bold text-slate-800 mb-2">ثبت سریع اقدام مراقبتی جدید</h4>
        <div class="flex flex-wrap items-center gap-2">
          <select
            v-model="selectedEventType"
            class="rounded-xl border-slate-300 bg-white p-2 text-xs text-slate-800 focus:border-emerald-500"
          >
            <option value="WATERING">💧 آبیاری</option>
            <option value="FERTILIZING">💊 کوددهی</option>
            <option value="REPOTTING">🪴 تعویض بستر/گلدان</option>
          </select>

          <input
            v-model="eventNote"
            type="text"
            placeholder="یادداشت اختیاری (مثلاً دوز کودی یا حجم آب)..."
            class="flex-1 min-w-[180px] rounded-xl border-slate-300 bg-white p-2 text-xs text-slate-800 focus:border-emerald-500"
          />

          <button
            @click="handleAddEvent"
            :disabled="isLoggingEvent"
            class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm flex items-center gap-1 shrink-0"
          >
            <Loader2 v-if="isLoggingEvent" class="w-3.5 h-3.5 animate-spin" />
            <Plus v-else class="w-3.5 h-3.5" />
            <span>ثبت اقدام</span>
          </button>
        </div>
      </div>

      <!-- Events Timeline Body -->
      <div class="flex-1 overflow-y-auto space-y-3 pr-1 pl-2">
        <div v-if="plantStore.isHistoryLoading" class="text-center py-8 text-slate-400 text-xs flex flex-col items-center gap-2">
          <Loader2 class="w-6 h-6 animate-spin text-emerald-600" />
          <span>در حال بارگذاری سوابق پرونده...</span>
        </div>

        <div v-else-if="events.length === 0" class="text-center py-8 text-slate-400 text-xs">
          هنوز هیچ رویدادی برای این گیاه ثبت نشده است. می‌توانید با استفاده از فرم بالا یا کلیک روی دکمه‌های تقویم تشخیصی، اولین رویداد را ثبت کنید.
        </div>

        <div
          v-for="ev in events"
          :key="ev.id"
          class="p-3.5 rounded-2xl bg-white border border-slate-200/90 shadow-sm flex items-start space-x-3 space-x-reverse"
        >
          <!-- Icon Badge -->
          <div
            class="p-2 rounded-xl border shrink-0"
            :class="getEventStyle(ev.event_type).color"
          >
            <component :is="getEventStyle(ev.event_type).icon" class="w-4 h-4" />
          </div>

          <!-- Content -->
          <div class="flex-1">
            <div class="flex items-center justify-between gap-2">
              <h5 class="text-xs font-bold text-slate-900">
                {{ getEventStyle(ev.event_type).label }}
              </h5>
              <span class="text-[11px] text-slate-400 flex items-center gap-1">
                <Clock class="w-3 h-3" />
                <span>{{ formatPersianDate(ev.created_at) }}</span>
              </span>
            </div>

            <!-- Details representation -->
            <div v-if="ev.details && Object.keys(ev.details).length > 0" class="mt-1.5 text-xs text-slate-600">
              <div v-if="ev.details.action" class="font-medium text-emerald-800">
                {{ ev.details.action }}
              </div>
              <div v-if="ev.details.note" class="text-slate-500 mt-0.5">
                {{ ev.details.note }}
              </div>
              <div v-if="ev.details.supplements && ev.details.supplements.length > 0" class="mt-1 flex flex-wrap gap-1">
                <span
                  v-for="s in ev.details.supplements"
                  :key="s"
                  class="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700"
                >
                  {{ s }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="mt-4 pt-3 border-t border-slate-100 flex justify-end shrink-0">
        <button
          @click="emit('close')"
          class="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs"
        >
          بستن پرونده
        </button>
      </div>
    </div>
  </div>
</template>
