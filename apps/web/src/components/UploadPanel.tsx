import { useRef } from "react";
import { useEditorStore } from "../store/editorStore";

export function UploadPanel() {
  const upload = useEditorStore((s) => s.upload);
  const asset = useEditorStore((s) => s.asset);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-sm font-medium text-slate-300">1. 上传参考图</h2>
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void upload(file);
          e.target.value = "";
        }}
      />
      <button
        onClick={() => inputRef.current?.click()}
        className="w-full rounded border border-dashed border-slate-600 py-6 text-sm text-slate-400 hover:border-slate-400 hover:text-slate-200"
      >
        {asset ? "重新上传（JPG / PNG / WebP，≤ 10MB）" : "点击选择图像（JPG / PNG / WebP，≤ 10MB）"}
      </button>
      {asset && (
        <p className="mt-2 text-xs text-slate-500">
          {asset.width}×{asset.height}
          {asset.downsampled && "（已自动缩放）"} · 资产 24h 后自动销毁
        </p>
      )}
    </div>
  );
}
