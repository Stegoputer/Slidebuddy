"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Chunk {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
  char_count: number;
  token_estimate: number;
}

export function useChunks(projectId: string, sourceId: string | null, search: string = "") {
  return useQuery<Chunk[]>({
    queryKey: ["chunks", projectId, sourceId, search],
    queryFn: () => {
      const params = search ? `?search=${encodeURIComponent(search)}` : "";
      return api.get(`/projects/${projectId}/sources/${sourceId}/chunks${params}`);
    },
    enabled: !!projectId && !!sourceId,
  });
}
