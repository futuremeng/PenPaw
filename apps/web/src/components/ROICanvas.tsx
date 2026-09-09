import { useEffect, useMemo, useState } from "react";
import { Image as KonvaImage, Line, Stage } from "react-konva";
import { useEditorStore } from "../store/editorStore";
import type { RoiBox } from "../types";

const MAX_SIZE = 480;

/** ROI 框选画布：拖拽创建区域，点击区域删除（M1 简化版 SAM 交互，M2 接真实 SAM 点选）。 */
export function ROICanvas() {
  const asset = useEditorStore((s) => s.asset)!;
  const imageUrl = useEditorStore((s) => s.imageUrl)!;
  const regions = useEditorStore((s) => s.regions);
  const setRegions = useEditorStore((s) => s.setRegions);

  const scale = Math.min(1, MAX_SIZE / Math.max(asset.width, asset.height));
  const width = asset.width * scale;
  const height = asset.height * scale;

  const [konvaImg, setKonvaImg] = useState<HTMLImageElement | null>(null);
  const [draft, setDraft] = useState<RoiBox | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const img = new Image();
    img.onload = () => setKonvaImg(img);
    img.src = imageUrl;
  }, [imageUrl]);

  const existing = useMemo(
    () =>
      regions.map((r, i) => (
        <Line
          key={i}
          points={[
            r.x * scale, r.y * scale,
            (r.x + r.width) * scale, r.y * scale,
            (r.x + r.width) * scale, (r.y + r.height) * scale,
            r.x * scale, (r.y + r.height) * scale,
          ]}
          closed
          stroke="#4F7CFF"
          strokeWidth={2}
          fill="rgba(79,124,255,0.15)"
          onMouseDown={(e) => {
            e.cancelBubble = true; // 点中已有区域时不启动新框选
          }}
          onTap={() => setRegions(regions.filter((_, j) => j !== i))}
        />
      )),
    [regions, scale, setRegions]
  );

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-1 text-sm font-medium text-slate-300">2. 框选语义区域（ROI）</h2>
      <p className="mb-3 text-xs text-slate-500">
        拖拽创建区域 · 点击区域删除 · 不框选则全图解析
      </p>
      <div className="overflow-hidden rounded">
        <Stage
          width={width}
          height={height}
          onMouseDown={(e) => {
            const pos = e.target.getStage()!.getPointerPosition();
            if (pos) setDragStart(pos);
          }}
          onMouseMove={(e) => {
            if (!dragStart) return;
            const pos = e.target.getStage()!.getPointerPosition();
            if (!pos) return;
            const a = { x: dragStart.x / scale, y: dragStart.y / scale };
            const b = { x: pos.x / scale, y: pos.y / scale };
            setDraft({
              x: Math.min(a.x, b.x),
              y: Math.min(a.y, b.y),
              width: Math.abs(b.x - a.x),
              height: Math.abs(b.y - a.y),
            });
          }}
          onMouseUp={() => {
            if (draft && draft.width > 8 && draft.height > 8) {
              setRegions([...regions, { ...draft, label: `region-${regions.length + 1}` }]);
            }
            setDraft(null);
            setDragStart(null);
          }}
        >
          {konvaImg && <KonvaImage image={konvaImg} width={width} height={height} />}
          {existing}
          {draft && (
            <Line
              points={[
                draft.x * scale, draft.y * scale,
                (draft.x + draft.width) * scale, draft.y * scale,
                (draft.x + draft.width) * scale, (draft.y + draft.height) * scale,
                draft.x * scale, (draft.y + draft.height) * scale,
              ]}
              closed
              stroke="#FF7A59"
              strokeWidth={2}
              dash={[4, 4]}
            />
          )}
        </Stage>
      </div>
    </div>
  );
}
