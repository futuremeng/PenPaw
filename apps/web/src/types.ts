/** 前后端共享的数据类型（对齐 apps/server/app/schemas.py）。 */

export interface AssetInfo {
  asset_id: string;
  width: number;
  height: number;
  downsampled: boolean;
  expires_at: string;
}

export interface RoiBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label?: string;
}

export interface PreviewResult {
  svg: string;
  control_points: number;
  confidence: number;
  version: number;
}

export type TaskStatus = "queued" | "running" | "succeeded" | "degraded" | "failed";

export interface TaskInfo {
  task_id: string;
  asset_id: string;
  status: TaskStatus;
  progress: number;
  error: string | null;
  control_points: number | null;
}
