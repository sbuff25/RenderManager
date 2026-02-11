/**
 * Wain API response types — matches the REST API from server.py
 */

export interface ServerStatus {
  app: string;
  version: string;
  mode: string;
  uptime_seconds: number;
  total_jobs: number;
  queued_jobs: number;
  rendering_jobs: number;
  active_workers: number;
  auth_required: boolean;
}

export interface RenderJob {
  id: string;
  name: string;
  engine_type: string;
  file_path: string;
  output_folder: string;
  output_name: string;
  output_format: string;
  status: string;
  progress: number;
  is_animation: boolean;
  frame_start: number;
  frame_end: number;
  current_frame: number;
  rendering_frame: number;
  original_start: number;
  res_width: number;
  res_height: number;
  camera: string;
  overwrite_existing: boolean;
  engine_settings: Record<string, any>;
  start_time: string | null;
  end_time: string | null;
  elapsed_time: string;
  accumulated_seconds: number;
  error_message: string;
  status_message: string;
  current_sample: number;
  total_samples: number;
  current_tile: number;
  total_tiles: number;
  current_pass: string;
  current_pass_num: number;
  total_passes: number;
  pass_frame: number;
  pass_total_frames: number;
  assigned_to: string | null;
  claimed_at: string | null;
  target_worker: string;
  priority: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface Worker {
  worker_id: string;
  hostname: string;
  ip_address: string;
  status: string;
  current_job_id: string | null;
  last_heartbeat: string;
  capabilities: Record<string, any>;
  registered_at: string;
  is_stale: boolean;
}

export interface JobsResponse {
  jobs: RenderJob[];
  total: number;
}

export interface WorkersResponse {
  workers: Worker[];
}
