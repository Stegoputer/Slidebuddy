"use client";

import { useRef, useState } from "react";
import {
  useMasters,
  useUploadMaster,
  useActivateMaster,
  useDeleteMaster,
  useMasterTemplates,
} from "@/hooks/useMasters";

export default function MastersPage() {
  const { data: masters, isLoading } = useMasters();
  const uploadMaster = useUploadMaster();
  const activateMaster = useActivateMaster();
  const deleteMaster = useDeleteMaster();
  const fileRef = useRef<HTMLInputElement>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const activeMaster = masters?.find((m) => m.is_active);

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadMaster.mutate(file);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">PowerPoint Master</h1>
      <p className="text-sm text-[var(--text-secondary)]">
        Lade eine PPTX-Vorlage hoch. Die Layouts werden automatisch analysiert und als Templates verwendet.
      </p>

      {/* Upload */}
      <div className="flex gap-3">
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploadMaster.isPending}
          className="px-6 py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors disabled:opacity-50"
        >
          {uploadMaster.isPending ? "Wird analysiert..." : "PPTX hochladen"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".pptx"
          className="hidden"
          onChange={handleUpload}
        />
      </div>

      {uploadMaster.isError && (
        <p className="text-sm text-[var(--error)]">Fehler: {uploadMaster.error.message}</p>
      )}

      {/* Active Master Info */}
      {activeMaster && (
        <div className="rounded-xl bg-[var(--success)]/10 border border-[var(--success)]/30 p-4">
          <p className="text-sm">
            <span className="font-semibold text-[var(--success)]">Aktiver Master:</span>{" "}
            {activeMaster.name} ({activeMaster.filename})
          </p>
        </div>
      )}

      {/* Master List */}
      {isLoading ? (
        <p className="text-[var(--text-secondary)]">Laden...</p>
      ) : !masters?.length ? (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-8 text-center">
          <p className="text-[var(--text-secondary)]">
            Noch kein Master hochgeladen. Lade eine PPTX-Datei hoch um Templates zu generieren.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {masters.map((m) => (
            <div key={m.id} className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)]">
              {/* Master header */}
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setExpandedId(expandedId === m.id ? null : m.id)}
                    className="text-[var(--text-secondary)] hover:text-white transition-colors"
                  >
                    {expandedId === m.id ? "▼" : "▶"}
                  </button>
                  <div>
                    <p className="font-semibold">{m.name}</p>
                    <p className="text-xs text-[var(--text-secondary)]">
                      {m.filename} · {new Date(m.created_at).toLocaleDateString("de-DE")}
                    </p>
                  </div>
                  {m.is_active && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--success)]/20 text-[var(--success)]">
                      Aktiv
                    </span>
                  )}
                </div>

                <div className="flex gap-2">
                  {!m.is_active && (
                    <button
                      onClick={() => activateMaster.mutate(m.id)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-light)] transition-colors"
                    >
                      Aktivieren
                    </button>
                  )}
                  {deleteConfirm === m.id ? (
                    <div className="flex gap-1">
                      <button
                        onClick={() => { deleteMaster.mutate(m.id); setDeleteConfirm(null); }}
                        className="text-xs px-3 py-1.5 rounded-lg bg-[var(--error)] text-white"
                      >
                        Ja, löschen
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-subtle)]"
                      >
                        Nein
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirm(m.id)}
                      className="text-xs px-3 py-1.5 rounded-lg border border-[var(--error)]/30 text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
                    >
                      Löschen
                    </button>
                  )}
                </div>
              </div>

              {/* Templates (expanded) */}
              {expandedId === m.id && <TemplateList masterId={m.id} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TemplateList({ masterId }: { masterId: string }) {
  const { data: templates, isLoading } = useMasterTemplates(masterId);

  if (isLoading) return <div className="p-4 pt-0 text-sm text-[var(--text-secondary)]">Templates laden...</div>;
  if (!templates?.length) return <div className="p-4 pt-0 text-sm text-[var(--text-secondary)]">Keine Templates gefunden.</div>;

  return (
    <div className="border-t border-[var(--border-subtle)] p-4 space-y-2">
      <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-2">
        {templates.length} Templates
      </p>
      {templates.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${
            t.is_active
              ? "border-[var(--accent)]/30 bg-[var(--accent)]/5"
              : "border-[var(--border-subtle)] opacity-50"
          }`}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-[var(--accent)]/20 text-[var(--accent-light)]">
                {t.template_key}
              </span>
              <span className="text-sm font-medium">{t.display_name}</span>
              {!t.is_active && (
                <span className="text-xs text-[var(--text-secondary)]">(deaktiviert)</span>
              )}
            </div>
            {t.description && (
              <p className="text-xs text-[var(--text-secondary)] mt-1">{t.description}</p>
            )}
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Layout #{t.layout_index}: {t.layout_name}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
