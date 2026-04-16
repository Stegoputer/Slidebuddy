"use client";

import { useState } from "react";
import { useProjects } from "@/hooks/useProjects";
import { useSources } from "@/hooks/useSources";
import { useChunks } from "@/hooks/useChunks";

export default function ChunkBrowserPage() {
  const { data: projects } = useProjects();
  const [projectId, setProjectId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [chunkIdx, setChunkIdx] = useState(0);

  const { data: sources } = useSources(projectId || "");
  const { data: chunks, isLoading: chunksLoading } = useChunks(projectId, sourceId || null, search);

  // Reset source and chunk when project changes
  const handleProjectChange = (pid: string) => {
    setProjectId(pid);
    setSourceId("");
    setChunkIdx(0);
    setSearch("");
    setSearchInput("");
  };

  // Reset chunk index when source changes
  const handleSourceChange = (sid: string) => {
    setSourceId(sid);
    setChunkIdx(0);
    setSearch("");
    setSearchInput("");
  };

  const handleSearch = () => {
    setSearch(searchInput);
    setChunkIdx(0);
  };

  const totalChunks = chunks?.length ?? 0;
  const currentChunk = chunks?.[chunkIdx];

  // Clamp index if chunks change
  if (chunkIdx >= totalChunks && totalChunks > 0) {
    setChunkIdx(totalChunks - 1);
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Chunk-Browser</h1>
      <p className="text-sm text-[var(--text-secondary)]">
        Durchsuche und inspiziere die verarbeiteten Textchunks deiner Quellen.
      </p>

      {/* Selectors */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-[var(--text-secondary)] mb-1.5">Projekt</label>
          <select
            value={projectId}
            onChange={(e) => handleProjectChange(e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:border-[var(--accent)] focus:outline-none"
          >
            <option value="">Projekt wählen...</option>
            {projects?.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-[var(--text-secondary)] mb-1.5">Quelle</label>
          <select
            value={sourceId}
            onChange={(e) => handleSourceChange(e.target.value)}
            disabled={!projectId}
            className="w-full px-4 py-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white focus:border-[var(--accent)] focus:outline-none disabled:opacity-50"
          >
            <option value="">Quelle wählen...</option>
            {sources?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.filename} ({s.chunk_count} Chunks)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Search */}
      {sourceId && (
        <div className="flex gap-2">
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Chunks durchsuchen..."
            className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
          />
          <button
            onClick={handleSearch}
            className="px-5 py-2.5 rounded-lg bg-[var(--accent)] text-white font-semibold hover:bg-[var(--accent-light)] transition-colors"
          >
            Suchen
          </button>
          {search && (
            <button
              onClick={() => { setSearch(""); setSearchInput(""); setChunkIdx(0); }}
              className="px-4 py-2.5 rounded-lg border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
            >
              Zurücksetzen
            </button>
          )}
        </div>
      )}

      {/* Content */}
      {!projectId && (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-12 text-center">
          <p className="text-[var(--text-secondary)]">Wähle ein Projekt und eine Quelle um Chunks zu durchsuchen.</p>
        </div>
      )}

      {projectId && !sourceId && sources && sources.length === 0 && (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-12 text-center">
          <p className="text-[var(--text-secondary)]">Keine Quellen in diesem Projekt.</p>
        </div>
      )}

      {chunksLoading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <span className="text-[var(--text-secondary)]">Chunks laden...</span>
        </div>
      )}

      {sourceId && !chunksLoading && totalChunks === 0 && (
        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-12 text-center">
          <p className="text-[var(--text-secondary)]">
            {search ? "Keine Chunks entsprechen der Suche." : "Keine Chunks für diese Quelle gefunden."}
          </p>
        </div>
      )}

      {currentChunk && (
        <div className="space-y-4">
          {/* Navigation */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setChunkIdx((i) => Math.max(0, i - 1))}
              disabled={chunkIdx === 0}
              className="px-4 py-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white font-semibold hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ◀
            </button>
            <div className="flex-1 text-center">
              <span className="text-sm">
                Chunk <span className="font-bold text-[var(--accent-light)]">{chunkIdx + 1}</span> / {totalChunks}
              </span>
              {search && (
                <span className="text-xs text-[var(--text-secondary)] ml-2">(gefiltert)</span>
              )}
            </div>
            <button
              onClick={() => setChunkIdx((i) => Math.min(totalChunks - 1, i + 1))}
              disabled={chunkIdx >= totalChunks - 1}
              className="px-4 py-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-white font-semibold hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ▶
            </button>
          </div>

          {/* Metadata + Stats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4">
              <h3 className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-3">Metadaten</h3>
              <div className="space-y-1.5">
                {Object.entries(currentChunk.metadata).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">{key}</span>
                    <span className="font-mono text-xs text-[var(--accent-light)] max-w-[60%] truncate text-right">
                      {String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4">
              <h3 className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-3">Statistik</h3>
              <div className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--text-secondary)]">ID</span>
                  <span className="font-mono text-xs text-[var(--accent-light)] truncate max-w-[70%] text-right">{currentChunk.id}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--text-secondary)]">Zeichen</span>
                  <span className="font-bold">{currentChunk.char_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--text-secondary)]">Tokens (ca.)</span>
                  <span className="font-bold">{currentChunk.token_estimate}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Chunk text */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-5">
            <h3 className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-3">Chunk-Inhalt</h3>
            <pre className="text-sm text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed max-h-[400px] overflow-y-auto">
              {currentChunk.text}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
