import { apiClient } from './client';
import type {
  PlantResponse,
  PlantCreateRequest,
  PlantUpdateRequest,
  EventLogResponse,
  EventLogCreateRequest,
} from '../types/plant';

export const plantApi = {
  /**
   * Fetch all plants belonging to a user
   */
  async getUserPlants(userId: string): Promise<PlantResponse[]> {
    const res = await apiClient.get<PlantResponse[]>('/plants', {
      params: { user_id: userId },
    });
    return res.data;
  },

  /**
   * Create a new plant digital twin
   */
  async createPlant(req: PlantCreateRequest): Promise<PlantResponse> {
    const res = await apiClient.post<PlantResponse>('/plants', req);
    return res.data;
  },

  /**
   * Get single plant details
   */
  async getPlant(plantId: string): Promise<PlantResponse> {
    const res = await apiClient.get<PlantResponse>(`/plants/${plantId}`);
    return res.data;
  },

  /**
   * Incrementally update plant parameters
   */
  async updatePlant(plantId: string, req: PlantUpdateRequest): Promise<PlantResponse> {
    const res = await apiClient.patch<PlantResponse>(`/plants/${plantId}`, req);
    return res.data;
  },

  /**
   * Delete a plant and all its logs
   */
  async deletePlant(plantId: string): Promise<void> {
    await apiClient.delete(`/plants/${plantId}`);
  },

  /**
   * Log a care/fertilizing/watering/warning event for a plant
   */
  async addPlantEvent(plantId: string, req: EventLogCreateRequest): Promise<EventLogResponse> {
    const res = await apiClient.post<EventLogResponse>(`/plants/${plantId}/events`, req);
    return res.data;
  },

  /**
   * Get event history logs for a plant
   */
  async getPlantEvents(plantId: string, limit = 20): Promise<EventLogResponse[]> {
    const res = await apiClient.get<EventLogResponse[]>(`/plants/${plantId}/events`, {
      params: { limit },
    });
    return res.data;
  },
};
