"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Master {
  id: string;
  name: string;
  filename: string;
  is_active: boolean;
  created_at: string;
}

interface MasterTemplate {
  id: string;
  master_id: string;
  layout_index: number;
  layout_name: string;
  template_key: string;
  display_name: string;
  description: string;
  placeholder_schema: string | null;
  content_schema: string | null;
  generation_prompt: string | null;
  is_active: boolean;
}

export function useMasters() {
  return useQuery<Master[]>({
    queryKey: ["masters"],
    queryFn: () => api.get("/masters"),
  });
}

export function useUploadMaster() {
  const qc = useQueryClient();
  return useMutation<Master, Error, File>({
    mutationFn: async (file) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/masters", { method: "POST", body: form });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["masters"] });
      qc.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}

export function useActivateMaster() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (masterId) => api.put(`/masters/${masterId}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["masters"] });
      qc.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}

export function useDeleteMaster() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (masterId) => api.delete(`/masters/${masterId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["masters"] });
      qc.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}

export function useMasterTemplates(masterId: string | null) {
  return useQuery<MasterTemplate[]>({
    queryKey: ["masters", masterId, "templates"],
    queryFn: () => api.get(`/masters/${masterId}/templates`),
    enabled: !!masterId,
  });
}

export function useUpdateMasterTemplate() {
  const qc = useQueryClient();
  return useMutation<MasterTemplate, Error, { masterId: string; templateId: string; data: Partial<MasterTemplate> }>({
    mutationFn: ({ masterId, templateId, data }) =>
      api.put(`/masters/${masterId}/templates/${templateId}`, data),
    onSuccess: (_, { masterId }) => {
      qc.invalidateQueries({ queryKey: ["masters", masterId, "templates"] });
    },
  });
}
