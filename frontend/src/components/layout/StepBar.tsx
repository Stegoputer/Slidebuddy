"use client";

import Link from "next/link";
import { useProgress } from "@/hooks/useProgress";

const STEPS = [
  { key: "sources", label: "Quellen", path: "" },
  { key: "chapters", label: "Kapitelplanung", path: "/chapters" },
  { key: "sections", label: "Sektionsplanung", path: "/sections" },
  { key: "generation", label: "Generierung", path: "/generation" },
  { key: "review", label: "Review", path: "/review" },
];

interface StepBarProps {
  projectId: string;
  currentStep: string;
}

export function StepBar({ projectId, currentStep }: StepBarProps) {
  const { data: progress } = useProgress(projectId);
  // Backend has 4 steps (0-3), frontend has 5 (0-4 with review).
  // Review is accessible whenever generation is reached (step_index 3).
  const backendMax = progress?.step_index ?? 0;
  const maxIndex = backendMax >= 3 ? 4 : backendMax;
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="mb-8">
      {/* Circle + Line indicator */}
      <div className="flex items-center justify-between mb-4">
        {STEPS.map((step, i) => {
          const isDone = i < currentIndex;
          const isActive = i === currentIndex;
          const isAccessible = i <= maxIndex;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                    isActive
                      ? "bg-gradient-to-br from-[var(--accent)] to-[var(--accent-light)] text-white shadow-[0_0_16px_var(--accent-glow)]"
                      : isDone
                        ? "bg-[var(--success)] text-white"
                        : isAccessible
                          ? "bg-[var(--bg-card)] border-2 border-[var(--accent)] text-[var(--accent)]"
                          : "bg-[var(--bg-card)] border-2 border-[var(--border-subtle)] text-[var(--text-secondary)]"
                  }`}
                >
                  {isDone ? "✓" : i + 1}
                </div>
                <span
                  className={`text-xs font-medium whitespace-nowrap ${
                    isActive ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 mb-5 rounded ${
                    isDone ? "bg-gradient-to-r from-[var(--success)] to-[var(--accent)]" : "bg-[var(--border-subtle)]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Navigation buttons */}
      <div className="grid grid-cols-5 gap-2">
        {STEPS.map((step, i) => {
          const isAccessible = i <= maxIndex;
          const isActive = i === currentIndex;
          return isAccessible ? (
            <Link
              key={step.key}
              href={`/projects/${projectId}${step.path}`}
              className={`py-2.5 px-3 rounded-lg text-center text-sm font-semibold transition-all ${
                isActive
                  ? "bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] text-white shadow-lg"
                  : "bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-white border border-[var(--border-subtle)]"
              }`}
            >
              {step.label}
            </Link>
          ) : (
            <span
              key={step.key}
              className="py-2.5 px-3 rounded-lg text-center text-sm font-semibold bg-[var(--bg-card)] text-[var(--text-secondary)] opacity-40 cursor-not-allowed border border-[var(--border-subtle)]"
            >
              {step.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
