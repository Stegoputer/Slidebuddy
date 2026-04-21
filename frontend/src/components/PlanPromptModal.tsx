"use client";

import { useState } from "react";

export interface PlanPromptResult {
  goal: string;
  audience?: string;
  slideCount?: number;
  focus?: string;
}

interface PlanPromptModalProps {
  strategyLabel: string;
  initialValues?: Partial<PlanPromptResult>;
  onSubmit: (result: PlanPromptResult) => void;
  onCancel: () => void;
}

/**
 * Build a structured feedback string from the prompt fields.
 * This gets sent as `feedback` to the chapter planning API.
 */
export function buildFeedbackString(result: PlanPromptResult): string {
  const parts: string[] = [];
  parts.push(`ZIEL: ${result.goal}`);
  if (result.audience?.trim()) {
    parts.push(`ZIELGRUPPE: ${result.audience.trim()}`);
  }
  if (result.slideCount && result.slideCount > 0) {
    parts.push(`GEWÜNSCHTE FOLIENANZAHL: ${result.slideCount}`);
  }
  if (result.focus?.trim()) {
    parts.push(`SCHWERPUNKTE: ${result.focus.trim()}`);
  }
  return parts.join("\n");
}

export function PlanPromptModal({ strategyLabel, initialValues, onSubmit, onCancel }: PlanPromptModalProps) {
  const [goal, setGoal] = useState(initialValues?.goal ?? "");
  const [audience, setAudience] = useState(initialValues?.audience ?? "");
  const [slideCount, setSlideCount] = useState<number | "">(initialValues?.slideCount ?? "");
  const [focus, setFocus] = useState(initialValues?.focus ?? "");
  const [showAdvanced, setShowAdvanced] = useState(
    !!(initialValues?.audience || initialValues?.slideCount || initialValues?.focus)
  );

  const canSubmit = goal.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit({
      goal: goal.trim(),
      audience: audience || undefined,
      slideCount: typeof slideCount === "number" ? slideCount : undefined,
      focus: focus || undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg mx-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-2">
          <h2 className="text-lg font-bold text-[var(--text-primary)]">
            Planungsziel beschreiben
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Strategie: <span className="font-medium text-[var(--accent)]">{strategyLabel}</span>
          </p>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          {/* Goal (required) */}
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
              Was möchtest du mit der Präsentation erreichen? *
            </label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="z.B. Die Kernaussagen einer Studie verständlich auf Slides bringen..."
              rows={3}
              className="w-full rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-page)] px-4 py-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40 resize-none"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && canSubmit) {
                  handleSubmit();
                }
              }}
            />
          </div>

          {/* Advanced options toggle */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-[var(--accent)] hover:underline flex items-center gap-1"
          >
            <span className="text-xs">{showAdvanced ? "▾" : "▸"}</span>
            Erweiterte Optionen
          </button>

          {/* Advanced fields */}
          {showAdvanced && (
            <div className="space-y-3 pl-2 border-l-2 border-[var(--accent)]/20">
              {/* Audience */}
              <div>
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                  Zielgruppe
                </label>
                <input
                  type="text"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="z.B. Studierende, Management, Fachpublikum..."
                  className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                />
              </div>

              {/* Slide count */}
              <div>
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                  Gewünschte Folienanzahl (gesamt)
                </label>
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={slideCount}
                  onChange={(e) => setSlideCount(e.target.value ? parseInt(e.target.value) : "")}
                  placeholder="z.B. 15"
                  className="w-32 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                />
              </div>

              {/* Focus */}
              <div>
                <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                  Schwerpunkte / Fokus
                </label>
                <input
                  type="text"
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                  placeholder="z.B. Nur Methodik und Ergebnisse, weniger Einleitung..."
                  className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 pt-2 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-5 py-2.5 rounded-xl border border-[var(--border-subtle)] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="px-5 py-2.5 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Planung starten
          </button>
        </div>
      </div>
    </div>
  );
}
