/**
 * API 客户端接口（PRD 附录 E.1 约束）。
 *
 * 桌面端（V2 方案 B）复用本前端时，注入 LocalClient（Tauri Command 实现），
 * Web 端使用 HttpClient。组件层只依赖 PreviewClient 接口。
 */
import type { AssetInfo, PreviewResult, RoiBox, TaskInfo } from "../types";

export interface PreviewClient {
  upload(file: File): Promise<AssetInfo>;
  preview(
    assetId: string,
    req: { regions: RoiBox[]; smoothness: number; detail: number; version: number }
  ): Promise<PreviewResult>;
  optimize(assetId: string): Promise<{ task_id: string }>;
  taskState(taskId: string): Promise<TaskInfo>;
  /** SSE 进度流地址（EventSource） */
  taskEventsUrl(taskId: string): string;
  /** 导出下载地址（optimized=false 快速导出 / true 精细优化导出） */
  exportUrl(assetId: string, optimized: boolean): string;
}

const BASE = "/api/v1";

export class HttpClient implements PreviewClient {
  async upload(file: File): Promise<AssetInfo> {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${BASE}/uploads`, { method: "POST", body: form });
    if (!resp.ok) throw new Error(await this._error(resp));
    return resp.json();
  }

  async preview(
    assetId: string,
    req: { regions: RoiBox[]; smoothness: number; detail: number; version: number }
  ): Promise<PreviewResult> {
    const resp = await fetch(`${BASE}/assets/${assetId}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!resp.ok) throw new Error(await this._error(resp));
    return resp.json();
  }

  async optimize(assetId: string): Promise<{ task_id: string }> {
    const resp = await fetch(`${BASE}/assets/${assetId}/optimize`, { method: "POST" });
    if (!resp.ok) throw new Error(await this._error(resp));
    const task: TaskInfo = await resp.json();
    return { task_id: task.task_id };
  }

  async taskState(taskId: string): Promise<TaskInfo> {
    const resp = await fetch(`${BASE}/tasks/${taskId}`);
    if (!resp.ok) throw new Error(await this._error(resp));
    return resp.json();
  }

  taskEventsUrl(taskId: string): string {
    return `${BASE}/tasks/${taskId}/events`;
  }

  exportUrl(assetId: string, optimized: boolean): string {
    const q = optimized ? "?optimized=true" : "";
    return `${BASE}/assets/${assetId}/export${q}`;
  }

  private async _error(resp: Response): Promise<string> {
    try {
      const body = await resp.json();
      return body.detail ?? resp.statusText;
    } catch {
      return resp.statusText;
    }
  }
}

export const client: PreviewClient = new HttpClient();
