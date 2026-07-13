"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post } from "@/lib/api";
import { getAccessToken } from "@/lib/api";
import { WebSocketManager } from "@/lib/ws";

interface Company {
  id: number;
  name: string;
  status: string;
  industry?: string;
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
  html_content: string;
  is_fallback: boolean;
  created_at: string;
}

interface CompareResponse {
  report_id: number;
  status: string;
}

export default function ComparePage({
  params,
}: {
  params: { id: string };
}) {
  const workspaceId = params.id;
  const queryClient = useQueryClient();

  const [selectedCompanies, setSelectedCompanies] = useState<number[]>([]);
  const [isComparing, setIsComparing] = useState(false);
  const [reportId, setReportId] = useState<number | null>(null);
  const wsRef = useRef<WebSocketManager | null>(null);

  // Fetch workspace detail with companies
  const { data: workspace, isLoading: isLoadingWorkspace } = useQuery<WorkspaceDetail>({
    queryKey: ["workspace", workspaceId],
    queryFn: () => get<WorkspaceDetail>(`/workspaces/${workspaceId}`),
  });

  // Fetch report if reportId is set
  const { data: report, isLoading: isLoadingReport } = useQuery<ComparisonReport>({
    queryKey: ["comparison-report", workspaceId, reportId],
    queryFn: () => get<ComparisonReport>(`/workspaces/${workspaceId}/reports/${reportId}`),
    enabled: !!reportId,
  });

  // Initiate comparison mutation
  const compareMutation = useMutation({
    mutationFn: (companyIds: number[]) =>
      post<CompareResponse>(`/workspaces/${workspaceId}/compare`, {
        company_ids: companyIds,
      }),
    onSuccess: (data) => {
      setReportId(data.report_id);
      setIsComparing(true);
    },
    onError: () => {
      setIsComparing(false);
    },
  });

  // WebSocket for real-time comparison result
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;

    const ws = new WebSocketManager({
      token,
    });

    ws.on("comparison.result", (data) => {
      if (String(data.workspace_id) === workspaceId) {
        setReportId(data.report_id);
        setIsComparing(false);
        // Refetch the report
        queryClient.invalidateQueries({
          queryKey: ["comparison-report", workspaceId, data.report_id],
        });
      }
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [workspaceId, queryClient]);

  // Filter companies that are "ready" for comparison
  const readyCompanies = workspace?.companies.filter(
    (c) => c.status === "ready"
  ) ?? [];

  const handleToggleCompany = (companyId: number) => {
    setSelectedCompanies((prev) => {
      if (prev.includes(companyId)) {
        return prev.filter((id) => id !== companyId);
      }
      // Max 3 companies
      if (prev.length >= 3) return prev;
      return [...prev, companyId];
    });
  };

  const handleCompare = () => {
    if (selectedCompanies.length < 2 || selectedCompanies.length > 3) return;
    setIsComparing(true);
    compareMutation.mutate(selectedCompanies);
  };

  const isCompareDisabled =
    selectedCompanies.length < 2 ||
    selectedCompanies.length > 3 ||
    isComparing ||
    compareMutation.isPending;

  if (isLoadingWorkspace) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center min-h-[200px]">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Compare Companies</h1>
        <span className="text-sm text-base-content/60">
          Workspace: {workspace?.name}
        </span>
      </div>

      {/* Company Selection */}
      <div className="card bg-base-100 shadow-sm">
        <div className="card-body">
          <h2 className="card-title text-lg">
            Select Companies to Compare (2-3)
          </h2>
          <p className="text-sm text-base-content/60 mb-4">
            Only companies with status &quot;ready&quot; are eligible for comparison.
          </p>

          {readyCompanies.length === 0 ? (
            <div className="alert alert-warning">
              <span>
                No companies with &quot;ready&quot; status found in this workspace.
                Research companies first before comparing.
              </span>
            </div>
          ) : (
            <div className="space-y-2">
              {readyCompanies.map((company) => (
                <label
                  key={company.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedCompanies.includes(company.id)
                      ? "border-primary bg-primary/5"
                      : "border-base-300 hover:border-primary/50"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="checkbox checkbox-primary"
                    checked={selectedCompanies.includes(company.id)}
                    onChange={() => handleToggleCompany(company.id)}
                    disabled={
                      !selectedCompanies.includes(company.id) &&
                      selectedCompanies.length >= 3
                    }
                  />
                  <div className="flex-1">
                    <span className="font-medium">{company.name}</span>
                    {company.industry && (
                      <span className="ml-2 badge badge-ghost badge-sm">
                        {company.industry}
                      </span>
                    )}
                  </div>
                  {company.overall_score !== undefined && (
                    <span className="badge badge-primary badge-outline">
                      Score: {company.overall_score.toFixed(1)}
                    </span>
                  )}
                </label>
              ))}
            </div>
          )}

          <div className="card-actions justify-end mt-4">
            <span className="text-sm text-base-content/60 self-center mr-2">
              {selectedCompanies.length} of 3 selected
            </span>
            <button
              className="btn btn-primary"
              disabled={isCompareDisabled}
              onClick={handleCompare}
            >
              {compareMutation.isPending || isComparing ? (
                <>
                  <span className="loading loading-spinner loading-sm"></span>
                  Comparing...
                </>
              ) : (
                "Compare"
              )}
            </button>
          </div>

          {compareMutation.isError && (
            <div className="alert alert-error mt-2">
              <span>
                {compareMutation.error instanceof Error
                  ? compareMutation.error.message
                  : "Failed to initiate comparison."}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Loading state while waiting for comparison result */}
      {isComparing && !report && (
        <div className="card bg-base-100 shadow-sm">
          <div className="card-body items-center text-center">
            <span className="loading loading-dots loading-lg text-primary"></span>
            <p className="text-base-content/60 mt-2">
              Generating comparison report... This may take a moment.
            </p>
          </div>
        </div>
      )}

      {/* Report display */}
      {isLoadingReport && reportId && (
        <div className="card bg-base-100 shadow-sm">
          <div className="card-body items-center">
            <span className="loading loading-spinner loading-md"></span>
            <p className="text-sm text-base-content/60">Loading report...</p>
          </div>
        </div>
      )}

      {report && (
        <div className="card bg-base-100 shadow-sm">
          <div className="card-body">
            <div className="flex items-center justify-between mb-4">
              <h2 className="card-title text-lg">Comparison Report</h2>
              {report.is_fallback && (
                <span className="badge badge-warning">Fallback Report</span>
              )}
            </div>
            <div className="text-xs text-base-content/50 mb-4">
              Generated: {new Date(report.created_at).toLocaleString()}
            </div>
            {/* Render HTML report — content is sanitized server-side */}
            <div
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: report.html_content }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
