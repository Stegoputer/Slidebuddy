"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Source } from "@/lib/types";

export function useSources(projectId: string) {
  return useQuery<Source[]>({
    queryKey: ["sources", projectId],
    queryFn: () => api.get(`/projects/${projectId}/sources`),
    enabled: !!projectId,
  });
}

export function useUploadSources(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => api.upload<Source[]>(`/projects/${projectId}/sources/upload`, files),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources", projectId] }),
  });
}

export function useAddYoutube(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => api.post<Source>(`/projects/${projectId}/sources/youtube`, { url }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources", projectId] }),
  });
}

export function useDeleteSource(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => api.delete(`/projects/${projectId}/sources/${sourceId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources", projectId] }),
  });
}
