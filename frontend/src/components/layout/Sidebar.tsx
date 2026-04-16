"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useProjects } from "@/hooks/useProjects";

export function Sidebar() {
  const pathname = usePathname();
  const { data: projects } = useProjects();

  return (
    <aside className="w-64 bg-[var(--bg-card)] border-r border-[var(--border-subtle)] flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="p-5 border-b border-[var(--border-subtle)]">
        <Link href="/" className="text-xl font-bold text-white flex items-center gap-2">
          SlideBuddy
        </Link>
        <p className="text-xs text-[var(--text-secondary)] mt-1">PowerPoint Content Agent</p>
      </div>

      {/* Navigation */}
      <nav className="p-3 flex flex-col gap-1">
        <NavLink href="/" active={pathname === "/"}>
          Projekte
        </NavLink>
        <NavLink href="/masters" active={pathname === "/masters"}>
          PowerPoint Master
        </NavLink>
        <NavLink href="/chunks" active={pathname === "/chunks"}>
          Chunk-Browser
        </NavLink>
        <NavLink href="/settings" active={pathname === "/settings"}>
          Einstellungen
        </NavLink>
      </nav>

      {/* Project List */}
      <div className="flex-1 overflow-y-auto p-3 border-t border-[var(--border-subtle)]">
        <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider mb-2 px-3">
          Projekte
        </p>
        {projects?.map((p) => {
          const isActive = pathname.startsWith(`/projects/${p.id}`);
          return (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              className={`block px-3 py-2.5 rounded-lg text-sm transition-colors mb-1 ${
                isActive
                  ? "bg-[var(--accent)] text-white font-medium"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-white"
              }`}
            >
              {p.name}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center px-3 py-3 rounded-lg text-sm font-semibold transition-colors ${
        active
          ? "bg-[var(--accent)] text-white"
          : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-white"
      }`}
    >
      {children}
    </Link>
  );
}
