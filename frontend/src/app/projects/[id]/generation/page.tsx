"use client";

import { use, useCallback, useEffect, useState } from "react";
import { ProjectLoader } from "@/components/ProjectLoader";
import { useSlides, useGenerateSingle, useGenerateChapter } from "@/hooks/useSlides";
import { useSections } from "@/hooks/useSections";
import { useChapters } from "@/hooks/useChapters";
import { useSettings } from "@/hooks/useSettings";
import { useNavigationGuard } from "@/hooks/useNavigationGuard";
import { SlideCard } from "@/components/SlideCard";
import { StepBar } from "@/components/layout/StepBar";
import { api } from "@/lib/api";
import Link from "next/link";
import type { Project, Slide, SectionPlan, Chapter } from "@/lib/types";

const LENGTH_LABEL: Record<string, string> = { short: "Kurz", medium: "Mittel", long: "Ausführlich" };

export default function GenerationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProjectLoader projectId={id}>
      {(project) => (
        <GenerationContent project={project} projectId={id} />
      )}
    </ProjectLoader>
  );
}

function GenerationContent({
  project,
  projectId,
}: {
  project: Project;
  projectId: string;
}) {
  const defaultTextLength = project.global_text_length ?? "medium";

  const { data: slides, isLoading: slidesLoading, error: slidesError } = useSlides(projectId);
  const { data: sections, isLoading: sectionsLoading, error: sectionsError } = useSections(projectId);
  const { data: chapters, isLoading: chaptersLoading, error: chaptersError } = useChapters(projectId);
  const { data: settings } = useSettings();
  const generateSingle = useGenerateSingle(projectId);
  const generateChapter = useGenerateChapter(projectId);

  const [textLength, setTextLength] = useState(defaultTextLength);
  const [batchSize, setBatchSize] = useState(4);
  const [batchInput, setBatchInput] = useState("4");

  // Ziel-Karte state
  const [editingGoal, setEditingGoal] = useState(false);
  const [goalDraft, setGoalDraft] = useState("");
  const [currentGoal, setCurrentGoal] = useState(project.planning_prompt ?? null);

  // Sync batchSize from preferences once settings are loaded
  useEffect(() => {
    const prefBatch = settings?.preferences?.batch_size;
    if (typeof prefBatch === "number" && prefBatch > 0) {
      setBatchSize(prefBatch);
      setBatchInput(String(prefBatch));
    }
  }, [settings?.preferences?.batch_size]);
  const [generatingChapterIdx, setGeneratingChapterIdx] = useState<number | null>(null);
  const [slideErrors, setSlideErrors] = useState<Record<string, string>>({});

  useNavigationGuard(
    generatingChapterIdx !== null || generateSingle.isPending,
    "Generierung läuft noch. Wirklich verlassen?"
  );

  const isLoading = slidesLoading || sectionsLoading || chaptersLoading;
  const fetchError = slidesError || sectionsError || chaptersError;
  const hasSections = sections && sections.length > 0;
  const isGenerating = generatingChapterIdx !== null || generateSingle.isPending;

  const totalPlanned = sections?.reduce((s, sec) => s + sec.slides.length, 0) ?? 0;
  const totalGenerated = slides?.length ?? 0;
  const allDone = totalPlanned > 0 && totalGenerated >= totalPlanned;

  // Group generated slides by chapter using chapter_id → chapter_index mapping
  const slidesByChapter = groupSlidesByChapter(slides ?? [], chapters ?? []);

  // ── Save goal ────────────────────────────────────────────────────────────

  const saveGoal = useCallback(async (newGoal: string) => {
    try {
      await api.put(`/projects/${projectId}`, { planning_prompt: newGoal });
      setCurrentGoal(newGoal);
    } catch (err) {
      console.error("Failed to save goal:", err);
    }
  }, [projectId]);

  // ── Generate all chapters sequentially ──────────────────────────────────

  const handleGenerateAll = async () => {
    if (!sections) return;
    setSlideErrors({});
    let generated = false;
    for (let i = 0; i < sections.length; i++) {
      const sec = sections[i];
      const chIdx = sec.chapter_index;
      const existing = slidesByChapter[chIdx] ?? [];
      // Skip chapters that already have all slides
      if (existing.length >= sec.slides.length) continue;

      if (generated) {
        // Pause between chapters to avoid API rate limits
        await new Promise((r) => setTimeout(r, 2000));
      }
      setGeneratingChapterIdx(chIdx);
      try {
        await generateChapter.mutateAsync({
          chapterIndex: chIdx,
          textLength,
          batchSize,
        });
        generated = true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unbekannter Fehler";
        setSlideErrors((prev) => ({ ...prev, [`ch-${chIdx}`]: msg }));
        generated = true;
      }
    }
    setGeneratingChapterIdx(null);
  };

  // ── Generate a single slide ──────────────────────────────────────────────

  const handleGenerateSingle = async (chapterIndex: number, slideIndex: number) => {
    const key = `${chapterIndex}-${slideIndex}`;
    setSlideErrors((prev) => { const next = { ...prev }; delete next[key]; return next; });
    try {
      await generateSingle.mutateAsync({ chapterIndex, slideIndex, textLength });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Fehler";
      setSlideErrors((prev) => ({ ...prev, [key]: msg }));
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Generierung — {project.name}</h1>
      <StepBar projectId={projectId} currentStep="generation" />

      {/* Ziel der Präsentation */}
      {currentGoal && (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
              Ziel der Präsentation
            </span>
            {!editingGoal && (
              <button
                onClick={() => { setGoalDraft(currentGoal); setEditingGoal(true); }}
                className="text-xs text-[var(--accent)] hover:underline"
              >
                Bearbeiten
              </button>
            )}
          </div>
          {editingGoal ? (
            <div className="space-y-2 mt-2">
              <textarea
                value={goalDraft}
                onChange={(e) => setGoalDraft(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40 resize-none"
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setEditingGoal(false)}
                  className="text-xs text-[var(--text-secondary)] hover:underline"
                >
                  Abbrechen
                </button>
                <button
                  onClick={() => { saveGoal(goalDraft); setEditingGoal(false); }}
                  className="px-3 py-1 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white text-xs font-semibold transition-colors"
                >
                  Speichern
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap line-clamp-4">
              {currentGoal}
            </p>
          )}
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Daten laden...</span>
        </div>
      )}

      {fetchError && (
        <div className="rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/5 p-4">
          <p className="text-[var(--error)] text-sm">Fehler beim Laden: {fetchError.message}</p>
        </div>
      )}

      {!isLoading && !fetchError && !hasSections && (
        <div className="rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/5 p-4 space-y-2">
          <p className="text-[var(--warning)] text-sm">Bitte zuerst Sektionen planen.</p>
          <Link href={`/projects/${projectId}/sections`} className="inline-block text-sm text-[var(--accent)] hover:underline">
            Zur Sektionsplanung
          </Link>
        </div>
      )}

      {hasSections && !isLoading && (
        <>
          {/* Controls bar */}
          <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]">
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--text-secondary)] whitespace-nowrap">Textlänge</label>
              <select
                value={textLength}
                onChange={(e) => setTextLength(e.target.value)}
                disabled={isGenerating}
                className="px-3 py-1.5 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-sm focus:border-[var(--accent)] focus:outline-none disabled:opacity-50"
              >
                <option value="short">Kurz</option>
                <option value="medium">Mittel</option>
                <option value="long">Ausführlich</option>
              </select>
              {textLength !== defaultTextLength && (
                <span className="text-xs text-[var(--text-secondary)]">
                  (Standard: {LENGTH_LABEL[defaultTextLength] ?? defaultTextLength})
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--text-secondary)] whitespace-nowrap">Folien pro KI-Aufruf</label>
              <input
                type="number"
                min={1}
                max={20}
                value={batchInput}
                onChange={(e) => {
                  setBatchInput(e.target.value);
                  const n = parseInt(e.target.value, 10);
                  if (!isNaN(n) && n >= 1 && n <= 20) setBatchSize(n);
                }}
                onBlur={() => {
                  // Clamp and normalize on blur
                  const n = Math.max(1, Math.min(20, parseInt(batchInput, 10) || batchSize));
                  setBatchSize(n);
                  setBatchInput(String(n));
                }}
                disabled={isGenerating}
                className="w-16 px-2 py-1.5 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-sm text-center focus:border-[var(--accent)] focus:outline-none disabled:opacity-50"
              />
            </div>

            {!allDone && (
              <button
                onClick={handleGenerateAll}
                disabled={isGenerating}
                className="ml-auto px-5 py-2 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold text-sm transition-colors disabled:opacity-50"
              >
                {generatingChapterIdx !== null
                  ? `Kapitel ${generatingChapterIdx + 1} wird generiert...`
                  : `Alle ${totalPlanned - totalGenerated} Folien generieren`}
              </button>
            )}
          </div>

          {/* All done CTA */}
          {allDone && (
            <div className="rounded-xl bg-[var(--success)]/10 border border-[var(--success)]/30 p-5 space-y-3">
              <p className="text-center text-[var(--success)] font-semibold">
                Alle {totalGenerated} Folien wurden generiert!
              </p>
              <Link
                href={`/projects/${projectId}/review`}
                className="block w-full py-3 rounded-xl bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] text-white font-semibold text-center hover:opacity-90 transition"
              >
                Weiter zum Review & Export →
              </Link>
            </div>
          )}

          {/* Per-chapter slide grid */}
          <div className="space-y-8">
            {sections.map((sec) => {
              const chIdx = sec.chapter_index;
              const chapterSlides = slidesByChapter[chIdx] ?? [];
              const isGenThisChapter = generatingChapterIdx === chIdx;

              return (
                <div key={chIdx} className="space-y-3">
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold">Kapitel {chIdx + 1}</h2>
                    <span className="text-xs text-[var(--text-secondary)]">
                      {chapterSlides.length} / {sec.slides.length} Folien
                    </span>
                    {isGenThisChapter && (
                      <span className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                        <span className="w-3.5 h-3.5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin inline-block" />
                        Wird generiert...
                      </span>
                    )}
                    {slideErrors[`ch-${chIdx}`] && (
                      <span className="text-xs text-[var(--error)]">{slideErrors[`ch-${chIdx}`]}</span>
                    )}
                  </div>

                  <div className="space-y-3">
                    {sec.slides.map((plan, si) => {
                      const generated = chapterSlides[si] as Slide | undefined;
                      const errKey = `${chIdx}-${si}`;

                      if (generated) {
                        return <SlideCard key={si} slide={generated} index={si} />;
                      }

                      return (
                        <div
                          key={si}
                          className="rounded-xl border border-dashed border-[var(--border-subtle)] bg-[var(--bg-card)]/50 p-4 flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-[var(--accent-light)]">Folie {si + 1}</p>
                            {plan.brief && (
                              <p className="text-sm text-[var(--text-secondary)] mt-0.5 line-clamp-2">{plan.brief}</p>
                            )}
                            {slideErrors[errKey] && (
                              <p className="text-xs text-[var(--error)] mt-1">{slideErrors[errKey]}</p>
                            )}
                          </div>
                          <button
                            onClick={() => handleGenerateSingle(chIdx, si)}
                            disabled={isGenerating}
                            className="shrink-0 px-4 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white text-xs font-semibold transition-colors disabled:opacity-40"
                          >
                            Generieren
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Group generated slides by chapter_index using chapter_id mapping.
 * Each slide has a chapter_id; each chapter has id + chapter_index.
 */
function groupSlidesByChapter(slides: Slide[], chapters: Chapter[]): Record<number, Slide[]> {
  // Build chapter_id → chapter_index lookup
  const idToIndex: Record<string, number> = {};
  for (const ch of chapters) {
    idToIndex[ch.id] = ch.chapter_index;
  }

  const result: Record<number, Slide[]> = {};
  for (const slide of slides) {
    const chIdx = idToIndex[slide.chapter_id];
    if (chIdx === undefined) continue;
    if (!result[chIdx]) result[chIdx] = [];
    result[chIdx].push(slide);
  }

  // Sort each chapter's slides by slide_index_in_chapter
  for (const key of Object.keys(result)) {
    result[Number(key)].sort((a, b) => a.slide_index_in_chapter - b.slide_index_in_chapter);
  }

  return result;
}
