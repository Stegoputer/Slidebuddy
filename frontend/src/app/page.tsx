"use client";

import { useState } from "react";
import { useProjects, useCreateProject, useDeleteProject } from "@/hooks/useProjects";
import { useConstants } from "@/hooks/useSettings";
import { useProgress } from "@/hooks/useProgress";
import Link from "next/link";
import type { Project } from "@/lib/types";

const STEP_PATHS: Record<string, string> = {
  sources: "",
  chapters: "/chapters",
  sections: "/sections",
  generation: "/generation",
  review: "/review",
};

const STEP_LABELS: Record<string, string> = {
  sources: "Quellen",
  chapters: "Kapitelplanung",
  sections: "Sektionsplanung",
  generation: "Generierung",
  review: "Review",
};

const LENGTH_LABEL: Record<string, string> = { short: "Kurz", medium: "Mittel", long: "Ausführlich" };

export default function Home() {
  const { data: projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const { data: constants } = useConstants();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [language, setLanguage] = useState("de");
  const [textLength, setTextLength] = useState("medium");

  const languages = constants?.languages ?? ["de", "en"];
  const langLabels = constants?.language_labels ?? { de: "Deutsch", en: "English" };
  const textLengths = constants?.text_lengths ?? ["short", "medium", "long"];
  const lengthLabels = constants?.text_length_labels ?? LENGTH_LABEL;

  const handleCreate = () => {
    if (!name.trim()) return;
    createProject.mutate({ name: name.trim(), topic: topic.trim(), language, global_text_length: textLength }, {
      onSuccess: () => { setShowForm(false); setName(""); setTopic(""); setLanguage("de"); setTextLength("medium"); },
    });
  };

  if (isLoading) {
    return <div className="text-[var(--text-secondary)]">Projekte laden...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Projekte</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] text-white font-semibold hover:opacity-90 transition"
        >
          + Neues Projekt
        </button>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Neues Projekt erstellen</h2>
          <div className="space-y-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Projektname"
              className="w-full px-4 py-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-white placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
              autoFocus
            />
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Thema / Beschreibung (optional)"
              className="w-full px-4 py-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-white placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1.5">Sprache</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-white focus:border-[var(--accent)] focus:outline-none"
                >
                  {languages.map((l: string) => (
                    <option key={l} value={l}>{langLabels[l] ?? l.toUpperCase()}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--text-secondary)] mb-1.5">Textlänge (Standard)</label>
                <select
                  value={textLength}
                  onChange={(e) => setTextLength(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-white focus:border-[var(--accent)] focus:outline-none"
                >
                  {textLengths.map((tl: string) => (
                    <option key={tl} value={tl}>{lengthLabels[tl] ?? tl}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={createProject.isPending || !name.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white font-semibold disabled:opacity-50"
              >
                {createProject.isPending ? "Erstelle..." : "Erstellen"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-lg bg-[var(--bg-hover)] text-[var(--text-secondary)]"
              >
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Project List */}
      <div className="grid gap-3">
        {projects?.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}

        {!projects?.length && (
          <p className="text-[var(--text-secondary)] text-center py-12">
            Noch keine Projekte. Erstelle dein erstes Projekt!
          </p>
        )}
      </div>
    </div>
  );
}

function ProjectCard({ project: p }: { project: Project }) {
  const deleteProject = useDeleteProject();
  const { data: progress } = useProgress(p.id);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // Navigate directly to project's current step
  const currentStep = progress?.current_step ?? "sources";
  const stepPath = STEP_PATHS[currentStep] ?? "";
  const href = `/projects/${p.id}${stepPath}`;
  const stepLabel = STEP_LABELS[currentStep] ?? currentStep;

  return (
    <Link
      href={href}
      className="block bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl p-5 hover:border-[var(--accent)] transition group"
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold group-hover:text-[var(--accent-light)] transition">
            {p.name}
          </h3>
          {p.topic && (
            <p className="text-sm text-[var(--text-secondary)] mt-1">{p.topic}</p>
          )}
          <p className="text-xs text-[var(--text-secondary)] mt-2">
            {new Date(p.created_at).toLocaleDateString("de-DE")} · {p.language.toUpperCase()} · {LENGTH_LABEL[p.global_text_length] ?? p.global_text_length}
            {progress && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-[var(--accent)]/15 text-[var(--accent-light)]">
                {stepLabel}
              </span>
            )}
          </p>
        </div>

        {deleteConfirm ? (
          <div className="flex gap-2" onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); deleteProject.mutate(p.id); setDeleteConfirm(false); }}
              className="px-3 py-1 rounded-lg bg-[var(--error)] text-white text-sm"
            >
              Löschen
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDeleteConfirm(false); }}
              className="px-3 py-1 rounded-lg bg-[var(--bg-hover)] text-sm"
            >
              Nein
            </button>
          </div>
        ) : (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDeleteConfirm(true); }}
            className="shrink-0 px-3 py-1 rounded-lg text-sm text-[var(--text-secondary)] hover:text-[var(--error)] hover:bg-[var(--bg-hover)] transition"
            title="Projekt löschen"
          >
            🗑️
          </button>
        )}
      </div>
    </Link>
  );
}
