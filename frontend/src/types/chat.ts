export type RiskLevel = 'OPTIMAL' | 'SUB_OPTIMAL' | 'CRITICAL_BLOCKER';
export type FeasibilityStatus = 'FEASIBLE' | 'UNREALISTIC';

export interface ScheduleWeek {
  week_num: number;
  action: string;
  dose_factor?: string;
  supplements: string[];
}

export interface CalculatedSchedule {
  applied_ratio: string;
  banned_elements: string[];
  weeks: ScheduleWeek[];
}

export interface ChatRequest {
  user_id: string;
  message: string;
  session_id?: string;
  plant_id?: string;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  plant_id?: string | null;
  risk_level?: RiskLevel | null;
  feasibility_status?: FeasibilityStatus | null;
  calculated_schedule?: CalculatedSchedule | null;
  missing_slots: string[];
  extracted_entities?: Record<string, any> | null;
}

export interface UIMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: Date;
  plant_id?: string | null;
  risk_level?: RiskLevel | null;
  feasibility_status?: FeasibilityStatus | null;
  calculated_schedule?: CalculatedSchedule | null;
  missing_slots?: string[];
  extracted_entities?: Record<string, any> | null;
}
