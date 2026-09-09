import { useEffect } from "react";
import { useEditorStore } from "../store/editorStore";

/** 实时预览（快系统，PRD §4.2）+ 低置信度提示（PRD §5.2）。 */
export function PreviewPane() {
  const preview = useEditorStore((s) => s.preview);
  const previewLoading = useEditorStore((s) => s.previewLoading);
  const regions = useEditorStore((s) => s.regions);

  // ROI 变化也触发预览（300ms debounce 由 store 调用方保证；此处直接触发）
  useEffect(() => {
    const t = setTimeout(() => void useEditorStore.getState().runPreview(), 300);
    return () => clearTimeout(t);
  }, [regions]);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-300">实时预览</h2>
        {previewLoading && <span className="text-xs text-slate-500">生成中…</span>}
      </div>

      <div
        className="flex min-h-[320px] items-center justify-center overflow-hidden rounded bg-slate-950"
        dangerouslySetInnerHTML={
          preview ? { __html: preview.svg } : { __html: "<span class='text-xs text-slate-600'>上传图像后自动生成</span>" }
        }
      />

      {preview && (
        <div className="mt-3 flex gap-4 text-xs text-slate-400">
          <span>控制点：<b className="text-slate-200">{preview.control_points}</b></span>
          <span>
            置信度：<b className="text-slate-200">{(preview.confidence * 100).toFixed(0)}%</b>
          </span>
          {preview.confidence < 0.7 && (
            <span className="text-amber-400">路径可能存在自交叉，建议人工精修</span>
          )}
        </div>
      )}
    </div>
  );
}
