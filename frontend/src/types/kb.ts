export interface MandatorySupplement {
  id: string;
  name: string;
  dose?: string;
  reason?: string;
  [key: string]: any;
}

export interface SpeciesSummaryResponse {
  species_id: string;
  scientific_name: string;
  persian_name: string;
  family: string;
  growth_rate: string;
  ideal_mix_label: string;
  default_npk_ratio: string;
  standard_dose_ec: number;
}

export interface SubstrateSummaryResponse {
  substrate_id: string;
  label: string;
  dose_multiplier: number;
  interval_multiplier: number;
  target_ph_range: number[];
  mandatory_supplements: MandatorySupplement[];
}

export interface TraitSummaryResponse {
  trait_id: string;
  label: string;
  override_npk_ratio?: string | null;
  banned_fertilizers: string[];
  mandatory_supplements: MandatorySupplement[];
}

export interface PhaseSummaryResponse {
  phase_id: string;
  label: string;
  suppress_high_nitrogen: boolean;
  override_npk_ratio?: string | null;
  mandatory_supplements: MandatorySupplement[];
}
