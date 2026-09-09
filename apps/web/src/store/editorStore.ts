/** 编辑器全局状态（Zustand）。 */
import { create } from "zustand";
import { client } from "../api/client";
import type { AssetInfo, PreviewResult, RoiBox, TaskInfo } from "../types";

interface EditorState {
  asset: AssetInfo | null;
  imageUrl: string | null;
  regions: RoiBox[];
  smoothness: number;
  detail: number;
  preview: PreviewResult | null;
  previewLoading: boolean;
  task: TaskInfo | null;
  error: string | null;

  upload: (file: File) => Promise<void>;
  setRegions: (regions: RoiBox[]) => void;
  setSmoothness: (v: number) => void;
  setDetail: (v: number) => void;
  runPreview: () => Promise<void>;
  runOptimize: () => Promise<void>;
  clearError: () => void;
}

let previewVersion = 0;

export const useEditorStore = create<EditorState>((set, get) => ({
  asset: null,
  imageUrl: null,
  regions: [],
  smoothness: 50,
  detail: 50,
  preview: null,
  previewLoading: false,
  task: null,
  error: null,

  upload: async (file) => {
    try {
      const asset = await client.upload(file);
      set({
        asset,
        imageUrl: URL.createObjectURL(file),
        regions: [],
        preview: null,
        task: null,
        error: asset.downsampled ? "图像已自动缩放以保证处理速度" : null,
      });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "上传失败" });
    }
  },

  setRegions: (regions) => set({ regions }),
  setSmoothness: (v) => set({ smoothness: v }),
  setDetail: (v) => set({ detail: v }),

  runPreview: async () => {
    const { asset, regions, smoothness, detail } = get();
    if (!asset) return;
    const version = ++previewVersion;
    set({ previewLoading: true });
    try {
      const result = await client.preview(asset.asset_id, {
        regions,
        smoothness,
        detail,
        version,
      });
      // 丢弃过期响应（PRD §4.2 请求节流）
      if (version === previewVersion) {
        set({ preview: result, previewLoading: false });
      }
    } catch (e) {
      if (version === previewVersion) {
        set({ previewLoading: false, error: e instanceof Error ? e.message : "预览失败" });
      }
    }
  },

  runOptimize: async () => {
    const { asset } = get();
    if (!asset) return;
    set({ error: null });
    try {
      const { task_id } = await client.optimize(asset.asset_id);
      const es = new EventSource(client.taskEventsUrl(task_id));
      es.onmessage = (ev) => {
        const task: TaskInfo = JSON.parse(ev.data);
        set({ task });
        if (task.status === "succeeded" || task.status === "degraded" || task.status === "failed") {
          es.close();
          if (task.status === "degraded") {
            set({
              error:
                task.error === "stage3_timeout"
                  ? "当前图像过于复杂，已为您跳过终极优化"
                  : "已为您跳过终极优化",
            });
          } else if (task.status === "failed") {
            set({ error: `优化失败：${task.error ?? "未知错误"}` });
          }
        }
      };
      es.onerror = () => es.close();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "优化请求失败" });
    }
  },

  clearError: () => set({ error: null }),
}));
