"use client";

interface HelpIconProps {
  text: string;
}

export function HelpIcon({ text }: HelpIconProps) {
  return (
    <span className="group relative inline-flex items-center ml-1.5 align-middle">
      <span className="w-4 h-4 rounded-full bg-[var(--bg-hover)] border border-[var(--border-subtle)] text-[var(--text-secondary)] text-[10px] font-bold flex items-center justify-center cursor-help hover:border-[var(--accent)] hover:text-[var(--accent-light)] transition-colors select-none">
        ?
      </span>
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 hidden group-hover:block bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg p-3 text-xs text-[var(--text-secondary)] leading-relaxed shadow-xl z-50 pointer-events-none whitespace-normal">
        {text}
      </span>
    </span>
  );
}
