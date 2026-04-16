"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSettings() {
  return useQuery<{ preferences: Record<string, unknown>; api_keys_configured: Record<string, boolean> }>({
    queryKey: ["settings"],
    queryFn: () => api.get("/settings"),
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation<void, Error, Record<string, unknown>>({
    mutationFn: (prefs) => api.put("/settings", { preferences: prefs }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export function useApiKeys() {
  return useQuery<Record<string, boolean>>({
    queryKey: ["settings", "api-keys"],
    queryFn: () => api.get("/settings/api-keys"),
  });
}

export function useSetApiKey() {
  const qc = useQueryClient();
  return useMutation<void, Error, { provider: string; key: string }>({
    mutationFn: ({ provider, key }) => api.put(`/settings/api-keys/${provider}`, { key }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["models"] });
    },
  });
}

export function useDeleteApiKey() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (provider) => api.delete(`/settings/api-keys/${provider}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["models"] });
    },
  });
}

export function useModels() {
  return useQuery<Record<string, string[]>>({
    queryKey: ["models"],
    queryFn: () => api.get("/settings/models"),
  });
}

export function usePromptPhases() {
  return useQuery<{
    groups: Record<string, string[]>;
    labels: Record<string, string>;
    defaults: Record<string, string>;
    custom_prompts: Record<string, { phase: string; text: string }>;
    active_prompts: Record<string, string>;
  }>({
    queryKey: ["prompts"],
    queryFn: () => api.get("/settings/prompts/phases"),
  });
}

export function useSaveCustomPrompt() {
  const qc = useQueryClient();
  return useMutation<void, Error, { name: string; phase: string; text: string }>({
    mutationFn: (body) => api.post("/settings/prompts/custom", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useDeleteCustomPrompt() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (name) => api.delete(`/settings/prompts/custom/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useSetActivePrompt() {
  const qc = useQueryClient();
  return useMutation<void, Error, { phase: string; source: string }>({
    mutationFn: ({ phase, source }) => api.put(`/settings/prompts/active/${phase}`, { source }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useDebugSummary() {
  return useQuery<{
    total_calls: number;
    total_input_tokens?: number;
    total_output_tokens?: number;
    total_duration_s?: number;
    by_phase?: Record<string, { calls: number; input_tokens: number; output_tokens: number; duration_s: number }>;
  }>({
    queryKey: ["debug-summary"],
    queryFn: () => api.get("/settings/debug/summary"),
  });
}

export function useClearDebugLog() {
  const qc = useQueryClient();
  return useMutation<void, Error>({
    mutationFn: () => api.delete("/settings/debug/log"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["debug-summary"] }),
  });
}

export function useTemplates() {
  return useQuery<{ types: string[]; labels: Record<string, string> }>({
    queryKey: ["templates"],
    queryFn: () => api.get("/settings/templates"),
  });
}

export function useConstants() {
  return useQuery<{
    languages: string[];
    text_lengths: string[];
    language_labels: Record<string, string>;
    text_length_labels: Record<string, string>;
  }>({
    queryKey: ["constants"],
    queryFn: () => api.get("/settings/constants"),
  });
}

export function useMigrateCosine() {
  return useMutation<{ migrated: number }, Error>({
    mutationFn: () => api.post("/settings/rag/migrate-cosine"),
  });
}
