import { useEditorStore } from "../store/editorStore";
import { client } from "../api/client";

/** 导出（PRD §4.2：快速导出 / 精细优化并导出 + SSE 进度条）。 */
export function ExportPanel() {
  const asset = useEditorStore((s) => s.asset)!;
  const preview = useEditorStore((s) => s.preview);
  const task = useEditorStore((s) => s.task);
  const runOptimize = useEditorStore((s) => s.runOptimize);

  const optimizing = task && !task.status.startsWith("s") && task.status !== "degraded" && task.status !== "failed";
  const optimizedDone = task?.status === "succeeded";

  return (
    <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="text-sm font-medium text-slate-300">4. 导出</h2>

      <a
        href={preview ? client.exportUrl(asset.asset_id, false) : "#"}
        download
        className={`block w-full rounded px-4 py-2 text-center text-sm ${
          preview
            ? "bg-slate-700 text-slate-100 hover:bg-slate-600"
            : "cursor-not-allowed bg-slate-800 text-slate-600"
        }`}
      >
        快速导出（Stage 2 预览结果）
      </a>

      <button
        onClick={() => void runOptimize()}
        disabled={!preview || !!optimizing}
        className={`w-full rounded px-4 py-2 text-sm ${
          !preview || optimizing
            ? "cursor-not-allowed bg-slate-800 text-slate-600"
            : "bg-blue-600 text-white hover:bg-blue-500"
        }`}
      >
        {optimizing ? `精细优化中… ${Math.round((task?.progress ?? 0) * 100)}%` : "精细优化并导出（Stage 3）"}
      </button>

      {optimizing && (
        <div className="h-1.5 w-full overflow-hidden rounded bg-slate-800">
          <div
            className="h-full bg-blue-500 transition-all"
            style={{ width: `${(task?.progress ?? 0) * 100}%` }}
          />
        </div>
      )}

      {optimizedDone && (
        <a
          href={client.exportUrl(asset.asset_id, true)}
          download
          className="block w-full rounded bg-emerald-600 px-4 py-2 text-center text-sm text-white hover:bg-emerald-500"
        >
          下载优化后 SVG（控制点 {task?.control_points}）
        </a>
      )}
    </div>
  );
}
