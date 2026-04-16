"use client";

import { use, useEffect, useState } from "react";
import { ProjectLoader } from "@/components/ProjectLoader";
import { useSections, usePlanSections, useDeleteSections, useUpdateSectionChapter } from "@/hooks/useSections";
import { useChapters } from "@/hooks/useChapters";
import { useTemplates } from "@/hooks/useSettings";
import { useSources } from "@/hooks/useSources";
import { useChunks, type Chunk } from "@/hooks/useChunks";
import { useNavigationGuard } from "@/hooks/useNavigationGuard";
import { StepBar } from "@/components/layout/StepBar";
import Link from "next/link";
import type { SectionPlan, SlidePlan, SlidePlanChunk } from "@/lib/types";

export default function SectionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProjectLoader projectId={id}>
      {(project) => <SectionsContent projectId={id} projectName={project.name} />}
    </ProjectLoader>
  );
}

function SectionsContent({ projectId, projectName }: { projectId: string; projectName: string }) {
  const { data: sections, isLoading, error } = useSections(projectId);
  const { data: chapters } = useChapters(projectId);
  const { data: templateData } = useTemplates();
  const planMutation = usePlanSections(projectId);
  const deleteMutation = useDeleteSections(projectId);
  const updateMutation = useUpdateSectionChapter(projectId);

  useNavigationGuard(planMutation.isPending, "Sektionsplanung läuft noch. Wirklich verlassen?");

  const [editedSections, setEditedSections] = useState<Record<number, SlidePlan[]>>({});
  const [dirtyChapters, setDirtyChapters] = useState<Set<number>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<{ chapterIdx: number; slideIdx: number } | null>(null);
  const [confirmReplan, setConfirmReplan] = useState(false);

  // Chunk picker state
  const [chunkPickerKey, setChunkPickerKey] = useState<string | null>(null); // "chIdx-slideIdx"
  const [pickerSourceId, setPickerSourceId] = useState<string | null>(null);
  const [pickerSearch, setPickerSearch] = useState("");
  const { data: sources } = useSources(projectId);
  const { data: pickerChunks } = useChunks(projectId, pickerSourceId, pickerSearch);

  const templateTypes = templateData?.types ?? [];
  const templateLabels = templateData?.labels ?? {};

  // Sync edits from server data
  useEffect(() => {
    if (sections) {
      const initial: Record<number, SlidePlan[]> = {};
      for (const sec of sections) {
        initial[sec.chapter_index] = sec.slides.map((s) => ({ ...s }));
      }
      setEditedSections(initial);
      setDirtyChapters(new Set());
      setDeleteConfirm(null);
    }
  }, [sections]);

  const hasSections = sections && sections.length > 0;
  const hasChapters = chapters && chapters.length > 0;

  // ── Edit helpers ──────────────────────────────────────────────────

  const updateSlideField = (
    chapterIdx: number,
    slideIdx: number,
    field: keyof SlidePlan,
    value: string
  ) => {
    setEditedSections((prev) => ({
      ...prev,
      [chapterIdx]: prev[chapterIdx].map((s, i) =>
        i === slideIdx ? { ...s, [field]: value } : s
      ),
    }));
    setDirtyChapters((prev) => new Set(prev).add(chapterIdx));
  };

  const removeSlide = (chapterIdx: number, slideIdx: number) => {
    setEditedSections((prev) => ({
      ...prev,
      [chapterIdx]: prev[chapterIdx].filter((_, i) => i !== slideIdx),
    }));
    setDirtyChapters((prev) => new Set(prev).add(chapterIdx));
    setDeleteConfirm(null);
  };

  const addSlide = (chapterIdx: number) => {
    setEditedSections((prev) => ({
      ...prev,
      [chapterIdx]: [
        ...(prev[chapterIdx] ?? []),
        { template_type: templateTypes[0] ?? "content", brief: "", prompt: "", chunks: [] },
      ],
    }));
    setDirtyChapters((prev) => new Set(prev).add(chapterIdx));
  };

  const saveChapter = (chapterIdx: number) => {
    const slides = editedSections[chapterIdx] ?? [];
    updateMutation.mutate(
      { chapterIndex: chapterIdx, slides },
      {
        onSuccess: () => {
          setDirtyChapters((prev) => {
            const next = new Set(prev);
            next.delete(chapterIdx);
            return next;
          });
        },
      }
    );
  };

  // ── Chunk helpers ──────────────────────────────────────────────────

  const toggleChunkPicker = (chIdx: number, slideIdx: number) => {
    const key = `${chIdx}-${slideIdx}`;
    setChunkPickerKey((prev) => (prev === key ? null : key));
    setPickerSourceId(null);
    setPickerSearch("");
  };

  const addChunk = (chIdx: number, slideIdx: number, chunk: Chunk) => {
    const item: SlidePlanChunk = {
      text: chunk.text,
      distance: null,
      selected: true,
      metadata: chunk.metadata as SlidePlanChunk["metadata"],
    };
    setEditedSections((prev) => ({
      ...prev,
      [chIdx]: prev[chIdx].map((s, i) =>
        i === slideIdx ? { ...s, chunks: [...(s.chunks ?? []), item] } : s
      ),
    }));
    setDirtyChapters((prev) => new Set(prev).add(chIdx));
  };

  const toggleChunkSelected = (chIdx: number, slideIdx: number, chunkIdx: number) => {
    setEditedSections((prev) => ({
      ...prev,
      [chIdx]: prev[chIdx].map((s, i) =>
        i === slideIdx
          ? {
              ...s,
              chunks: s.chunks?.map((c, ci) =>
                ci === chunkIdx ? { ...c, selected: !c.selected } : c
              ),
            }
          : s
      ),
    }));
    setDirtyChapters((prev) => new Set(prev).add(chIdx));
  };

  const removeChunk = (chIdx: number, slideIdx: number, chunkIdx: number) => {
    setEditedSections((prev) => ({
      ...prev,
      [chIdx]: prev[chIdx].map((s, i) =>
        i === slideIdx ? { ...s, chunks: s.chunks?.filter((_, ci) => ci !== chunkIdx) } : s
      ),
    }));
    setDirtyChapters((prev) => new Set(prev).add(chIdx));
  };

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Sektionsplanung — {projectName}</h1>
      <StepBar projectId={projectId} currentStep="sections" />

      {isLoading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Sektionen laden...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/5 p-4">
          <p className="text-[var(--error)] text-sm">Fehler: {error.message}</p>
        </div>
      )}

      {!isLoading && !error && !hasChapters && !hasSections && (
        <div className="rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/5 p-4 space-y-2">
          <p className="text-[var(--warning)] text-sm">Bitte zuerst Kapitel planen und freigeben.</p>
          <Link href={`/projects/${projectId}/chapters`} className="inline-block text-sm text-[var(--accent)] hover:underline">
            Zur Kapitelplanung
          </Link>
        </div>
      )}

      {!hasSections && !planMutation.isPending && hasChapters && !isLoading && !error && (
        <button
          onClick={() => planMutation.mutate()}
          className="w-full py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors"
        >
          Sektionen planen lassen
        </button>
      )}

      {planMutation.isPending && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Sektionen werden geplant...</span>
        </div>
      )}

      {planMutation.isError && (
        <div className="rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/5 p-4">
          <p className="text-[var(--error)] text-sm">Fehler: {planMutation.error.message}</p>
        </div>
      )}

      {hasSections && (
        <div className="space-y-8">
          {sections.map((sec) => {
            const chIdx = sec.chapter_index;
            const slides = editedSections[chIdx] ?? sec.slides;
            const isDirty = dirtyChapters.has(chIdx);
            const chapterTitle = chapters?.find((c) => c.chapter_index === chIdx)?.title;

            return (
              <div key={chIdx} className="space-y-3">
                {/* Chapter header */}
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">
                    Kapitel {chIdx + 1}{chapterTitle ? ` — ${chapterTitle}` : ""}
                  </h2>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {slides.length} Folien
                    {(() => {
                      // Deduplicate chunks across slides by text content
                      const seen = new Set<string>();
                      const uniqueSelected: { text: string }[] = [];
                      for (const s of slides) {
                        for (const c of s.chunks ?? []) {
                          if (c.selected !== false && !seen.has(c.text)) {
                            seen.add(c.text);
                            uniqueSelected.push(c);
                          }
                        }
                      }
                      if (uniqueSelected.length === 0) return null;
                      const totalTokens = uniqueSelected.reduce(
                        (sum, c) => sum + Math.ceil(c.text.length / 4), 0
                      );
                      return ` · ~${totalTokens} Token (${uniqueSelected.length} Chunks)`;
                    })()}
                  </span>
                </div>

                {/* Slide cards */}
                <div className="space-y-3">
                  {slides.map((slide, si) => (
                    <div
                      key={si}
                      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 space-y-3"
                    >
                      {/* Slide header */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[var(--accent-light)]">Folie {si + 1}</span>

                        {deleteConfirm?.chapterIdx === chIdx && deleteConfirm?.slideIdx === si ? (
                          <div className="flex gap-2">
                            <button
                              onClick={() => removeSlide(chIdx, si)}
                              className="px-3 py-1 rounded-lg bg-[var(--error)] text-white text-xs font-semibold"
                            >
                              Löschen
                            </button>
                            <button
                              onClick={() => setDeleteConfirm(null)}
                              className="px-3 py-1 rounded-lg border border-[var(--border-subtle)] text-xs hover:bg-[var(--bg-hover)]"
                            >
                              Nein
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeleteConfirm({ chapterIdx: chIdx, slideIdx: si })}
                            className="text-[var(--text-secondary)] hover:text-[var(--error)] transition px-2"
                            title="Folie löschen"
                          >
                            🗑️
                          </button>
                        )}
                      </div>

                      {/* Slideart */}
                      <div>
                        <label className="block text-xs text-[var(--text-secondary)] mb-1">Slideart</label>
                        {templateTypes.length > 0 ? (
                          <select
                            value={slide.template_type}
                            onChange={(e) => updateSlideField(chIdx, si, "template_type", e.target.value)}
                            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
                          >
                            {templateTypes.map((t) => (
                              <option key={t} value={t}>
                                {templateLabels[t] ?? t}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            value={slide.template_type}
                            onChange={(e) => updateSlideField(chIdx, si, "template_type", e.target.value)}
                            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
                          />
                        )}
                      </div>

                      {/* Inhalt / Brief */}
                      <div>
                        <label className="block text-xs text-[var(--text-secondary)] mb-1">Inhalt</label>
                        <textarea
                          value={slide.brief}
                          onChange={(e) => updateSlideField(chIdx, si, "brief", e.target.value)}
                          rows={2}
                          placeholder="Was soll diese Folie enthalten?"
                          className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm resize-y focus:border-[var(--accent)] focus:outline-none"
                        />
                      </div>

                      {/* Prompt Override */}
                      <div>
                        <label className="block text-xs text-[var(--text-secondary)] mb-1">
                          Prompt Override{" "}
                          <span className="text-[10px] opacity-60">(optional — überschreibt Standard-Generierungsprompt)</span>
                        </label>
                        <textarea
                          value={slide.prompt ?? ""}
                          onChange={(e) => updateSlideField(chIdx, si, "prompt", e.target.value)}
                          rows={2}
                          placeholder="Leer lassen = Standard-Prompt wird verwendet"
                          className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm resize-y focus:border-[var(--accent)] focus:outline-none placeholder:text-[var(--text-secondary)]"
                        />
                      </div>

                      {/* Chunk-Zuweisung */}
                      <ChunkSection
                        slide={slide}
                        chIdx={chIdx}
                        slideIdx={si}
                        isPickerOpen={chunkPickerKey === `${chIdx}-${si}`}
                        onTogglePicker={() => toggleChunkPicker(chIdx, si)}
                        onToggleSelected={(ci) => toggleChunkSelected(chIdx, si, ci)}
                        onRemoveChunk={(ci) => removeChunk(chIdx, si, ci)}
                        onAddChunk={(chunk) => addChunk(chIdx, si, chunk)}
                        pickerSourceId={pickerSourceId}
                        onPickerSourceChange={(id) => { setPickerSourceId(id); setPickerSearch(""); }}
                        pickerSearch={pickerSearch}
                        onPickerSearchChange={setPickerSearch}
                        sources={sources}
                        pickerChunks={pickerChunks}
                      />
                    </div>
                  ))}
                </div>

                {/* Add slide */}
                <button
                  onClick={() => addSlide(chIdx)}
                  className="w-full py-2 rounded-xl border-2 border-dashed border-[var(--border-subtle)] hover:border-[var(--accent)] text-[var(--text-secondary)] hover:text-[var(--accent-light)] transition-colors text-sm"
                >
                  + Folie hinzufügen
                </button>

                {/* Save chapter */}
                {isDirty && (
                  <button
                    onClick={() => saveChapter(chIdx)}
                    disabled={updateMutation.isPending}
                    className="w-full py-2 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold text-sm transition-colors disabled:opacity-50"
                  >
                    {updateMutation.isPending ? "Wird gespeichert..." : "Änderungen speichern"}
                  </button>
                )}
              </div>
            );
          })}

          {/* CTA */}
          <Link
            href={`/projects/${projectId}/generation`}
            className="block w-full py-3 rounded-xl bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] text-white font-semibold text-center hover:opacity-90 transition"
          >
            Weiter zur Generierung →
          </Link>

          {/* Replan */}
          <div className="flex justify-end">
            {!confirmReplan ? (
              <button
                onClick={() => setConfirmReplan(true)}
                className="px-6 py-2 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] text-sm transition-colors"
              >
                Neu planen
              </button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setConfirmReplan(false);
                    deleteMutation.mutate(undefined, { onSuccess: () => planMutation.mutate() });
                  }}
                  className="px-6 py-2 rounded-xl bg-[var(--error)] text-white text-sm font-semibold"
                >
                  Ja, neu planen
                </button>
                <button
                  onClick={() => setConfirmReplan(false)}
                  className="px-6 py-2 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm"
                >
                  Abbrechen
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Chunk Detail Section Component ──────────────────────────────────

function ChunkSection({
  slide,
  chIdx,
  slideIdx,
  isPickerOpen,
  onTogglePicker,
  onToggleSelected,
  onRemoveChunk,
  onAddChunk,
  pickerSourceId,
  onPickerSourceChange,
  pickerSearch,
  onPickerSearchChange,
  sources,
  pickerChunks,
}: {
  slide: SlidePlan;
  chIdx: number;
  slideIdx: number;
  isPickerOpen: boolean;
  onTogglePicker: () => void;
  onToggleSelected: (chunkIdx: number) => void;
  onRemoveChunk: (chunkIdx: number) => void;
  onAddChunk: (chunk: Chunk) => void;
  pickerSourceId: string | null;
  onPickerSourceChange: (id: string | null) => void;
  pickerSearch: string;
  onPickerSearchChange: (search: string) => void;
  sources: { id: string; filename: string }[] | undefined;
  pickerChunks: Chunk[] | undefined;
}) {
  const chunks = slide.chunks ?? [];
  const selectedChunks = chunks.filter((c) => c.selected !== false);
  const selectedTokens = selectedChunks.reduce((sum, c) => sum + Math.ceil(c.text.length / 4), 0);

  return (
    <div className="border-t border-[var(--border-subtle)] pt-3 space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <button
          onClick={onTogglePicker}
          className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
            isPickerOpen
              ? "border-[var(--accent)] text-[var(--accent)]"
              : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent-light)]"
          }`}
        >
          + Chunk suchen
        </button>
        <span className="text-xs text-[var(--text-secondary)]">
          {selectedChunks.length}/{chunks.length} selektiert · ~{selectedTokens} Token
        </span>
      </div>

      {/* Chunk list */}
      {chunks.length > 0 && (
        <div className="space-y-1">
          {chunks.map((chunk, ci) => {
            const relevance = chunk.distance != null ? Math.round((1 - chunk.distance) * 100) : null;
            const tokenEst = Math.ceil(chunk.text.length / 4);
            const isSelected = chunk.selected !== false;
            const filename = chunk.metadata?.filename ?? "?";
            const chunkIndex = chunk.metadata?.chunk_index;

            return (
              <div
                key={ci}
                className={`rounded-lg p-2.5 space-y-1 transition-colors ${
                  isSelected ? "bg-[var(--bg-main)]" : "bg-[var(--bg-main)] opacity-50"
                }`}
              >
                <div className="flex items-start gap-2">
                  {/* Checkbox */}
                  <button
                    onClick={() => onToggleSelected(ci)}
                    className="shrink-0 mt-0.5 w-4 h-4 rounded border border-[var(--border-subtle)] flex items-center justify-center text-xs transition-colors hover:border-[var(--accent)]"
                    title={isSelected ? "Deselektieren" : "Selektieren"}
                  >
                    {isSelected && <span className="text-[var(--accent)]">&#10003;</span>}
                  </button>

                  {/* Chunk info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-medium text-[var(--text-primary)] truncate">
                        {filename}
                        {chunkIndex != null && ` (Chunk ${chunkIndex})`}
                      </span>
                      {relevance != null ? (
                        <span className={`shrink-0 ${
                          relevance >= 75 ? "text-[var(--success)]" :
                          relevance >= 50 ? "text-[var(--warning)]" :
                          "text-[var(--text-secondary)]"
                        }`}>
                          Relevanz: {relevance}%
                        </span>
                      ) : (
                        <span className="shrink-0 text-[var(--text-secondary)] italic">
                          manuell
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] line-clamp-2 mt-0.5">
                      {chunk.text}
                    </p>
                    <span className="text-[10px] text-[var(--text-secondary)]">~{tokenEst} Token</span>
                  </div>

                  {/* Remove button */}
                  <button
                    onClick={() => onRemoveChunk(ci)}
                    className="shrink-0 text-[var(--text-secondary)] hover:text-[var(--error)] transition text-xs"
                    title="Chunk entfernen"
                  >
                    &#10005;
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Chunk picker */}
      {isPickerOpen && (
        <div className="space-y-2 border-t border-[var(--border-subtle)] pt-2">
          <p className="text-xs text-[var(--text-secondary)] font-medium">Chunk hinzufuegen:</p>
          <select
            value={pickerSourceId ?? ""}
            onChange={(e) => onPickerSourceChange(e.target.value || null)}
            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-2 py-1.5 text-xs focus:border-[var(--accent)] focus:outline-none"
          >
            <option value="">Quelle waehlen...</option>
            {sources?.map((s) => (
              <option key={s.id} value={s.id}>{s.filename}</option>
            ))}
          </select>

          {pickerSourceId && (
            <input
              value={pickerSearch}
              onChange={(e) => onPickerSearchChange(e.target.value)}
              placeholder="Suchen..."
              className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-2 py-1.5 text-xs focus:border-[var(--accent)] focus:outline-none placeholder:text-[var(--text-secondary)]"
            />
          )}

          {pickerSourceId && pickerChunks && pickerChunks.length === 0 && (
            <p className="text-xs text-[var(--text-secondary)]">Keine Chunks gefunden.</p>
          )}

          {pickerChunks?.map((chunk) => {
            const alreadyAssigned = (slide.chunks ?? []).some(
              (c) => c.text === chunk.text && c.metadata?.filename === (chunk.metadata as Record<string, unknown>)?.filename
            );
            return (
              <div key={chunk.id} className="flex items-start gap-2 bg-[var(--bg-main)] rounded-lg p-2">
                <p className="flex-1 text-xs text-[var(--text-secondary)] line-clamp-3">{chunk.text}</p>
                <button
                  onClick={() => !alreadyAssigned && onAddChunk(chunk)}
                  disabled={alreadyAssigned}
                  className="shrink-0 text-xs px-2 py-0.5 rounded-md bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-medium transition-colors disabled:opacity-40 disabled:cursor-default"
                >
                  {alreadyAssigned ? "&#10003;" : "+"}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
