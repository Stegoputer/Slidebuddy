"use client";

import { useState, useEffect } from "react";
import { HelpIcon } from "@/components/HelpIcon";
import {
  useSettings,
  useUpdateSettings,
  useApiKeys,
  useSetApiKey,
  useDeleteApiKey,
  useModels,
  usePromptPhases,
  useSaveCustomPrompt,
  useDeleteCustomPrompt,
  useSetActivePrompt,
  useDebugSummary,
  useClearDebugLog,
  useTemplates,
  useConstants,
  useMigrateCosine,
} from "@/hooks/useSettings";

const TABS = ["API-Keys", "Modelle", "Generierung", "Planung", "RAG", "Prompts", "Präferenzen"] as const;
type Tab = (typeof TABS)[number];

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("API-Keys");

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Einstellungen</h1>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t
                ? "bg-[var(--accent)] text-white"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "API-Keys" && <ApiKeysTab />}
      {tab === "Modelle" && <ModelsTab />}
      {tab === "Generierung" && <GenerationTab />}
      {tab === "Planung" && <PlanungTab />}
      {tab === "RAG" && <RagTab />}
      {tab === "Prompts" && <PromptsTab />}
      {tab === "Präferenzen" && <PreferencesTab />}
    </div>
  );
}

/* ─── Card wrapper ──────────────────────────────────────────────────── */

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-5 ${className}`}>
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold mb-4">{children}</h2>;
}

function SaveButton({ onClick, pending, label = "Speichern" }: { onClick: () => void; pending?: boolean; label?: string }) {
  return (
    <button
      onClick={onClick}
      disabled={pending}
      className="w-full py-3 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white font-semibold transition-colors disabled:opacity-50"
    >
      {pending ? "Speichern..." : label}
    </button>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] p-3 text-center">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p className="text-lg font-bold mt-1">{String(value)}</p>
    </div>
  );
}

/* ─── Tab 1: API Keys ───────────────────────────────────────────────── */

const PROVIDERS = [
  { key: "anthropic", name: "Anthropic", desc: "Claude-Modelle" },
  { key: "openai", name: "OpenAI", desc: "GPT + Embeddings" },
  { key: "google", name: "Google AI", desc: "Gemini-Modelle" },
  { key: "cerebras", name: "Cerebras", desc: "Schnell-Inferenz (~3k T/s)" },
];

function ApiKeysTab() {
  const { data: apiKeys } = useApiKeys();
  const setKeyMutation = useSetApiKey();
  const deleteKeyMutation = useDeleteApiKey();
  const [editing, setEditing] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");

  const handleSave = (provider: string) => {
    if (!keyInput.trim()) return;
    setKeyMutation.mutate({ provider, key: keyInput.trim() }, {
      onSuccess: () => { setEditing(null); setKeyInput(""); },
    });
  };

  return (
    <div className="space-y-4">
      <SectionTitle>API-Schlüssel</SectionTitle>
      <p className="text-sm text-[var(--text-secondary)] -mt-2 mb-4">
        Keys werden sicher im Windows Credential Manager gespeichert.
      </p>

      {/* Status overview */}
      <div className="grid grid-cols-4 gap-3">
        {PROVIDERS.map(({ key, name, desc }) => {
          const active = apiKeys?.[key] ?? false;
          return (
            <div key={key} className="rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] p-3 text-center">
              <p className="text-xs text-[var(--text-secondary)]">{name}</p>
              <p className={`text-lg font-bold mt-1 ${active ? "text-[var(--success)]" : "text-[var(--warning)]"}`}>
                {active ? "Aktiv" : "Fehlt"}
              </p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">{desc}</p>
            </div>
          );
        })}
      </div>

      {/* Key inputs */}
      {PROVIDERS.map(({ key, name }) => {
        const configured = apiKeys?.[key] ?? false;
        const isEditing = editing === key;

        return (
          <Card key={key}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="font-semibold">{name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  configured ? "bg-[var(--success)]/20 text-[var(--success)]" : "bg-[var(--warning)]/20 text-[var(--warning)]"
                }`}>
                  {configured ? "Konfiguriert" : "Nicht konfiguriert"}
                </span>
              </div>
              <div className="flex gap-2">
                {!isEditing ? (
                  <>
                    <button
                      onClick={() => { setEditing(key); setKeyInput(""); }}
                      className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] transition-colors"
                    >
                      {configured ? "Ändern" : "Hinzufügen"}
                    </button>
                    {configured && (
                      <button
                        onClick={() => deleteKeyMutation.mutate(key)}
                        className="text-xs px-3 py-1.5 rounded-lg border border-[var(--error)]/30 text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
                      >
                        Entfernen
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    <button onClick={() => handleSave(key)} className="text-xs px-3 py-1.5 rounded-lg bg-[var(--success)] text-white">
                      Speichern
                    </button>
                    <button onClick={() => setEditing(null)} className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                      Abbrechen
                    </button>
                  </>
                )}
              </div>
            </div>
            {isEditing && (
              <input
                type="password"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder={`${name} API Key eingeben...`}
                className="mt-3 w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && handleSave(key)}
              />
            )}
          </Card>
        );
      })}
    </div>
  );
}

/* ─── Tab 2: Modelle ────────────────────────────────────────────────── */

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google AI",
  cerebras: "Cerebras (schnell)",
};

function ModelsTab() {
  const { data: settings } = useSettings();
  const { data: modelMap } = useModels();
  const updateSettings = useUpdateSettings();

  const prefs = (settings?.preferences ?? {}) as Record<string, unknown>;
  const defaultModels = (prefs.default_models ?? {}) as Record<string, string>;

  const groups: Record<string, string[]> = modelMap ?? {};
  const hasModels = Object.values(groups).some((m) => m.length > 0);

  const [planning, setPlanning] = useState(defaultModels.planning ?? "");
  const [generation, setGeneration] = useState(defaultModels.generation ?? "");
  const [masterAnalysis, setMasterAnalysis] = useState(defaultModels.master_analysis ?? "");
  const [embedding, setEmbedding] = useState(defaultModels.embedding ?? "text-embedding-3-small");

  if (!hasModels) {
    return (
      <Card>
        <p className="text-[var(--warning)]">Keine Modelle verfügbar. Bitte zuerst API-Keys eintragen.</p>
      </Card>
    );
  }

  const handleSave = () => {
    const updated = {
      ...prefs,
      default_models: { planning, generation, master_analysis: masterAnalysis, embedding },
    };
    updateSettings.mutate(updated);
  };

  const short = (m: string) => m?.split("/").pop() ?? "—";

  return (
    <div className="space-y-4">
      <SectionTitle>Modellauswahl</SectionTitle>

      <div className="grid grid-cols-4 gap-3">
        <Metric label="Planung" value={short(planning)} />
        <Metric label="Generierung" value={short(generation)} />
        <Metric label="Master-Analyse" value={short(masterAnalysis)} />
        <Metric label="Embeddings" value={embedding} />
      </div>

      <Card className="space-y-4">
        <ModelSelect label="Kapitel- & Sektionsplanung" value={planning} groups={groups} onChange={setPlanning} help="Wird für Kapitel- und Sektionsplanung verwendet. Schnellere Modelle reichen aus, da kein langer Text erzeugt wird." />
        <ModelSelect label="Slide-Generierung" value={generation} groups={groups} onChange={setGeneration} help="Erstellt Folieninhalt, Titel und Sprechernoten. Stärkere Modelle liefern deutlich bessere Qualität." />
        <ModelSelect label="Master-Analyse (Layout-Erkennung)" value={masterAnalysis} groups={groups} onChange={setMasterAnalysis} help="Analysiert PPTX-Layouts beim Upload eines Masters und erkennt Template-Strukturen und Platzhalter." />
        <ModelSelect
          label="Embedding-Modell"
          value={embedding}
          groups={{ OpenAI: ["text-embedding-3-small", "text-embedding-3-large"] }}
          onChange={setEmbedding}
          help="Erzeugt Vektoren für die semantische Quellensuche (RAG). 'small' ist schneller und günstiger, 'large' ist präziser bei komplexen Inhalten."
        />
        <SaveButton onClick={handleSave} pending={updateSettings.isPending} />
      </Card>
    </div>
  );
}

function ModelSelect({ label, value, groups, onChange, help }: {
  label: string; value: string; groups: Record<string, string[]>; onChange: (v: string) => void; help?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">
        {label}{help && <HelpIcon text={help} />}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
      >
        {Object.entries(groups).map(([provider, models]) =>
          models.length === 0 ? null : (
            <optgroup key={provider} label={PROVIDER_LABELS[provider] ?? provider}>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </optgroup>
          )
        )}
      </select>
    </div>
  );
}

/* ─── Tab 3: Generierung ────────────────────────────────────────────── */

function GenerationTab() {
  const { data: settings } = useSettings();
  const updateSettings = useUpdateSettings();
  const { data: debugSummary, refetch: refetchDebug } = useDebugSummary();
  const clearLog = useClearDebugLog();

  const prefs = (settings?.preferences ?? {}) as Record<string, unknown>;
  const [batchSize, setBatchSize] = useState<number>(4);
  const [batchInput, setBatchInput] = useState("4");
  const [debugOn, setDebugOn] = useState((prefs.debug_prompts as boolean) ?? false);

  // Sync batchSize from loaded preferences (useState won't re-init after first render)
  useEffect(() => {
    const v = prefs.batch_size as number | undefined;
    if (typeof v === "number" && v > 0) {
      setBatchSize(v);
      setBatchInput(String(v));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  const handleSaveBatch = () => {
    updateSettings.mutate({ ...prefs, batch_size: batchSize });
  };

  const handleToggleDebug = () => {
    const next = !debugOn;
    setDebugOn(next);
    updateSettings.mutate({ ...prefs, debug_prompts: next });
  };

  const hasCalls = (debugSummary?.total_calls ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Batch */}
      <div className="space-y-4">
        <SectionTitle>Batch-Generierung</SectionTitle>

        <div className="grid grid-cols-2 gap-3">
          <Metric label="Batch-Größe" value={`${batchSize} Folien`} />
          <Metric label="Empfehlung" value="3–5 Folien" />
        </div>

        <Card className="space-y-3">
          <label className="block text-sm font-medium">
            Folien pro Batch
            <HelpIcon text="Anzahl Folien pro LLM-Aufruf. 3–5 ist optimal: reduziert API-Kosten und hält Antwortzeiten kurz. Bei 1 wird jede Folie einzeln generiert." />
          </label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={1}
              max={20}
              value={batchInput}
              onChange={(e) => {
                setBatchInput(e.target.value);
                const n = parseInt(e.target.value, 10);
                if (!isNaN(n) && n >= 1 && n <= 20) setBatchSize(n);
              }}
              onBlur={() => {
                const n = Math.max(1, Math.min(20, parseInt(batchInput, 10) || batchSize));
                setBatchSize(n);
                setBatchInput(String(n));
              }}
              className="w-20 px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-main)] text-sm text-center focus:border-[var(--accent)] focus:outline-none"
            />
            <span className="text-sm text-[var(--text-secondary)]">Folien (1–20, empfohlen: 3–5)</span>
          </div>
          <SaveButton onClick={handleSaveBatch} pending={updateSettings.isPending} />
        </Card>
      </div>

      {/* Debug */}
      <div className="space-y-4">
        <SectionTitle>Prompt-Debug-Modus</SectionTitle>
        <p className="text-sm text-[var(--text-secondary)] -mt-2">
          Loggt jeden LLM-Aufruf mit vollständigem Prompt, Chunks und Antwort.
        </p>

        <Card>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              Debug-Logging
              <HelpIcon text="Protokolliert alle LLM-Aufrufe vollständig (Prompts, Antworten, Tokens, Dauer). Hilfreich zur Qualitätsanalyse, erzeugt größere Logdateien." />
            </span>
            <button
              onClick={handleToggleDebug}
              className={`w-12 h-6 rounded-full transition-colors relative ${debugOn ? "bg-[var(--accent)]" : "bg-[var(--border-subtle)]"}`}
            >
              <span className={`block w-5 h-5 rounded-full bg-white transition-transform absolute top-0.5 ${debugOn ? "translate-x-6" : "translate-x-0.5"}`} />
            </button>
          </div>
        </Card>

        {debugOn && hasCalls && (
          <>
            <div className="grid grid-cols-4 gap-3">
              <Metric label="Calls" value={debugSummary!.total_calls} />
              <Metric label="Input-Tokens" value={`~${(debugSummary!.total_input_tokens ?? 0).toLocaleString()}`} />
              <Metric label="Output-Tokens" value={`~${(debugSummary!.total_output_tokens ?? 0).toLocaleString()}`} />
              <Metric label="Dauer" value={`${debugSummary!.total_duration_s ?? 0}s`} />
            </div>

            {debugSummary!.by_phase && (
              <Card>
                <p className="text-sm font-medium mb-2">Details pro Phase</p>
                {Object.entries(debugSummary!.by_phase!).map(([phase, stats]) => (
                  <p key={phase} className="text-xs text-[var(--text-secondary)] mb-1">
                    <span className="font-semibold text-[var(--text-primary)]">{phase}</span>: {stats.calls}x · ~{stats.input_tokens.toLocaleString()} in · ~{stats.output_tokens.toLocaleString()} out · {stats.duration_s.toFixed(1)}s
                  </p>
                ))}
              </Card>
            )}

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => { clearLog.mutate(); refetchDebug(); }}
                className="py-2 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm transition-colors"
              >
                Log löschen
              </button>
              <a
                href="/api/settings/debug/download"
                download="prompt_debug.jsonl"
                className="py-2 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm transition-colors text-center"
              >
                Log herunterladen
              </a>
            </div>
          </>
        )}

        {debugOn && !hasCalls && (
          <Card>
            <p className="text-sm text-[var(--text-secondary)]">Noch keine Calls geloggt. Starte eine Generierung.</p>
          </Card>
        )}
      </div>
    </div>
  );
}

/* ─── Tab 4: Planung ────────────────────────────────────────────────── */

function PlanungTab() {
  const { data: settings } = useSettings();
  const updateSettings = useUpdateSettings();

  const prefs = (settings?.preferences ?? {}) as Record<string, unknown>;
  const planning = (prefs.planning ?? {}) as Record<string, unknown>;

  const [form, setForm] = useState({
    min_chars_per_slide: (planning.min_chars_per_slide as number) ?? 1500,
    target_slides_per_chapter: (planning.target_slides_per_chapter as number) ?? 5,
    max_chapters: (planning.max_chapters as number) ?? 12,
    min_slides_per_chapter: (planning.min_slides_per_chapter as number) ?? 3,
  });

  const set = (key: string, val: number) => setForm((f) => ({ ...f, [key]: val }));

  const handleSave = () => {
    updateSettings.mutate({ ...prefs, planning: { ...form } });
  };

  return (
    <div className="space-y-6">
      <SectionTitle>Kapitel- und Folienplanung</SectionTitle>

      <div className="grid grid-cols-2 gap-3">
        <Metric label="Min. Zeichen/Folie" value={form.min_chars_per_slide} />
        <Metric label="Folien/Kapitel" value={form.target_slides_per_chapter} />
      </div>

      <Card className="space-y-6">
        <div>
          <p className="font-semibold mb-1">Foliendichte</p>
          <p className="text-xs text-[var(--text-secondary)] mb-3">
            Bestimmt wie viel Quelltext pro Folie mindestens vorhanden sein muss. Beeinflusst die automatische Berechnung von Kapitel- und Folienanzahl.
          </p>
          <div className="grid grid-cols-2 gap-6">
            <RangeInput label="Min. Zeichen pro Folie" value={form.min_chars_per_slide} min={500} max={5000} step={100} onChange={(v) => set("min_chars_per_slide", v)} help="Mindestmenge an Quelltext pro Folie (~4 Zeichen = 1 Token). Hoeher = weniger, aber gehaltvollere Folien. Standard: 1500 (~375 Tokens)." />
            <RangeInput label="Ziel-Folien pro Kapitel" value={form.target_slides_per_chapter} min={2} max={15} onChange={(v) => set("target_slides_per_chapter", v)} help="Richtwert fuer die Kapitelplanung. Beeinflusst wie viele Kapitel erstellt werden." />
          </div>
        </div>

        <hr className="border-[var(--border-subtle)]" />

        <div>
          <p className="font-semibold mb-1">Grenzen</p>
          <p className="text-xs text-[var(--text-secondary)] mb-3">
            Ober- und Untergrenzen fuer die Strukturplanung.
          </p>
          <div className="grid grid-cols-2 gap-6">
            <RangeInput label="Max. Kapitel" value={form.max_chapters} min={2} max={20} onChange={(v) => set("max_chapters", v)} help="Obergrenze fuer die Kapitelanzahl. Wird dem LLM als harte Grenze mitgeteilt." />
            <RangeInput label="Min. Folien pro Kapitel" value={form.min_slides_per_chapter} min={1} max={8} onChange={(v) => set("min_slides_per_chapter", v)} help="Jedes Kapitel bekommt mindestens so viele Folien." />
          </div>
        </div>
      </Card>

      <SaveButton onClick={handleSave} pending={updateSettings.isPending} />
    </div>
  );
}

/* ─── Tab 5: RAG ────────────────────────────────────────────────────── */

function RagTab() {
  const { data: settings } = useSettings();
  const updateSettings = useUpdateSettings();
  const migrateCosine = useMigrateCosine();

  const prefs = (settings?.preferences ?? {}) as Record<string, unknown>;
  const rag = (prefs.rag ?? {}) as Record<string, unknown>;

  const [form, setForm] = useState({
    overview_sample_interval: (rag.overview_sample_interval as number) ?? 4,
    overview_chars_per_chunk: (rag.overview_chars_per_chunk as number) ?? 200,
    n_chunks_per_slide: (rag.n_chunks_per_slide as number) ?? 3,
    n_global_generation: (rag.n_global_generation as number) ?? 0,
    chunk_size: (rag.chunk_size as number) ?? 500,
    chunk_overlap: (rag.chunk_overlap as number) ?? 20,
  });
  const [chunkMode, setChunkMode] = useState<string>(
    (rag.chunk_assignment_mode as string) ?? "chunk"
  );

  const set = (key: string, val: number) => setForm((f) => ({ ...f, [key]: val }));

  const handleSave = () => {
    updateSettings.mutate({
      ...prefs,
      rag: { ...form, chunk_assignment_mode: chunkMode },
    });
  };

  return (
    <div className="space-y-6">
      <SectionTitle>RAG</SectionTitle>

      <div className="grid grid-cols-3 gap-3">
        <Metric label="Stichproben-Intervall" value={form.overview_sample_interval} />
        <Metric label="Chunks/Folie" value={form.n_chunks_per_slide} />
        <Metric label="Chunk-Groesse" value={`${form.chunk_size} Tok`} />
      </div>

      <Card className="space-y-6">
        {/* Chapter planning overview */}
        <div>
          <p className="font-semibold mb-1">Kapitelplanung (Quellenueberblick)</p>
          <p className="text-xs text-[var(--text-secondary)] mb-3">Stichproben aus allen Quellen fuer die Kapitelstruktur und Lueckenanalyse.</p>
          <div className="grid grid-cols-2 gap-6">
            <RangeInput label="Stichproben-Intervall" value={form.overview_sample_interval} min={1} max={20} onChange={(v) => set("overview_sample_interval", v)} help="Alle N Chunks eine Stichprobe pro Quelle. Kleinerer Wert = mehr Kontext, mehr Tokens. Laengere Quellen bekommen automatisch mehr Stichproben." />
            <RangeInput label="Zeichen pro Stichprobe" value={form.overview_chars_per_chunk} min={50} max={500} step={25} onChange={(v) => set("overview_chars_per_chunk", v)} help="Wie viel Text pro gesampeltem Chunk der LLM sieht. Bestimmt die Detailtiefe des Ueberblicks." />
          </div>
        </div>

        <hr className="border-[var(--border-subtle)]" />

        {/* Section planning */}
        <div>
          <p className="font-semibold mb-1">Sektionsplanung (Chunk-Zuweisung)</p>
          <p className="text-xs text-[var(--text-secondary)] mb-3">Automatische Zuweisung per Semantic Search. Wird manuell ueberprueft.</p>

          {/* Chunk assignment mode */}
          <div className="mb-4">
            <label className="block text-sm mb-1.5">Zuweisungs-Modus</label>
            <select
              value={chunkMode}
              onChange={(e) => setChunkMode(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-white focus:border-[var(--accent)] focus:outline-none"
            >
              <option value="chunk">Chunk (Semantic Search global)</option>
              <option value="hybrid">Hybrid (pro Kapitel + global Auffuellung)</option>
              <option value="full_source">Full Source (ganze Quelle sequentiell auf Folien)</option>
            </select>
            <p className="text-xs text-[var(--text-secondary)] mt-1.5">
              <strong>Chunk:</strong> Vector-Search ueber alle Quellen (flexibel, Default).{" "}
              <strong>Hybrid:</strong> Semantic Search innerhalb der verlinkten Quellen des Kapitels, ggf. global aufgefuellt.{" "}
              <strong>Full Source:</strong> Der komplette Originaltext jeder verlinkten Quelle wird der Reihe nach auf die Folien des Kapitels verteilt — ideal fuer &quot;Je Quelle ein Kapitel&quot;.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <RangeInput label="Chunks pro Folie" value={form.n_chunks_per_slide} min={1} max={10} onChange={(v) => set("n_chunks_per_slide", v)} help="Top-N relevanteste Chunks pro Slide aus allen Quellen. Diese werden in der Sektionsplanung angezeigt und koennen manuell bearbeitet werden. (Nicht fuer Full Source.)" />
            <RangeInput label="Globale Slides" value={form.n_global_generation} min={0} max={10} onChange={(v) => set("n_global_generation", v)} help="Referenz-Slides aus frueheren Projekten fuer Stil-Konsistenz bei der Generierung. 0 = deaktiviert." />
          </div>
        </div>

        <hr className="border-[var(--border-subtle)]" />

        {/* Chunking */}
        <div>
          <p className="font-semibold mb-1">Chunking (Textaufteilung)</p>
          <p className="text-xs text-[var(--text-secondary)] mb-3">Aenderungen wirken nur bei neuem Upload.</p>
          <div className="grid grid-cols-2 gap-6">
            <RangeInput label="Chunk-Groesse (Tokens)" value={form.chunk_size} min={100} max={2000} step={50} onChange={(v) => set("chunk_size", v)} help="Zielgroesse fuer Textbloecke beim Upload. ~500 Tokens = 2000 Zeichen. Groesser = weniger Chunks, kleiner = feinere Aufloesung." />
            <RangeInput label="Ueberlappung (Tokens)" value={form.chunk_overlap} min={0} max={200} step={5} onChange={(v) => set("chunk_overlap", v)} help="Token-Ueberlappung zwischen Chunks. Verhindert Informationsverlust an Grenzen. Gilt nur fuer neue Uploads." />
          </div>
        </div>

        <SaveButton onClick={handleSave} pending={updateSettings.isPending} />
      </Card>

      {/* Cosine migration */}
      <Card className="space-y-3">
        <p className="font-semibold">Distanzmetrik migrieren</p>
        <p className="text-xs text-[var(--text-secondary)]">
          Stellt bestehende ChromaDB-Collections von L2 auf Cosine-Distanz um.
        </p>
        <button
          onClick={() => migrateCosine.mutate()}
          disabled={migrateCosine.isPending}
          className="w-full py-2 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm transition-colors disabled:opacity-50"
        >
          {migrateCosine.isPending ? "Migriere..." : "Collections auf Cosine migrieren"}
        </button>
        {migrateCosine.isSuccess && (
          <p className="text-sm text-[var(--success)]">
            {migrateCosine.data.migrated > 0
              ? `${migrateCosine.data.migrated} Collection(s) migriert.`
              : "Alle Collections nutzen bereits Cosine."}
          </p>
        )}
      </Card>
    </div>
  );
}

function RangeInput({ label, value, min, max, step = 1, onChange, help }: {
  label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void; help?: string;
}) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{label}{help && <HelpIcon text={help} />}</span>
        <span className="font-mono text-[var(--accent-light)]">{value}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--accent)]"
      />
    </div>
  );
}

/* ─── Tab 5: Prompts ────────────────────────────────────────────────── */

function PromptsTab() {
  const { data: promptData } = usePromptPhases();
  const savePrompt = useSaveCustomPrompt();
  const deletePrompt = useDeleteCustomPrompt();
  const setActive = useSetActivePrompt();

  const [group, setGroup] = useState("Basis");
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [editedText, setEditedText] = useState("");
  const [newName, setNewName] = useState("");
  const [showDefault, setShowDefault] = useState(false);

  if (!promptData) return <Card><p className="text-[var(--text-secondary)]">Laden...</p></Card>;

  const phases = promptData.groups[group] ?? [];
  const phase = phases[phaseIdx] ?? phases[0];
  const label = promptData.labels[phase] ?? phase;

  // Find matching custom prompts for this phase
  const matchingCustom = Object.entries(promptData.custom_prompts)
    .filter(([, p]) => p.phase === phase)
    .map(([name]) => name);

  const sourceOptions = ["default", ...matchingCustom];
  const activeSource = promptData.active_prompts[phase] ?? "default";

  const currentText =
    activeSource === "default"
      ? promptData.defaults[phase] ?? ""
      : promptData.custom_prompts[activeSource]?.text ?? "";

  // Sync edited text when phase/source changes
  const textKey = `${phase}:${activeSource}`;

  return (
    <div className="space-y-4">
      <SectionTitle>Prompt-Editor</SectionTitle>
      <p className="text-sm text-[var(--text-secondary)] -mt-2">
        Bearbeite die System-Prompts für jede Phase. Du kannst eigene Varianten erstellen.
      </p>

      {/* Phase selection */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Kategorie</label>
          <select
            value={group}
            onChange={(e) => { setGroup(e.target.value); setPhaseIdx(0); }}
            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
          >
            {Object.keys(promptData.groups).map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Prompt</label>
          <select
            value={phaseIdx}
            onChange={(e) => setPhaseIdx(Number(e.target.value))}
            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
          >
            {phases.map((p, i) => (
              <option key={p} value={i}>{promptData.labels[p] ?? p}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Active source */}
      <div>
        <label className="block text-sm font-medium mb-1">Aktiver Prompt</label>
        <select
          value={activeSource}
          onChange={(e) => setActive.mutate({ phase, source: e.target.value })}
          className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
        >
          {sourceOptions.map((s) => (
            <option key={s} value={s}>
              {s === "default" ? "🔒 Default (nicht löschbar)" : `📝 ${s}`}
            </option>
          ))}
        </select>
      </div>

      {/* Text editor */}
      <Card>
        <textarea
          key={textKey}
          defaultValue={currentText}
          onChange={(e) => setEditedText(e.target.value)}
          rows={14}
          className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm font-mono resize-y"
        />
      </Card>

      {/* Actions */}
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Name für neuen Prompt"
            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
          />
          <button
            onClick={() => {
              if (!newName.trim() || newName.trim() === "default") return;
              savePrompt.mutate({ name: newName.trim(), phase, text: editedText || currentText });
              setNewName("");
            }}
            className="w-full py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-semibold transition-colors hover:bg-[var(--accent-light)]"
          >
            Als neuen Prompt speichern
          </button>
        </div>
        <div className="flex items-end">
          {activeSource !== "default" && (
            <button
              onClick={() => savePrompt.mutate({ name: activeSource, phase, text: editedText || currentText })}
              className="w-full py-2 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-sm transition-colors"
            >
              Änderungen speichern
            </button>
          )}
        </div>
        <div className="flex items-end">
          {activeSource !== "default" && (
            <button
              onClick={() => deletePrompt.mutate(activeSource)}
              className="w-full py-2 rounded-lg border border-[var(--error)]/30 text-[var(--error)] hover:bg-[var(--error)]/10 text-sm transition-colors"
            >
              Prompt löschen
            </button>
          )}
        </div>
      </div>

      {/* Show default for comparison */}
      {activeSource !== "default" && (
        <div>
          <button
            onClick={() => setShowDefault(!showDefault)}
            className="text-sm text-[var(--text-secondary)] hover:text-white transition-colors"
          >
            {showDefault ? "▼" : "▶"} Default-Prompt anzeigen (zum Vergleich)
          </button>
          {showDefault && (
            <pre className="mt-2 p-3 rounded-lg bg-[var(--bg-main)] border border-[var(--border-subtle)] text-xs overflow-x-auto whitespace-pre-wrap">
              {promptData.defaults[phase]}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Tab 6: Präferenzen ────────────────────────────────────────────── */

function PreferencesTab() {
  const { data: settings } = useSettings();
  const updateSettings = useUpdateSettings();
  const { data: constants } = useConstants();
  const { data: templateData } = useTemplates();

  const prefs = (settings?.preferences ?? {}) as Record<string, unknown>;

  const [language, setLanguage] = useState((prefs.default_language as string) ?? "de");
  const [textLength, setTextLength] = useState((prefs.default_text_length as string) ?? "medium");
  const [tonality, setTonality] = useState((prefs.tonality as string) ?? "");
  const [customRules, setCustomRules] = useState(((prefs.custom_rules as string[]) ?? []).join("\n"));
  const [preferredTemplates, setPreferredTemplates] = useState<string[]>((prefs.preferred_templates as string[]) ?? []);

  // Sync local state when async settings load (useState only uses initializer on mount)
  useEffect(() => {
    if (!settings?.preferences) return;
    setLanguage((prefs.default_language as string) ?? "de");
    setTextLength((prefs.default_text_length as string) ?? "medium");
    setTonality((prefs.tonality as string) ?? "");
    setCustomRules(((prefs.custom_rules as string[]) ?? []).join("\n"));
    setPreferredTemplates((prefs.preferred_templates as string[]) ?? []);
  }, [settings?.preferences]);

  const langLabels = constants?.language_labels ?? { de: "Deutsch", en: "English" };
  const lengthLabels = constants?.text_length_labels ?? { short: "Kurz", medium: "Mittel", long: "Ausführlich" };
  const languages = constants?.languages ?? ["de", "en"];
  const textLengths = constants?.text_lengths ?? ["short", "medium", "long"];

  const templateTypes = templateData?.types ?? [];
  const templateLabels = templateData?.labels ?? {};

  const handleSave = () => {
    updateSettings.mutate({
      ...prefs,
      default_language: language,
      default_text_length: textLength,
      tonality,
      custom_rules: customRules.split("\n").filter((r) => r.trim()),
      preferred_templates: preferredTemplates,
    });
  };

  const toggleTemplate = (t: string) => {
    setPreferredTemplates((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  return (
    <div className="space-y-4">
      <SectionTitle>Präferenzen</SectionTitle>
      <p className="text-sm text-[var(--text-secondary)] -mt-2">Globale Standardwerte für neue Projekte.</p>

      <div className="grid grid-cols-3 gap-3">
        <Metric label="Sprache" value={langLabels[language] ?? language} />
        <Metric label="Textumfang" value={lengthLabels[textLength] ?? textLength} />
        <Metric label="Tonalität" value={tonality || "—"} />
      </div>

      <Card className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Standard-Sprache
              <HelpIcon text="Vorausgewählte Sprache für neue Projekte. Beeinflusst die Quellensuche und die Sprache der generierten Folien." />
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
            >
              {languages.map((l) => (
                <option key={l} value={l}>{langLabels[l] ?? l}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Standard-Textumfang
              <HelpIcon text="Voreingestellte Textmenge pro Folie für neue Projekte. Kann pro Projekt und pro Generierungslauf einzeln überschrieben werden." />
            </label>
            <select
              value={textLength}
              onChange={(e) => setTextLength(e.target.value)}
              className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
            >
              {textLengths.map((l) => (
                <option key={l} value={l}>{lengthLabels[l] ?? l}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            Tonalität
            <HelpIcon text="Stil und Ton für generierte Inhalte. Wird als Vorgabe an das Sprachmodell übergeben. Beispiele: 'professionell', 'wissenschaftlich', 'locker und verständlich'." />
          </label>
          <input
            value={tonality}
            onChange={(e) => setTonality(e.target.value)}
            placeholder="z.B. 'professionell', 'locker', 'wissenschaftlich'"
            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
          />
        </div>

        <hr className="border-[var(--border-subtle)]" />

        <div>
          <label className="block text-sm font-medium mb-1">
            Eigene Regeln (eine pro Zeile)
            <HelpIcon text="Globale Vorgaben für alle Generierungen, eine pro Zeile. Beispiele: 'Keine Anglizismen', 'Immer Quellenangaben nennen', 'Maximal 4 Punkte pro Folie'." />
          </label>
          <textarea
            value={customRules}
            onChange={(e) => setCustomRules(e.target.value)}
            rows={4}
            placeholder={"z.B. 'Keine Anglizismen verwenden'\n'Immer Quellenangaben nennen'"}
            className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm resize-y"
          />
        </div>

        {templateTypes.length > 0 && (
          <div>
            <label className="block text-sm font-medium mb-2">
              Bevorzugte Templates
              <HelpIcon text="Folienlayouts, die bei der Sektionsplanung bevorzugt verwendet werden. Kein Template ausgewählt = alle verfügbaren Layouts werden genutzt." />
            </label>
            <div className="flex flex-wrap gap-2">
              {templateTypes.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleTemplate(t)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    preferredTemplates.includes(t)
                      ? "bg-[var(--accent)] text-white"
                      : "bg-[var(--bg-main)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--accent)]"
                  }`}
                >
                  {templateLabels[t] ?? t}
                </button>
              ))}
            </div>
          </div>
        )}

        <SaveButton onClick={handleSave} pending={updateSettings.isPending} />
      </Card>
    </div>
  );
}
