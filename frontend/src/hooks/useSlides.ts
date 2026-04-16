"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Slide } from "@/lib/types";

export function useSlides(projectId: string) {
  return useQuery<Slide[]>({
    queryKey: ["slides", projectId],
    queryFn: () => api.get(`/projects/${projectId}/slides`),
  });
}

export function useDraftSlides(projectId: string) {
  return useQuery<Slide[]>({
    queryKey: ["slides", projectId, "drafts"],
    queryFn: () => api.get(`/projects/${projectId}/slides/drafts`),
  });
}

export function useGenerateSingle(projectId: string) {
  const qc = useQueryClient();
  return useMutation<{ status: string; slide?: Slide }, Error, { chapterIndex: number; slideIndex: number; textLength?: string }>({
    mutationFn: ({ chapterIndex, slideIndex, textLength }) =>
      api.post(`/projects/${projectId}/generate/single`, {
        chapter_index: chapterIndex,
        slide_index_in_chapter: slideIndex,
        text_length: textLength,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["slides", projectId] });
      qc.invalidateQueries({ queryKey: ["progress", projectId] });
    },
  });
}

export function useGenerateChapter(projectId: string) {
  const qc = useQueryClient();
  return useMutation<{ status: string; total: number }, Error, { chapterIndex: number; textLength: string; batchSize: number }>({
    mutationFn: ({ chapterIndex, textLength, batchSize }) =>
      api.post(`/projects/${projectId}/generate/chapter`, {
        chapter_index: chapterIndex,
        text_length: textLength,
        batch_size: batchSize,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["slides", projectId] });
      qc.invalidateQueries({ queryKey: ["progress", projectId] });
    },
  });
}

export function useUpdateSlide(projectId: string) {
  const qc = useQueryClient();
  return useMutation<Slide, Error, { slideId: string; data: Partial<Slide> }>({
    mutationFn: ({ slideId, data }) =>
      api.put(`/projects/${projectId}/slides/${slideId}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["slides", projectId] }),
  });
}
