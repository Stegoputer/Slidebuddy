"use client";

import { useState } from "react";
import type { Slide } from "@/lib/types";

interface SlideCardProps {
  slide: Slide;
  index: number;
  onSave?: (updated: Partial<Slide>) => void;
  saving?: boolean;
}

function parseContent(json: string | undefined): Record<string, unknown> {
  if (!json) return {};
  try { return JSON.parse(json) as Record<string, unknown>; } catch { return {}; }
}

function valueToEditString(v: unknown): string {
  if (Array.isArray(v)) {
    return (v as unknown[]).map((item) =>
      typeof item === "object" && item !== null ? JSON.stringify(item) : String(item)
    ).join("\n");
  }
  if (typeof v === "object" && v !== null) return JSON.stringify(v, null, 2);
  return String(v ?? "");
}

function editStringToValue(s: string, original: unknown): unknown {
  if (Array.isArray(original)) {
    const hasObjects = (original as unknown[]).some((item) => typeof item === "object" && item !== null);
    if (hasObjects) {
      return s.split("\n").filter((l) => l.trim() !== "").map((line) => {
        try { return JSON.parse(line); } catch { return line; }
      });
    }
    return s.split("\n").filter((l) => l.trim() !== "");
  }
  return s;
}

/* --- Type guards for nested template structures --- */

function isSectionObject(v: unknown): v is { heading: string; bullets: Array<{ heading: string; text: string }> } {
  if (typeof v !== "object" || v === null) return false;
  const obj = v as Record<string, unknown>;
  return typeof obj.heading === "string" && Array.isArray(obj.bullets);
}

function isBulletObject(v: unknown): v is { heading: string; text: string } {
  if (typeof v !== "object" || v === null) return false;
  const obj = v as Record<string, unknown>;
  return typeof obj.heading === "string" && typeof obj.text === "string";
}

function ContentValue({ value }: { value: unknown }) {
  // Array of section objects (detail template: {heading, bullets})
  if (Array.isArray(value) && value.length > 0 && value.every(isSectionObject)) {
    return (
      <div className="space-y-3">
        {(value as Array<{ heading: string; bullets: Array<{ heading: string; text: string }> }>).map((section, i) => (
          <div key={i}>
            <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{section.heading}</h4>
            <ul className="list-disc pl-4 space-y-1">
              {section.bullets.map((bullet, j) => (
                <li key={j} className="text-sm text-[var(--text-primary)]">
                  <span className="font-medium">{bullet.heading}:</span> {bullet.text}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    );
  }

  // Array of bullet objects ({heading, text})
  if (Array.isArray(value) && value.length > 0 && value.every(isBulletObject)) {
    return (
      <ul className="list-disc pl-4 space-y-1">
        {(value as Array<{ heading: string; text: string }>).map((bullet, i) => (
          <li key={i} className="text-sm text-[var(--text-primary)]">
            <span className="font-medium">{bullet.heading}:</span> {bullet.text}
          </li>
        ))}
      </ul>
    );
  }

  // Array of primitives or mixed
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-4 space-y-0.5">
        {(value as unknown[]).map((item, i) => (
          <li key={i} className="text-sm text-[var(--text-primary)]">
            {typeof item === "object" && item !== null
              ? JSON.stringify(item)
              : String(item)}
          </li>
        ))}
      </ul>
    );
  }

  // Plain object — render entries
  if (typeof value === "object" && value !== null) {
    return (
      <pre className="text-sm text-[var(--text-primary)] whitespace-pre-wrap font-mono bg-[var(--bg-main)] rounded-lg p-2">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }

  return <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">{String(value ?? "")}</p>;
}

export function SlideCard({ slide, index, onSave, saving }: SlideCardProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(slide.title);
  const [subtitle, setSubtitle] = useState(slide.subtitle ?? "");
  const [notes, setNotes] = useState(slide.speaker_notes ?? "");
  const [contentEdit, setContentEdit] = useState<Record<string, string>>({});

  const parsedContent = parseContent(slide.content_json);
  const contentEntries = Object.entries(parsedContent).filter(([k]) => k !== "type");

  const handleStartEdit = () => {
    setTitle(slide.title);
    setSubtitle(slide.subtitle ?? "");
    setNotes(slide.speaker_notes ?? "");
    setContentEdit(
      Object.fromEntries(contentEntries.map(([k, v]) => [k, valueToEditString(v)]))
    );
    setEditing(true);
  };

  const handleCancel = () => {
    setEditing(false);
  };

  const handleSave = () => {
    const newContent = Object.fromEntries(
      contentEntries.map(([k]) => [k, editStringToValue(contentEdit[k] ?? "", parsedContent[k])])
    );
    onSave?.({
      title,
      subtitle: subtitle || undefined,
      speaker_notes: notes || undefined,
      content_json: contentEntries.length > 0 ? JSON.stringify(newContent) : slide.content_json,
    });
    setEditing(false);
  };

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border-subtle)] bg-[var(--bg-main)]/40">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-[var(--accent)]/20 text-[var(--accent-light)]">
            {slide.template_type}
          </span>
          <span className="text-xs text-[var(--text-secondary)]">Folie {index + 1}</span>
          {slide.is_reused && (
            <span className="text-xs px-2 py-0.5 rounded bg-[var(--warning)]/20 text-[var(--warning)]">Wiederverwendet</span>
          )}
        </div>
        {onSave && !editing && (
          <button
            onClick={handleStartEdit}
            className="text-xs px-3 py-1 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors"
          >
            Bearbeiten
          </button>
        )}
      </div>

      <div className="p-5 space-y-4">
        {/* Title */}
        <div>
          <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-1">Titel</p>
          {editing ? (
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-lg font-bold focus:border-[var(--accent)] focus:outline-none"
            />
          ) : (
            <h3 className="text-lg font-bold">{slide.title}</h3>
          )}
        </div>

        {/* Subtitle */}
        {(editing || slide.subtitle) && (
          <div>
            <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-1">Untertitel</p>
            {editing ? (
              <input
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                placeholder="Untertitel eingeben..."
                className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
              />
            ) : (
              <p className="text-sm text-[var(--text-secondary)] italic">{slide.subtitle}</p>
            )}
          </div>
        )}

        {/* Content fields */}
        {contentEntries.map(([key, value]) => (
          <div key={key}>
            <p className="text-xs font-semibold text-[var(--accent-light)] uppercase tracking-wider mb-1">{key}</p>
            {editing ? (
              <textarea
                value={contentEdit[key] ?? ""}
                onChange={(e) => setContentEdit((prev) => ({ ...prev, [key]: e.target.value }))}
                rows={Array.isArray(value) ? Math.max(3, (value as unknown[]).length + 1) : 3}
                className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm resize-y focus:border-[var(--accent)] focus:outline-none"
              />
            ) : (
              <ContentValue value={value} />
            )}
            {editing && Array.isArray(value) && (
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">Ein Punkt pro Zeile</p>
            )}
          </div>
        ))}

        {/* Speaker Notes */}
        {(editing || slide.speaker_notes) && (
          <details className="text-sm" open={editing}>
            <summary className="cursor-pointer text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] uppercase tracking-wider select-none transition-colors">
              Sprechernotizen
            </summary>
            <div className="mt-2">
              {editing ? (
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="Sprechernotizen..."
                  className="w-full bg-[var(--bg-main)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm resize-y focus:border-[var(--accent)] focus:outline-none"
                />
              ) : (
                <p className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">{slide.speaker_notes}</p>
              )}
            </div>
          </details>
        )}

        {/* Chain of Thought — read-only, collapsed */}
        {slide.chain_of_thought && (
          <details className="text-sm">
            <summary className="cursor-pointer text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] uppercase tracking-wider select-none transition-colors">
              KI-Überlegungen
            </summary>
            <pre className="mt-2 text-xs text-[var(--text-secondary)] whitespace-pre-wrap font-mono bg-[var(--bg-main)] rounded-lg p-3 leading-relaxed">
              {slide.chain_of_thought}
            </pre>
          </details>
        )}

        {/* Edit actions */}
        {editing && (
          <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
            <button
              onClick={handleCancel}
              className="px-4 py-2 text-sm rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] transition-colors"
            >
              Abbrechen
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-light)] text-white transition-colors disabled:opacity-50"
            >
              {saving ? "Speichern..." : "Speichern"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
