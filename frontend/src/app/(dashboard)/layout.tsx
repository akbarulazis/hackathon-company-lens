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

interface ComparisonNotification {
  report_id: number;
  workspace_id: number;
  timestamp: number;
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
  const [comparisonNotifs, setComparisonNotifs] = useState<ComparisonNotification[]>([]);
  const [comparingInProgress, setComparingInProgress] = useState(false);

  useEffect(() => {
    if (!lastEvent) return;

    // Handle research status events
    if (lastEvent.type === "research.status") {
      const event = lastEvent as { type: "research.status"; company_id: number; status: string; message: string };
      setActiveJobs((prev) => {
        const next = new Map(prev);
        if (event.status === "ready" || event.status === "failed") {
          setTimeout(() => {
            setActiveJobs((p) => { const n = new Map(p); n.delete(event.company_id); return n; });
          }, 3000);
        }
        next.set(event.company_id, { company_id: event.company_id, status: event.status, message: event.message });
        return next;
      });
    }

    // Handle comparison result events
    if (lastEvent.type === "comparison.result") {
      const event = lastEvent as { type: "comparison.result"; workspace_id: number; report_id: number };
      setComparingInProgress(false);
      setComparisonNotifs((prev) => [
        ...prev,
        { report_id: event.report_id, workspace_id: event.workspace_id, timestamp: Date.now() },
      ]);
      // Auto-dismiss after 15 seconds
      setTimeout(() => {
        setComparisonNotifs((prev) => prev.filter((n) => n.report_id !== event.report_id));
      }, 15000);
    }

    // Handle comparison status (in-progress)
    if (lastEvent.type === "comparison.status") {
      const event = lastEvent as { type: "comparison.status"; workspace_id: number; report_id: number; status: string };
      if (event.status === "running") {
        setComparingInProgress(true);
      }
    }
  }, [lastEvent]);

  // Also allow compare page to signal progress via a custom event
  useEffect(() => {
    const handler = () => setComparingInProgress(true);
    window.addEventListener("comparison-started", handler);
    return () => window.removeEventListener("comparison-started", handler);
  }, []);

  // Listen for research-started events from workspace page
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { name: string; id: number };
      if (detail) {
        setActiveJobs((prev) => {
          const next = new Map(prev);
          next.set(detail.id, { company_id: detail.id, status: "researching", message: `Researching ${detail.name}...` });
          return next;
        });
        // Poll until done
        const pollInterval = setInterval(async () => {
          try {
            const data = await fetch(`/api/companies/${detail.id}`).then(r => r.json());
            if (data.status === "ready") {
              setActiveJobs((prev) => {
                const next = new Map(prev);
                next.set(detail.id, { company_id: detail.id, status: "ready", message: `${detail.name} research complete!` });
                return next;
              });
              setTimeout(() => {
                setActiveJobs((p) => { const n = new Map(p); n.delete(detail.id); return n; });
              }, 5000);
              clearInterval(pollInterval);
            } else if (data.status === "failed") {
              setActiveJobs((prev) => {
                const next = new Map(prev);
                next.set(detail.id, { company_id: detail.id, status: "failed", message: `${detail.name} research failed` });
                return next;
              });
              setTimeout(() => {
                setActiveJobs((p) => { const n = new Map(p); n.delete(detail.id); return n; });
              }, 5000);
              clearInterval(pollInterval);
            } else {
              // Update status message
              const statusMap: Record<string, string> = {
                pending: `Queued: ${detail.name}`,
                researching: `Searching web for ${detail.name}...`,
                profiling: `Generating brief for ${detail.name}...`,
                scoring: `Scoring ${detail.name}...`,
              };
              setActiveJobs((prev) => {
                const next = new Map(prev);
                next.set(detail.id, { company_id: detail.id, status: data.status, message: statusMap[data.status] || `Processing ${detail.name}...` });
                return next;
              });
            }
          } catch {
            // Ignore poll errors
          }
        }, 5000);
        // Cleanup after 10 minutes max
        setTimeout(() => clearInterval(pollInterval), 600000);
      }
    };
    window.addEventListener("research-started", handler);
    return () => window.removeEventListener("research-started", handler);
  }, []);

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

          {/* Comparison Notifications */}
          {comparingInProgress && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full" style={{ backgroundColor: "rgba(59,130,246,0.15)" }}>
              <svg className="animate-spin h-3 w-3" style={{ color: "#93c5fd" }} viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-[11px] font-medium" style={{ color: "#93c5fd" }}>
                Comparing companies...
              </span>
            </div>
          )}
          {comparisonNotifs.length > 0 && (
            <div className="flex items-center gap-2">
              {comparisonNotifs.map((notif) => (
                <Link
                  key={notif.report_id}
                  href={`/workspaces/${notif.workspace_id}/compare`}
                  className="flex items-center gap-2 px-3 py-1 rounded-full animate-pulse"
                  style={{ backgroundColor: "rgba(22,163,74,0.2)" }}
                  onClick={() => setComparisonNotifs((prev) => prev.filter((n) => n.report_id !== notif.report_id))}
                >
                  <span className="text-[11px]">✓</span>
                  <span className="text-[11px] font-medium" style={{ color: "#4ade80" }}>
                    Comparison ready — click to view
                  </span>
                </Link>
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
