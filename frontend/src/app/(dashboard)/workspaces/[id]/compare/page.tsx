"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post } from "@/lib/api";

interface Company {
  id: number;
  name: string;
  status: string;
  overall_score?: number;
}

interface WorkspaceDetail {
  id: number;
  name: string;
  companies: Company[];
}

interface ComparisonReport {
  id: number;
  workspace_id: number;
  company_ids: number[];
  html_content: string | null;
  is_fallback: boolean;
  created_at: string;
}

export default function ComparePage({ params }: { params: { id: string } }) {
  const workspaceId = params.id;
  const queryClient = useQueryClient();
  const [selectedCompanies, setSelectedCompanies] = useState<number[]>([]);
  const [activeReportId, setActiveReportId] = useState<number | null>(null);

  // Fetch workspace companies
  const { data: workspace, isLoading } = useQuery<WorkspaceDetail>({
    queryKey: ["workspace", workspaceId],
    queryFn: () => get<WorkspaceDetail>(`/workspaces/${workspaceId}`),
  });

  // Fetch past reports
  const { data: reports } = useQuery<ComparisonReport[]>({
    queryKey: ["comparison-reports", workspaceId],
    queryFn: async () => {
      // The API returns individual reports; fetch the active one if we have an ID
      if (!activeReportId) return [];
      const report = await get<ComparisonReport>(`/workspaces/${workspaceId}/reports/${activeReportId}`);
      return [report];
    },
    enabled: !!activeReportId,
    refetchInterval: activeReportId ? 5000 : false, // Poll every 5s while waiting
  });

  // Get active report
  const activeReport = reports?.find((r) => r.id === activeReportId);

  // Stop polling once we have html_content
  const shouldPoll = activeReportId && (!activeReport || !activeReport.html_content);

  // Initiate comparison
  const compareMutation = useMutation({
    mutationFn: (companyIds: number[]) =>
      post<{ id: number }>(`/workspaces/${workspaceId}/compare`, { company_ids: companyIds }),
    onSuccess: (data) => {
      setActiveReportId(data.id);
      // Notify navbar
      window.dispatchEvent(new Event("comparison-started"));
    },
  });

  const readyCompanies = workspace?.companies.filter((c) => c.status === "ready") ?? [];

  const handleToggle = (id: number) => {
    setSelectedCompanies((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 3) return prev;
      return [...prev, id];
    });
  };

  const handleCompare = () => {
    if (selectedCompanies.length < 2 || selectedCompanies.length > 3) return;
    compareMutation.mutate(selectedCompanies);
  };

  if (isLoading) {
    return <div className="p-8 flex justify-center"><span className="loading loading-spinner loading-lg" /></div>;
  }

  return (
    <div className="p-6 md:p-8 space-y-8">
      <h1 className="text-2xl font-medium" style={{ letterSpacing: "-0.5px" }}>Compare Companies</h1>

      {/* Selection Card */}
      <div className="bg-base-100 rounded-xl border border-base-300 p-6">
        <h2 className="text-[15px] font-medium mb-1">Select 2-3 Companies</h2>
        <p className="text-[13px] mb-4" style={{ color: "#7b7b78" }}>Only companies with status "ready" are eligible.</p>

        {readyCompanies.length === 0 ? (
          <p className="text-[13px]" style={{ color: "#626260" }}>No ready companies. Research companies first.</p>
        ) : (
          <div className="space-y-2">
            {readyCompanies.map((c) => (
              <label
                key={c.id}
                className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
                style={{
                  borderColor: selectedCompanies.includes(c.id) ? "#111111" : "#d3cec6",
                  backgroundColor: selectedCompanies.includes(c.id) ? "#f5f1ec" : "#ffffff",
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedCompanies.includes(c.id)}
                  onChange={() => handleToggle(c.id)}
                  disabled={!selectedCompanies.includes(c.id) && selectedCompanies.length >= 3}
                  className="checkbox checkbox-sm"
                />
                <span className="flex-1 text-[14px] font-medium">{c.name}</span>
                {c.overall_score && (
                  <span className="text-[12px]" style={{ color: "#626260" }}>{c.overall_score.toFixed(1)}/5.0</span>
                )}
              </label>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mt-4">
          <span className="text-[12px]" style={{ color: "#9c9fa5" }}>{selectedCompanies.length}/3 selected</span>
          <button
            onClick={handleCompare}
            disabled={selectedCompanies.length < 2 || compareMutation.isPending}
            className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg px-5"
          >
            {compareMutation.isPending ? "Starting..." : "Compare"}
          </button>
        </div>

        {compareMutation.error && (
          <p className="text-error text-[13px] mt-2">{(compareMutation.error as Error).message}</p>
        )}
      </div>

      {/* Active Comparison Progress */}
      {activeReportId && !activeReport?.html_content && (
        <div className="bg-base-100 rounded-xl border border-base-300 p-6 text-center">
          <div className="inline-flex items-center gap-2 mb-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-[14px] font-medium">Generating comparison report...</span>
          </div>
          <p className="text-[12px]" style={{ color: "#9c9fa5" }}>This usually takes 30-60 seconds. You can navigate away — check the navbar for updates.</p>
        </div>
      )}

      {/* Report Result */}
      {activeReport?.html_content && (
        <div className="bg-base-100 rounded-xl border border-base-300 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[15px] font-medium">Comparison Report</h2>
            <div className="flex items-center gap-2">
              {activeReport.is_fallback && (
                <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ backgroundColor: "#fef3c7", color: "#92400e" }}>Fallback</span>
              )}
              <span className="text-[11px]" style={{ color: "#9c9fa5" }}>
                {new Date(activeReport.created_at).toLocaleString()}
              </span>
            </div>
          </div>
          <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: activeReport.html_content }}
          />
        </div>
      )}
    </div>
  );
}
