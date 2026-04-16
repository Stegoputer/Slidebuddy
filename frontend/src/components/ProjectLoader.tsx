"use client";

import { useProject } from "@/hooks/useProjects";
import type { Project } from "@/lib/types";

interface Props {
  projectId: string;
  children: (project: Project) => React.ReactNode;
}

/**
 * Shared loading/error wrapper for all project pages.
 * Renders a spinner while loading, an error message on failure,
 * and calls children(project) once data is available.
 */
export function ProjectLoader({ projectId, children }: Props) {
  const { data: project, isLoading, error } = useProject(projectId);

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto flex items-center gap-3 py-12">
        <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
        <span className="text-[var(--text-secondary)]">Projekt wird geladen...</span>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="max-w-5xl mx-auto py-12">
        <p className="text-[var(--error)]">Projekt konnte nicht geladen werden.</p>
        {error && <p className="text-sm text-[var(--text-secondary)] mt-2">{error.message}</p>}
      </div>
    );
  }

  return <>{children(project)}</>;
}
