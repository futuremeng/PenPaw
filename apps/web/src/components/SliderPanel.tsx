import { useEffect, useRef } from "react";
import { useEditorStore } from "../store/editorStore";

/** 意图滑块（PRD §4.1）+ 300ms debounce 触发预览（PRD §4.2 请求节流）。 */
export function SliderPanel() {
  const smoothness = useEditorStore((s) => s.smoothness);
  const detail = useEditorStore((s) => s.detail);
  const setSmoothness = useEditorStore((s) => s.setSmoothness);
  const setDetail = useEditorStore((s) => s.setDetail);
  const runPreview = useEditorStore((s) => s.runPreview);
  const asset = useEditorStore((s) => s.asset);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 资产就绪后先跑一次默认预览
  useEffect(() => {
    if (asset) void runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asset?.asset_id]);

  const schedulePreview = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void runPreview(), 300);
  };

  return (
    <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="text-sm font-medium text-slate-300">3. 意图控制</h2>
      <label className="block text-xs text-slate-400">
        <div className="mb-1 flex justify-between">
          <span>线条平滑度（影响形状）</span>
          <span className="text-slate-200">{smoothness}</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={smoothness}
          onChange={(e) => {
            setSmoothness(Number(e.target.value));
            schedulePreview();
          }}
          className="w-full accent-blue-500"
        />
      </label>
      <label className="block text-xs text-slate-400">
        <div className="mb-1 flex justify-between">
          <span>细节保留度（影响色块数量）</span>
          <span className="text-slate-200">{detail}</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={detail}
          onChange={(e) => {
            setDetail(Number(e.target.value));
            schedulePreview();
          }}
          className="w-full accent-orange-400"
        />
      </label>
    </div>
  );
}
