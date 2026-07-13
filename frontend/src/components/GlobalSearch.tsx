"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSearch, SearchResult } from "@/hooks/useSearch";
import { post } from "@/lib/api";
import { useWebSocket, WebSocketEvent } from "@/hooks/useWebSocket";

/**
 * Global search component with typeahead dropdown.
 * Shows company results with Client_Status badge, industry, and Overall_Score.
 * Offers "Research new company" when no matches found.
 * Displays research progress via WebSocket integration.
 *
 * Validates: Requirements 4.1, 4.2, 4.3, 4.4
 */

interface ResearchProgress {
  company_id: number | null;
  status: string;
  message: string;
}

function ClientStatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    Client: "badge-success",
    Prospect: "badge-info",
    Unknown: "badge-ghost",
  };

  return (
    <span className={`badge badge-sm ${colorMap[status] ?? "badge-ghost"}`}>
      {status}
    </span>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-base-content/50">N/A</span>;

  let colorClass = "text-error";
  if (score > 4) colorClass = "text-success";
  else if (score > 3) colorClass = "text-info";
  else if (score > 2) colorClass = "text-warning";
  else if (score > 1) colorClass = "text-orange-500";

  return (
    <span className={`font-semibold text-sm ${colorClass}`}>
      {score.toFixed(1)}
    </span>
  );
}

export function GlobalSearch() {
  const router = useRouter();
  const { query, setQuery, results, isLoading, canResearch, clearSearch } = useSearch();
  const { lastEvent } = useWebSocket();

  const [isOpen, setIsOpen] = useState(false);
  const [researchProgress, setResearchProgress] = useState<ResearchProgress | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Show dropdown when query has content
  const showDropdown = isOpen && query.length >= 2;

  // Handle WebSocket research.status events
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === "research.status") {
      const event = lastEvent as Extract<WebSocketEvent, { type: "research.status" }>;
      setResearchProgress({
        company_id: event.company_id,
        status: event.status,
        message: event.message,
      });

      // If research is complete, clear progress after a short delay
      if (event.status === "ready" || event.status === "failed") {
        setTimeout(() => {
          setIsResearching(false);
          setResearchProgress(null);
          if (event.status === "ready") {
            router.push(`/companies/${event.company_id}`);
            clearSearch();
            setIsOpen(false);
          }
        }, 1500);
      }
    }
  }, [lastEvent, router, clearSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        inputRef.current?.blur();
      }
    },
    []
  );

  // Navigate to company detail
  const handleSelectResult = useCallback(
    (result: SearchResult) => {
      router.push(`/companies/${result.id}`);
      clearSearch();
      setIsOpen(false);
    },
    [router, clearSearch]
  );

  // Initiate research for new company
  const handleResearch = useCallback(async () => {
    if (!query.trim() || isResearching) return;

    setIsResearching(true);
    setResearchProgress({
      company_id: null,
      status: "pending",
      message: `Initiating research for "${query}"...`,
    });

    try {
      const response = await post<{ company_id: number; status: string }>(
        "/companies/research",
        { company_name: query.trim() }
      );

      setResearchProgress({
        company_id: response.company_id,
        status: response.status,
        message: `Research started for "${query}"`,
      });
    } catch (error) {
      setIsResearching(false);
      setResearchProgress({
        company_id: null,
        status: "failed",
        message: error instanceof Error ? error.message : "Failed to initiate research",
      });

      // Clear error message after 3 seconds
      setTimeout(() => {
        setResearchProgress(null);
      }, 3000);
    }
  }, [query, isResearching]);

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      {/* Search Input */}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          placeholder="Search companies..."
          className="input input-bordered w-full pr-10"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          aria-label="Search companies"
          aria-expanded={showDropdown}
          aria-controls="search-results-dropdown"
          aria-autocomplete="list"
          role="combobox"
        />

        {/* Loading spinner or search icon */}
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {isLoading ? (
            <span className="loading loading-spinner loading-sm" aria-label="Searching..." />
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 text-base-content/50"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          )}
        </div>
      </div>

      {/* Dropdown Results */}
      {showDropdown && (
        <div
          id="search-results-dropdown"
          className="absolute z-50 mt-1 w-full rounded-box bg-base-100 shadow-lg border border-base-300 max-h-80 overflow-y-auto"
          role="listbox"
        >
          {/* Research Progress */}
          {researchProgress && (
            <div className="p-3 border-b border-base-200">
              <div className="flex items-center gap-2">
                {researchProgress.status !== "failed" && researchProgress.status !== "ready" && (
                  <span className="loading loading-spinner loading-xs" />
                )}
                {researchProgress.status === "ready" && (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4 text-success"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {researchProgress.status === "failed" && (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4 text-error"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                <span className="text-sm">{researchProgress.message}</span>
              </div>
              {researchProgress.status && researchProgress.status !== "failed" && researchProgress.status !== "ready" && (
                <div className="mt-1">
                  <progress className="progress progress-primary w-full" />
                </div>
              )}
            </div>
          )}

          {/* Search Results */}
          {results.length > 0 && (
            <ul className="menu menu-compact p-1">
              {results.map((result) => (
                <li key={result.id}>
                  <button
                    className="flex items-center justify-between gap-2 w-full text-left"
                    onClick={() => handleSelectResult(result)}
                    role="option"
                    aria-selected={false}
                  >
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="font-medium truncate">{result.name}</span>
                      <span className="text-xs text-base-content/60 truncate">
                        {result.industry ?? "Unknown industry"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <ClientStatusBadge status={result.client_status} />
                      <ScoreBadge score={result.overall_score} />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* No results + can research */}
          {results.length === 0 && !isLoading && canResearch && !researchProgress && (
            <div className="p-3">
              <p className="text-sm text-base-content/60 mb-2">
                No companies found matching &ldquo;{query}&rdquo;
              </p>
              <button
                className="btn btn-primary btn-sm w-full"
                onClick={handleResearch}
                disabled={isResearching}
              >
                {isResearching ? (
                  <>
                    <span className="loading loading-spinner loading-xs" />
                    Researching...
                  </>
                ) : (
                  <>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Research &ldquo;{query}&rdquo;
                  </>
                )}
              </button>
            </div>
          )}

          {/* No results, cannot research (query too short handled by not showing dropdown) */}
          {results.length === 0 && !isLoading && !canResearch && !researchProgress && (
            <div className="p-3 text-sm text-base-content/60 text-center">
              No companies found
            </div>
          )}

          {/* Loading state */}
          {isLoading && results.length === 0 && (
            <div className="p-3 flex items-center justify-center gap-2">
              <span className="loading loading-spinner loading-sm" />
              <span className="text-sm text-base-content/60">Searching...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
