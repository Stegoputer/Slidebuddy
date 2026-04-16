"use client";

import { useEffect } from "react";

/**
 * Warns user before navigating away when a condition is true.
 * Covers: browser close/refresh (beforeunload) + in-app navigation (click intercept).
 */
export function useNavigationGuard(shouldBlock: boolean, message?: string) {
  const msg = message ?? "Ein Prozess läuft noch. Wirklich verlassen?";

  // Browser close / refresh
  useEffect(() => {
    if (!shouldBlock) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [shouldBlock]);

  // In-app link clicks — intercept <a> clicks before Next.js handles them
  useEffect(() => {
    if (!shouldBlock) return;
    const handler = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("http")) return;
      if (!window.confirm(msg)) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    // Capture phase to intercept before Next.js router
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [shouldBlock, msg]);
}
