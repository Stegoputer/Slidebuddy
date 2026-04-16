"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Chapter, SourceGap } from "@/lib/types";

/** Input for chapter planning — supports both LLM and deterministic strategies. */
export interface PlanInput {
  feedback?: string;
  strategy?: "auto" | "one_per_source" | "full_source_split";
}

export function useChapters(projectId: string) {
  return useQuery<Chapter[]>({
    queryKey: ["chapters", projectId],
    queryFn: () => api.get(`/projects/${projectId}/chapters`),
  });
}

export function useSourceGaps(projectId: string) {
  return useQuery<SourceGap[]>({
    queryKey: ["source-gaps", projectId],
    queryFn: () => api.get(`/projects/${projectId}/chapters/gaps`),
  });
}

export function usePlanChapters(projectId: string) {
  const qc = useQueryClient();
  return useMutation<Chapter[], Error, PlanInput | undefined>({
    mutationFn: (input?: PlanInput) =>
      api.post(
        `/projects/${projectId}/chapters/plan`,
        input?.feedback || input?.strategy
          ? { feedback: input.feedback, strategy: input.strategy }
          : undefined,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chapters", projectId] });
      qc.invalidateQueries({ queryKey: ["source-gaps", projectId] });
      qc.invalidateQueries({ queryKey: ["progress", projectId] });
    },
  });
}

export function useApproveChapters(projectId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: () => api.post(`/projects/${projectId}/chapters/approve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chapters", projectId] });
      qc.invalidateQueries({ queryKey: ["progress", projectId] });
    },
  });
}

export function useUpdateChapters(projectId: string) {
  const qc = useQueryClient();
  return useMutation<Chapter[], Error, Chapter[]>({
    mutationFn: (chapters) => api.put(`/projects/${projectId}/chapters`, { chapters }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chapters", projectId] }),
  });
}
