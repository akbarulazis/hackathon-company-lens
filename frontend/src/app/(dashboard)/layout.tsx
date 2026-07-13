"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { label: "Workspaces", href: "/workspaces" },
];

interface ResearchJob {
  company_id: number;
  status: string;
  message: string;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { lastEvent } = useWebSocket();

  // Track active research jobs for the progress indicator
  const [activeJobs, setActiveJobs] = useState<Map<number, ResearchJob>>(new Map());

  useEffect(() => {
    if (!lastEvent || lastEvent.type !== "research.status") return;
    const event = lastEvent as { type: "research.status"; company_id: number; status: string; message: string };

    setActiveJobs((prev) => {
      const next = new Map(prev);
      if (event.status === "ready" || event.status === "failed") {
        // Remove after a short delay so user sees the final state
        setTimeout(() => {
          setActiveJobs((p) => {
            const n = new Map(p);
            n.delete(event.company_id);
            return n;
          });
        }, 3000);
        next.set(event.company_id, { company_id: event.company_id, status: event.status, message: event.message });
      } else {
        next.set(event.company_id, { company_id: event.company_id, status: event.status, message: event.message });
      }
      return next;
    });
  }, [lastEvent]);

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  const jobsArray = Array.from(activeJobs.values());

  return (
    <div className="min-h-screen bg-base-200">
      {/* Dark Navbar */}
      <header className="sticky top-0 z-40" style={{ backgroundColor: "#111111" }}>
        <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-6">
          {/* Left: Logo + Nav */}
          <div className="flex items-center gap-8">
            <Link
              href="/workspaces"
              className="text-[15px] font-semibold text-white"
              style={{ letterSpacing: "-0.3px" }}
            >
              Company Lens
            </Link>
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="px-3 py-1.5 rounded-md text-[13px] font-medium transition-colors"
                    style={{
                      color: isActive ? "#ffffff" : "#9c9fa5",
                      backgroundColor: isActive ? "rgba(255,255,255,0.1)" : "transparent",
                    }}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Center: Research Progress (persistent across pages) */}
          {jobsArray.length > 0 && (
            <div className="flex items-center gap-3">
              {jobsArray.map((job) => (
                <div
                  key={job.company_id}
                  className="flex items-center gap-2 px-3 py-1 rounded-full"
                  style={{
                    backgroundColor:
                      job.status === "ready"
                        ? "rgba(22,163,74,0.2)"
                        : job.status === "failed"
                        ? "rgba(185,28,28,0.2)"
                        : "rgba(255,86,0,0.15)",
                  }}
                >
                  {job.status !== "ready" && job.status !== "failed" && (
                    <svg className="animate-spin h-3 w-3 text-white" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  {job.status === "ready" && (
                    <span className="text-[11px]">✓</span>
                  )}
                  {job.status === "failed" && (
                    <span className="text-[11px]">✕</span>
                  )}
                  <span
                    className="text-[11px] font-medium max-w-[200px] truncate"
                    style={{
                      color:
                        job.status === "ready"
                          ? "#4ade80"
                          : job.status === "failed"
                          ? "#f87171"
                          : "#ffffff",
                    }}
                  >
                    {job.message}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Right: User + Logout */}
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-[13px]" style={{ color: "#9c9fa5" }}>
                {user.username}
              </span>
            )}
            <button
              onClick={handleLogout}
              className="text-[13px] font-medium px-3 py-1.5 rounded-md transition-colors"
              style={{ color: "#9c9fa5" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#ffffff")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#9c9fa5")}
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      {/* Page Content */}
      <main className="mx-auto max-w-7xl">{children}</main>
    </div>
  );
}
