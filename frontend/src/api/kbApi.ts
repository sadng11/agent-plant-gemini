import { apiClient } from './client';
import type {
  SpeciesSummaryResponse,
  SubstrateSummaryResponse,
  TraitSummaryResponse,
  PhaseSummaryResponse,
} from '../types/kb';

export const kbApi = {
  /**
   * List all botanical species summaries
   */
  async getSpecies(): Promise<SpeciesSummaryResponse[]> {
    const res = await apiClient.get<SpeciesSummaryResponse[]>('/kb/species');
    return res.data;
  },

  /**
   * Get full botanical profile for a species
   */
  async getSpeciesById(speciesId: string): Promise<any> {
    const res = await apiClient.get(`/kb/species/${speciesId}`);
    return res.data;
  },

  /**
   * List all substrate types
   */
  async getSubstrates(): Promise<SubstrateSummaryResponse[]> {
    const res = await apiClient.get<SubstrateSummaryResponse[]>('/kb/substrates');
    return res.data;
  },

  /**
   * List all plant traits
   */
  async getTraits(): Promise<TraitSummaryResponse[]> {
    const res = await apiClient.get<TraitSummaryResponse[]>('/kb/traits');
    return res.data;
  },

  /**
   * List all phenological growth phases
   */
  async getPhases(): Promise<PhaseSummaryResponse[]> {
    const res = await apiClient.get<PhaseSummaryResponse[]>('/kb/phases');
    return res.data;
  },
};
