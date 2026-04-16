"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SectionPlan, SlidePlan } from "@/lib/types";

export function useSections(projectId: string) {
  return useQuery<SectionPlan[]>({
    queryKey: ["sections", projectId],
    queryFn: () => api.get(`/projects/${projectId}/sections`),
  });
}

export function usePlanSections(projectId: string) {
  const qc = useQueryClient();
  return useMutation<SectionPlan[], Error>({
    mutationFn: () => api.post(`/projects/${projectId}/sections/plan`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sections", projectId] });
      qc.invalidateQueries({ queryKey: ["progress", projectId] });
    },
  });
}


export function useUpdateSectionChapter(projectId: string) {
  const qc = useQueryClient();
  return useMutation<SectionPlan, Error, { chapterIndex: number; slides: SlidePlan[] }>({
    mutationFn: ({ chapterIndex, slides }) =>
      api.put(`/projects/${projectId}/sections/${chapterIndex}`, { slides }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sections", projectId] }),
  });
}

export function useDeleteSections(projectId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: () => api.delete(`/projects/${projectId}/sections`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sections", projectId] });
      qc.invalidateQueries({ queryKey: ["progress", projectId] });
    },
  });
}
