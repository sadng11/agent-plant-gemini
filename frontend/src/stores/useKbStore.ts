import { defineStore } from 'pinia';
import { ref } from 'vue';
import { kbApi } from '../api/kbApi';
import type {
  SpeciesSummaryResponse,
  SubstrateSummaryResponse,
  TraitSummaryResponse,
  PhaseSummaryResponse,
} from '../types/kb';

export const useKbStore = defineStore('kb', () => {
  const speciesList = ref<SpeciesSummaryResponse[]>([]);
  const substrateList = ref<SubstrateSummaryResponse[]>([]);
  const traitList = ref<TraitSummaryResponse[]>([]);
  const phaseList = ref<PhaseSummaryResponse[]>([]);

  const isLoading = ref(false);
  const isLoaded = ref(false);
  const error = ref<string | null>(null);

  async function fetchAllKb(force = false) {
    if (isLoaded.value && !force) return;

    isLoading.value = true;
    error.value = null;
    try {
      const [species, substrates, traits, phases] = await Promise.all([
        kbApi.getSpecies(),
        kbApi.getSubstrates(),
        kbApi.getTraits(),
        kbApi.getPhases(),
      ]);

      speciesList.value = species;
      substrateList.value = substrates;
      traitList.value = traits;
      phaseList.value = phases;
      isLoaded.value = true;
    } catch (err: any) {
      error.value = err.message || 'خطا در بارگذاری اطلاعات پایگاه دانش';
      console.error('KB Fetch error:', err);
    } finally {
      isLoading.value = false;
    }
  }

  function getSpeciesName(speciesId: string): string {
    const sp = speciesList.value.find((s) => s.species_id === speciesId);
    return sp ? `${sp.persian_name} (${sp.scientific_name})` : speciesId;
  }

  function getSpeciesPersianName(speciesId: string): string {
    const sp = speciesList.value.find((s) => s.species_id === speciesId);
    return sp ? sp.persian_name : speciesId;
  }

  function getSubstrateLabel(substrateId: string): string {
    const sub = substrateList.value.find((s) => s.substrate_id === substrateId);
    return sub ? sub.label : substrateId;
  }

  function getTraitLabel(traitId: string): string {
    const t = traitList.value.find((item) => item.trait_id === traitId);
    return t ? t.label : traitId;
  }

  function getPhaseLabel(phaseId: string): string {
    const p = phaseList.value.find((ph) => ph.phase_id === phaseId);
    return p ? p.label : phaseId;
  }

  return {
    speciesList,
    substrateList,
    traitList,
    phaseList,
    isLoading,
    isLoaded,
    error,
    fetchAllKb,
    getSpeciesName,
    getSpeciesPersianName,
    getSubstrateLabel,
    getTraitLabel,
    getPhaseLabel,
  };
});
