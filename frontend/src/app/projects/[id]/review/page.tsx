"use client";

import { use, useState } from "react";
import { ProjectLoader } from "@/components/ProjectLoader";
import { useSlides, useUpdateSlide } from "@/hooks/useSlides";
import { SlideCard } from "@/components/SlideCard";
import { StepBar } from "@/components/layout/StepBar";
import Link from "next/link";

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProjectLoader projectId={id}>
      {(project) => <ReviewContent projectId={id} projectName={project.name} />}
    </ProjectLoader>
  );
}

function ReviewContent({ projectId, projectName }: { projectId: string; projectName: string }) {
  const { data: slides, isLoading, error } = useSlides(projectId);
  const updateMutation = useUpdateSlide(projectId);
  const [downloading, setDownloading] = useState<"txt" | "pptx" | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  const handleDownload = async (format: "txt" | "pptx") => {
    setDownloading(format);
    try {
      const res = await fetch(`/api/projects/${projectId}/export/${format}`);
      if (!res.ok) throw new Error("Export fehlgeschlagen");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${projectName}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Review & Export — {projectName}</h1>
      <StepBar projectId={projectId} currentStep="review" />

      {isLoading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Folien laden...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/5 p-4">
          <p className="text-[var(--error)] text-sm">Fehler beim Laden der Folien: {error.message}</p>
        </div>
      )}

      {!isLoading && !error && slides && slides.length > 0 && (
        <>
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">Export</h2>
            <div className="flex gap-3">
              <button onClick={() => handleDownload("txt")} disabled={downloading === "txt"} className="flex-1 py-3 rounded-xl bg-[var(--success)] hover:brightness-110 text-white font-semibold transition-all disabled:opacity-50">
                {downloading === "txt" ? "Wird exportiert..." : "Als TXT herunterladen"}
              </button>
              <button onClick={() => handleDownload("pptx")} disabled={downloading === "pptx"} className="flex-1 py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors disabled:opacity-50">
                {downloading === "pptx" ? "Wird exportiert..." : "Als PPTX herunterladen"}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Folien ({slides.length})</h2>
            {slides.map((slide, i) => (
              <SlideCard
                key={slide.id}
                slide={slide}
                index={i}
                saving={savingId === slide.id}
                onSave={(data) => {
                  setSavingId(slide.id);
                  updateMutation.mutate(
                    { slideId: slide.id, data },
                    { onSettled: () => setSavingId(null) }
                  );
                }}
              />
            ))}
          </div>
        </>
      )}

      {!isLoading && !error && (!slides || slides.length === 0) && (
        <div className="rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/5 p-4 space-y-2">
          <p className="text-[var(--warning)] text-sm">Noch keine Folien generiert.</p>
          <Link
            href={`/projects/${projectId}/generation`}
            className="inline-block text-sm text-[var(--accent)] hover:underline"
          >
            Zur Generierung
          </Link>
        </div>
      )}
    </div>
  );
}
