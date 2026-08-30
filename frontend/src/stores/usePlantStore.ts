import { defineStore } from 'pinia';
import { ref } from 'vue';
import { plantApi } from '../api/plantApi';
import type {
  PlantResponse,
  PlantCreateRequest,
  PlantUpdateRequest,
  EventLogResponse,
} from '../types/plant';

export const usePlantStore = defineStore('plants', () => {
  const plants = ref<PlantResponse[]>([]);
  const activeUserId = ref<string>('user_123');
  const selectedPlant = ref<PlantResponse | null>(null);
  const eventsMap = ref<Record<string, EventLogResponse[]>>({});

  const isLoading = ref<boolean>(false);
  const isHistoryLoading = ref<boolean>(false);
  const error = ref<string | null>(null);

  async function fetchPlants() {
    isLoading.value = true;
    error.value = null;
    try {
      const data = await plantApi.getUserPlants(activeUserId.value);
      plants.value = data;
    } catch (err: any) {
      error.value = err.message || 'خطا در دریافت لیست گیاهان';
      console.error('Plant fetch error:', err);
    } finally {
      isLoading.value = false;
    }
  }

  async function addPlant(req: Omit<PlantCreateRequest, 'user_id'>) {
    isLoading.value = true;
    error.value = null;
    try {
      const newPlant = await plantApi.createPlant({
        ...req,
        user_id: activeUserId.value,
      });
      plants.value.unshift(newPlant);
      return newPlant;
    } catch (err: any) {
      error.value = err.message || 'خطا در ثبت گیاه جدید';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function updatePlant(plantId: string, req: PlantUpdateRequest) {
    try {
      const updated = await plantApi.updatePlant(plantId, req);
      const index = plants.value.findIndex((p) => p.id === plantId);
      if (index !== -1) {
        plants.value[index] = updated;
      }
      if (selectedPlant.value?.id === plantId) {
        selectedPlant.value = updated;
      }
      return updated;
    } catch (err: any) {
      console.error('Update plant error:', err);
      throw err;
    }
  }

  async function removePlant(plantId: string) {
    try {
      await plantApi.deletePlant(plantId);
      plants.value = plants.value.filter((p) => p.id !== plantId);
      if (selectedPlant.value?.id === plantId) {
        selectedPlant.value = null;
      }
      delete eventsMap.value[plantId];
    } catch (err: any) {
      console.error('Delete plant error:', err);
      throw err;
    }
  }

  async function logCareEvent(plantId: string, eventType: string, details: Record<string, any> = {}) {
    try {
      const newEvent = await plantApi.addPlantEvent(plantId, {
        event_type: eventType,
        details,
      });

      if (!eventsMap.value[plantId]) {
        eventsMap.value[plantId] = [];
      }
      eventsMap.value[plantId].unshift(newEvent);

      // Optimistic update of plant status if relevant
      if (eventType === 'WATERING') {
        const plant = plants.value.find((p) => p.id === plantId);
        if (plant && plant.health_status === 'CRITICAL') {
          // Keep status or refresh
        }
      }

      return newEvent;
    } catch (err: any) {
      console.error('Log care event error:', err);
      throw err;
    }
  }

  async function fetchHistory(plantId: string, limit = 20) {
    isHistoryLoading.value = true;
    try {
      const events = await plantApi.getPlantEvents(plantId, limit);
      eventsMap.value[plantId] = events;
      return events;
    } catch (err: any) {
      console.error('Fetch plant history error:', err);
      return [];
    } finally {
      isHistoryLoading.value = false;
    }
  }

  function getPlantById(plantId: string): PlantResponse | undefined {
    return plants.value.find((p) => p.id === plantId);
  }

  return {
    plants,
    activeUserId,
    selectedPlant,
    eventsMap,
    isLoading,
    isHistoryLoading,
    error,
    fetchPlants,
    addPlant,
    updatePlant,
    removePlant,
    logCareEvent,
    fetchHistory,
    getPlantById,
  };
});
