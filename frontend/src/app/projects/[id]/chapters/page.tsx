"use client";

import { use, useEffect, useState } from "react";
import { ProjectLoader } from "@/components/ProjectLoader";
import { PlanPromptModal, buildFeedbackString } from "@/components/PlanPromptModal";
import { useChapters, usePlanChapters, useApproveChapters, useUpdateChapters, useSourceGaps, type PlanInput } from "@/hooks/useChapters";
import { useSources } from "@/hooks/useSources";
import { useNavigationGuard } from "@/hooks/useNavigationGuard";
import { StepBar } from "@/components/layout/StepBar";
import Link from "next/link";
import type { Chapter, SourceGap } from "@/lib/types";

const STRATEGY_LABELS: Record<string, string> = {
  auto: "KI-Kapitelplanung",
  one_per_source: "Je Quelle ein Kapitel",
  full_source_split: "Quellen aufteilen",
};

const CHAPTER_STATUS: Record<string, string> = { planned: "Geplant", approved: "Freigegeben" };

export default function ChaptersPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProjectLoader projectId={id}>
      {(project) => <ChaptersContent projectId={id} projectName={project.name} />}
    </ProjectLoader>
  );
}

function ChaptersContent({ projectId, projectName }: { projectId: string; projectName: string }) {
  const { data: chapters, isLoading, error } = useChapters(projectId);
  const { data: sources } = useSources(projectId);
  const { data: sourceGaps } = useSourceGaps(projectId);
  const planMutation = usePlanChapters(projectId);
  const approveMutation = useApproveChapters(projectId);
  const updateMutation = useUpdateChapters(projectId);

  const [editedChapters, setEditedChapters] = useState<Chapter[] | null>(null);
  const [hasEdits, setHasEdits] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [confirmReplan, setConfirmReplan] = useState(false);
  const [deleteConfirmIdx, setDeleteConfirmIdx] = useState<number | null>(null);
  const [pendingStrategy, setPendingStrategy] = useState<string | null>(null);

  // Warn before navigating away during active operations
  useNavigationGuard(
    planMutation.isPending || approveMutation.isPending || updateMutation.isPending,
    "Kapitelplanung läuft noch. Wirklich verlassen?"
  );

  // Sync editedChapters from server data
  useEffect(() => {
    if (chapters && chapters.length > 0) {
      setEditedChapters(chapters);
      setHasEdits(false);
      setDeleteConfirmIdx(null);
    } else {
      setEditedChapters(null);
    }
  }, [chapters]);

  const hasChapters = editedChapters && editedChapters.length > 0;
  const hasSources = sources && sources.length > 0;
  const allApproved = chapters?.every((c) => c.status === "approved");
  const totalSlides = editedChapters?.reduce((s, c) => s + c.estimated_slide_count, 0) ?? 0;

  // ── Edit helpers ──────────────────────────────────────────────────

  const updateField = (idx: number, field: keyof Chapter, value: string | number) => {
    setEditedChapters((prev) =>
      prev!.map((c, i) => (i === idx ? { ...c, [field]: value } : c))
    );
    setHasEdits(true);
  };

  const adjustSlideCount = (idx: number, delta: number) => {
    setEditedChapters((prev) =>
      prev!.map((c, i) =>
        i === idx
          ? { ...c, estimated_slide_count: Math.max(1, c.estimated_slide_count + delta) }
          : c
      )
    );
    setHasEdits(true);
  };

  const removeChapter = (idx: number) => {
    setEditedChapters((prev) => prev!.filter((_, i) => i !== idx));
    setDeleteConfirmIdx(null);
    setHasEdits(true);
  };

  const addChapter = () => {
    setEditedChapters((prev) => [
      ...(prev ?? []),
      {
        id: crypto.randomUUID(),
        project_id: projectId,
        chapter_index: prev?.length ?? 0,
        title: "",
        summary: "",
        estimated_slide_count: 3,
        status: "planned",
      },
    ]);
    setHasEdits(true);
  };

  const handleSave = () => {
    if (!editedChapters) return;
    updateMutation.mutate(editedChapters, {
      onSuccess: () => setHasEdits(false),
    });
  };

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Kapitelplanung — {projectName}</h1>
      <StepBar projectId={projectId} currentStep="chapters" />

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Kapitel laden...</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/5 p-4">
          <p className="text-[var(--error)] text-sm">Fehler beim Laden der Kapitel: {error.message}</p>
        </div>
      )}

      {/* No sources */}
      {!isLoading && !error && !hasSources && !hasChapters && (
        <div className="rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/5 p-4">
          <p className="text-[var(--warning)] text-sm">Bitte zuerst Quellen hochladen, bevor Kapitel geplant werden können.</p>
        </div>
      )}

      {/* Initial plan buttons — three strategies (each opens prompt modal) */}
      {!hasChapters && !planMutation.isPending && hasSources && !isLoading && !error && (
        <div className="flex flex-col gap-3">
          <div className="flex gap-3">
            <button
              onClick={() => setPendingStrategy("auto")}
              className="flex-1 py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors"
            >
              KI-Kapitelplanung
            </button>
            <button
              onClick={() => setPendingStrategy("one_per_source")}
              className="flex-1 py-3 rounded-xl border border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-white font-semibold transition-colors"
            >
              Je Quelle ein Kapitel
            </button>
          </div>
          <button
            onClick={() => setPendingStrategy("full_source_split")}
            className="w-full py-3 rounded-xl border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] font-semibold transition-colors"
            title="Lange Quellen (z.B. Video-Transkripte) werden automatisch in mehrere Kapitel aufgeteilt"
          >
            Quellen aufteilen
          </button>
        </div>
      )}

      {/* Planning spinner */}
      {planMutation.isPending && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Kapitel werden geplant...</span>
        </div>
      )}

      {/* Planning error */}
      {planMutation.isError && (
        <div className="rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/5 p-4">
          <p className="text-[var(--error)] text-sm">Fehler: {planMutation.error.message}</p>
        </div>
      )}

      {/* Chapter list */}
      {hasChapters && (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Kapitelstruktur</h2>
            <span className="text-xs text-[var(--text-secondary)]">
              {editedChapters.length} Kapitel · {totalSlides} Folien gesamt
            </span>
          </div>

          {/* Source gap analysis */}
          {sourceGaps && sourceGaps.length > 0 && (
            <div className="rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/5 p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                Quellen-Luckenanalyse
                <span className="text-xs font-normal text-[var(--text-secondary)]">
                  {sourceGaps.length} {sourceGaps.length === 1 ? "Lucke" : "Lucken"} erkannt
                </span>
              </h3>
              <div className="space-y-2">
                {sourceGaps.map((gap) => {
                  const severityConfig = {
                    high:   { icon: "\u{1F534}", label: "Hoch",   color: "text-[var(--error)]" },
                    medium: { icon: "\u{1F7E1}", label: "Mittel", color: "text-[var(--warning)]" },
                    low:    { icon: "\u{1F7E2}", label: "Niedrig", color: "text-[var(--success)]" },
                  }[gap.severity] ?? { icon: "\u{1F7E1}", label: gap.severity, color: "text-[var(--warning)]" };

                  const linkedChapter = editedChapters.find((c) => c.id === gap.chapter_id);

                  return (
                    <div key={gap.id} className="flex items-start gap-2 text-sm">
                      <span className="shrink-0">{severityConfig.icon}</span>
                      <div className="min-w-0">
                        {linkedChapter && (
                          <span className="font-medium text-[var(--text-primary)]">
                            {linkedChapter.title}:{" "}
                          </span>
                        )}
                        <span className="text-[var(--text-secondary)]">{gap.description}</span>
                      </div>
                      <span className={`shrink-0 text-xs ${severityConfig.color}`}>
                        {severityConfig.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Editable chapter cards */}
          {editedChapters.map((ch, i) => (
            <div key={ch.id} className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-5 space-y-3">
              {/* Header row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-[var(--accent-light)]">Kapitel {i + 1}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      ch.status === "approved"
                        ? "bg-[var(--success)]/20 text-[var(--success)]"
                        : "bg-[var(--warning)]/20 text-[var(--warning)]"
                    }`}
                  >
                    {CHAPTER_STATUS[ch.status] ?? ch.status}
                  </span>
                </div>

                {/* Delete button */}
                {deleteConfirmIdx === i ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => removeChapter(i)}
                      className="px-3 py-1 rounded-lg bg-[var(--error)] text-white text-xs font-semibold"
                    >
                      Löschen
                    </button>
                    <button
                      onClick={() => setDeleteConfirmIdx(null)}
                      className="px-3 py-1 rounded-lg border border-[var(--border-subtle)] text-xs hover:bg-[var(--bg-hover)]"
                    >
                      Nein
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteConfirmIdx(i)}
                    className="text-[var(--text-secondary)] hover:text-[var(--error)] transition px-2"
                    title="Kapitel löschen"
                  >
                    🗑️
                  </button>
                )}
              </div>

              {/* Title */}
              <input
                value={ch.title}
                onChange={(e) => updateField(i, "title", e.target.value)}
                placeholder="Kapiteltitel"
                className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm font-semibold focus:border-[var(--accent)] focus:outline-none"
              />

              {/* Summary */}
              <textarea
                value={ch.summary}
                onChange={(e) => updateField(i, "summary", e.target.value)}
                placeholder="Zusammenfassung / Beschreibung"
                rows={2}
                className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none resize-y"
              />

              {/* Slide count */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-[var(--text-secondary)]">Folienanzahl:</span>
                <button
                  onClick={() => adjustSlideCount(i, -1)}
                  disabled={ch.estimated_slide_count <= 1}
                  className="w-7 h-7 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm font-bold disabled:opacity-30 transition-colors flex items-center justify-center"
                >
                  −
                </button>
                <span className="font-mono text-sm w-6 text-center">{ch.estimated_slide_count}</span>
                <button
                  onClick={() => adjustSlideCount(i, +1)}
                  className="w-7 h-7 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm font-bold transition-colors flex items-center justify-center"
                >
                  +
                </button>
              </div>
            </div>
          ))}

          {/* Add chapter */}
          <button
            onClick={addChapter}
            className="w-full py-3 rounded-xl border-2 border-dashed border-[var(--border-subtle)] hover:border-[var(--accent)] text-[var(--text-secondary)] hover:text-[var(--accent-light)] transition-colors text-sm font-medium"
          >
            + Kapitel hinzufügen
          </button>

          {/* LLM feedback */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 space-y-3">
            <p className="text-sm font-medium">Per KI anpassen</p>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="z.B. 'Füge ein Kapitel über Nachhaltigkeit hinzu' oder 'Reduziere auf 4 Kapitel'"
              rows={2}
              className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm resize-y placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
            />
            <button
              onClick={() => {
                planMutation.mutate({ feedback: feedback.trim() });
                setFeedback("");
              }}
              disabled={planMutation.isPending || !feedback.trim()}
              className="w-full py-2 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors disabled:opacity-50"
            >
              {planMutation.isPending ? "Wird angepasst..." : "Per KI anpassen"}
            </button>
          </div>

          {/* Save edits */}
          {hasEdits && (
            <button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="w-full py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors disabled:opacity-50"
            >
              {updateMutation.isPending ? "Wird gespeichert..." : "Änderungen speichern"}
            </button>
          )}

          {updateMutation.isError && (
            <p className="text-[var(--error)] text-sm">Fehler beim Speichern: {updateMutation.error.message}</p>
          )}

          {/* CTA after approve */}
          {allApproved && (
            <Link
              href={`/projects/${projectId}/sections`}
              className="block w-full py-3 rounded-xl bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] text-white font-semibold text-center hover:opacity-90 transition"
            >
              Weiter zur Sektionsplanung →
            </Link>
          )}

          {/* Approve / Replan buttons */}
          <div className="flex gap-3">
            {!allApproved && (
              <button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending || hasEdits}
                className="flex-1 py-3 rounded-xl bg-[var(--success)] hover:brightness-110 text-white font-semibold transition-all disabled:opacity-50"
                title={hasEdits ? "Bitte zuerst Änderungen speichern" : undefined}
              >
                {approveMutation.isPending ? "Wird freigegeben..." : "Kapitel freigeben"}
              </button>
            )}

            {!confirmReplan ? (
              <button
                onClick={() => setConfirmReplan(true)}
                className="px-6 py-3 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors"
              >
                Komplett neu planen
              </button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => { setPendingStrategy("auto"); setConfirmReplan(false); }}
                  className="px-5 py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors"
                >
                  KI-Neuplanung
                </button>
                <button
                  onClick={() => { setPendingStrategy("one_per_source"); setConfirmReplan(false); }}
                  className="px-5 py-3 rounded-xl border border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-white font-semibold transition-colors"
                >
                  Je Quelle ein Kapitel
                </button>
                <button
                  onClick={() => { setPendingStrategy("full_source_split"); setConfirmReplan(false); }}
                  className="px-5 py-3 rounded-xl border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] font-semibold transition-colors"
                  title="Lange Quellen automatisch in mehrere Kapitel aufteilen"
                >
                  Quellen aufteilen
                </button>
                <button
                  onClick={() => setConfirmReplan(false)}
                  className="px-5 py-3 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] transition-colors"
                >
                  Abbrechen
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Plan prompt modal */}
      {pendingStrategy && (
        <PlanPromptModal
          strategyLabel={STRATEGY_LABELS[pendingStrategy] ?? pendingStrategy}
          onCancel={() => setPendingStrategy(null)}
          onSubmit={(result) => {
            const feedbackStr = buildFeedbackString(result);
            planMutation.mutate({
              strategy: pendingStrategy as PlanInput["strategy"],
              feedback: feedbackStr,
            });
            setPendingStrategy(null);
          }}
        />
      )}
    </div>
  );
}
