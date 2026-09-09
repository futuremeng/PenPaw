import { useEditorStore } from "./store/editorStore";
import { ExportPanel } from "./components/ExportPanel";
import { PreviewPane } from "./components/PreviewPane";
import { ROICanvas } from "./components/ROICanvas";
import { SliderPanel } from "./components/SliderPanel";
import { UploadPanel } from "./components/UploadPanel";

export default function App() {
  const error = useEditorStore((s) => s.error);
  const clearError = useEditorStore((s) => s.clearError);
  const asset = useEditorStore((s) => s.asset);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-lg font-semibold">
          PenPaw <span className="text-slate-400">神经矢量引擎 · MVP</span>
        </h1>
      </header>

      {error && (
        <div className="mx-6 mt-4 flex items-center justify-between rounded border border-amber-600 bg-amber-950/40 px-4 py-2 text-sm text-amber-300">
          <span>{error}</span>
          <button onClick={clearError} className="text-amber-400 hover:text-amber-200">
            ✕
          </button>
        </div>
      )}

      <main className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-2">
        <section className="space-y-4">
          <UploadPanel />
          {asset && <ROICanvas />}
          {asset && <SliderPanel />}
        </section>
        <section className="space-y-4">
          <PreviewPane />
          {asset && <ExportPanel />}
        </section>
      </main>
    </div>
  );
}
