export interface PlantResponse {
  id: string;
  user_id: string;
  nickname: string;
  species_id: string;
  substrate_type: string;
  pot_type_and_size?: string | null;
  light_condition?: string | null;
  ambient_humidity?: number | null;
  traits: string[];
  current_phase: string;
  health_status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PlantCreateRequest {
  user_id: string;
  nickname: string;
  species_id: string;
  substrate_type: string;
  pot_type_and_size?: string | null;
  light_condition?: string | null;
  ambient_humidity?: number | null;
  traits?: string[];
  current_phase?: string;
  health_status?: string;
}

export interface PlantUpdateRequest {
  nickname?: string;
  species_id?: string;
  substrate_type?: string;
  pot_type_and_size?: string | null;
  light_condition?: string | null;
  ambient_humidity?: number | null;
  traits?: string[];
  current_phase?: string;
  health_status?: string;
}

export interface EventLogResponse {
  id: string;
  plant_id: string;
  event_type: string;
  details: Record<string, any>;
  created_at?: string | null;
}

export interface EventLogCreateRequest {
  event_type: string;
  details?: Record<string, any>;
}
