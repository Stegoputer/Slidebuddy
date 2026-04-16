"use client";

import { use, useCallback, useState } from "react";
import { ProjectLoader } from "@/components/ProjectLoader";
import { useSources, useUploadSources, useAddYoutube, useDeleteSource } from "@/hooks/useSources";
import { StepBar } from "@/components/layout/StepBar";
import Link from "next/link";

const STATUS_LABEL: Record<string, string> = {
  done: "Fertig",
  error: "Fehler",
  processing: "Wird verarbeitet…",
  pending: "Ausstehend",
};

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProjectLoader projectId={id}>
      {(project) => <SourcesContent projectId={id} projectName={project.name} />}
    </ProjectLoader>
  );
}

function SourcesContent({ projectId, projectName }: { projectId: string; projectName: string }) {
  const { data: sources, isLoading } = useSources(projectId);
  const uploadSources = useUploadSources(projectId);
  const addYoutube = useAddYoutube(projectId);
  const deleteSource = useDeleteSource(projectId);

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const hasSources = (sources?.length ?? 0) > 0;

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length) uploadSources.mutate(files);
    },
    [uploadSources]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (files.length) uploadSources.mutate(files);
    },
    [uploadSources]
  );

  const handleYoutube = () => {
    if (!youtubeUrl.trim()) return;
    addYoutube.mutate(youtubeUrl.trim(), { onSuccess: () => setYoutubeUrl("") });
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">Quellen — {projectName}</h1>
      <StepBar projectId={projectId} currentStep="sources" />

      {/* File Upload */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Dateien hochladen</h2>
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
            dragActive
              ? "border-[var(--accent)] bg-[var(--accent-glow)]"
              : "border-[var(--border-subtle)] hover:border-[var(--accent)]"
          }`}
        >
          <p className="text-[var(--text-secondary)] mb-2">
            Dateien hierher ziehen oder{" "}
            <label className="text-[var(--accent)] cursor-pointer hover:underline">
              durchsuchen
              <input type="file" multiple className="hidden" onChange={handleFileSelect} />
            </label>
          </p>
          <p className="text-xs text-[var(--text-secondary)]">PDF, PPTX, TXT, MD, CSV, XLSX, HTML</p>
        </div>
        {uploadSources.isPending && <p className="text-sm text-[var(--accent)] mt-2">Wird hochgeladen und verarbeitet...</p>}
        {uploadSources.isError && <p className="text-sm text-[var(--error)] mt-2">{uploadSources.error.message}</p>}
      </section>

      {/* YouTube */}
      <section>
        <h2 className="text-lg font-semibold mb-3">YouTube-Untertitel</h2>
        <div className="flex gap-2">
          <input
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleYoutube()}
            placeholder="YouTube-URL (z. B. https://youtube.com/watch?v=...)"
            className="flex-1 px-4 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
          />
          <button onClick={handleYoutube} disabled={addYoutube.isPending || !youtubeUrl.trim()} className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white font-semibold disabled:opacity-50">
            {addYoutube.isPending ? "Abrufen..." : "Abrufen"}
          </button>
        </div>
        {addYoutube.isError && (
          <p className="text-sm text-[var(--error)] mt-2">{addYoutube.error?.message}</p>
        )}
      </section>

      {/* Source List */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Hochgeladene Quellen</h2>
        {isLoading ? (
          <p className="text-[var(--text-secondary)]">Laden...</p>
        ) : !sources?.length ? (
          <p className="text-[var(--text-secondary)]">Noch keine Quellen hochgeladen.</p>
        ) : (
          <div className="space-y-2">
            {sources.map((s) => (
              <div key={s.id}>
                <div className="flex items-center justify-between bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-lg shrink-0">{s.source_type === "youtube" ? "🎬" : s.source_type === "pdf" ? "📄" : "📎"}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{s.filename}</p>
                      <p className="text-xs text-[var(--text-secondary)]">
                        {s.chunk_count} Chunks ·{" "}
                        <span className={s.processing_status === "error" ? "text-[var(--error)]" : s.processing_status === "done" ? "text-[var(--success)]" : "text-[var(--text-secondary)]"}>
                          {STATUS_LABEL[s.processing_status] ?? s.processing_status}
                        </span>
                      </p>
                    </div>
                  </div>

                  {deleteConfirmId === s.id ? (
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => { deleteSource.mutate(s.id); setDeleteConfirmId(null); }}
                        className="px-3 py-1 rounded-lg bg-[var(--error)] text-white text-xs font-semibold"
                      >
                        Löschen
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        className="px-3 py-1 rounded-lg border border-[var(--border-subtle)] text-xs hover:bg-[var(--bg-hover)]"
                      >
                        Nein
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirmId(s.id)}
                      className="text-[var(--text-secondary)] hover:text-[var(--error)] transition shrink-0 px-2"
                    >
                      🗑️
                    </button>
                  )}
                </div>
                {s.processing_status === "error" && s.error_message && (
                  <p className="text-xs text-[var(--error)] mt-1 px-4">{s.error_message}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* CTA to next step */}
      {hasSources && (
        <Link
          href={`/projects/${projectId}/chapters`}
          className="block w-full py-3 rounded-xl bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] text-white font-semibold text-center hover:opacity-90 transition"
        >
          Weiter zur Kapitelplanung →
        </Link>
      )}
    </div>
  );
}
