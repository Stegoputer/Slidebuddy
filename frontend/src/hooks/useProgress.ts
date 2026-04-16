"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Progress } from "@/lib/types";

export function useProgress(projectId: string) {
  return useQuery<Progress>({
    queryKey: ["progress", projectId],
    queryFn: () => api.get(`/projects/${projectId}/progress`),
    enabled: !!projectId,
  });
}
