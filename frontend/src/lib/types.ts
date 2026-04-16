/** TypeScript interfaces matching the FastAPI Pydantic schemas. */

export interface Project {
  id: string;
  name: string;
  topic: string;
  language: string;
  global_text_length: string;
  prompt_override?: string | null;
  llm_config?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  topic?: string;
  language?: string;
  global_text_length?: string;
}

export interface Source {
  id: string;
  project_id: string;
  source_type: string;
  filename: string;
  chunk_count: number;
  processing_status: string;
  error_message?: string | null;
  created_at: string;
}

export interface Chapter {
  id: string;
  project_id: string;
  chapter_index: number;
  title: string;
  summary: string;
  estimated_slide_count: number;
  status: string;
  source_ids?: string[];
}

export interface SectionPlan {
  chapter_index: number;
  slides: SlidePlan[];
}

export interface SlidePlanChunk {
  text: string;
  distance: number | null;
  selected: boolean;
  metadata: {
    source_id?: string;
    source_type?: string;
    filename?: string;
    chunk_index?: number;
    [key: string]: unknown;
  };
}

export interface SlidePlan {
  template_type: string;
  brief: string;
  prompt?: string | null;
  reused_slide_id?: string | null;
  chunks?: SlidePlanChunk[];
}

export interface Slide {
  id: string;
  chapter_id: string;
  project_id: string;
  slide_index: number;
  slide_index_in_chapter: number;
  template_type: string;
  title: string;
  subtitle?: string;
  content_json?: string;
  speaker_notes?: string;
  chain_of_thought?: string;
  is_reused: boolean;
}

export interface SourceGap {
  id: string;
  project_id: string;
  chapter_id: string | null;
  description: string;
  severity: "low" | "medium" | "high";
}

export interface Progress {
  current_step: string;
  step_index: number;
  total_steps: number;
}

export interface Settings {
  preferences: Record<string, unknown>;
  api_keys_configured: Record<string, boolean>;
}

// WebSocket message types
export type WsMessage =
  | { type: "progress"; done: number; total: number }
  | { type: "batch_done"; batch_start: number; slides: Slide[] }
  | { type: "complete"; total_slides: number }
  | { type: "error"; message: string };
