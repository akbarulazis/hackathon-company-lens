"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useWorkspaceDetail,
  useWorkspaceAnalytics,
  useRemoveCompanyFromWorkspace,
  useAddCompanyToWorkspace,
  CompanyInWorkspace,
  CompanyAnalytics,
  ScoreHistoryPoint,
} from "@/hooks/useWorkspaces";
import { get } from "@/lib/api";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
  ResponsiveContainer,
} from "recharts";

const DIMENSION_LABELS: Record<string, string> = {
  financial_health: "Financial Health",
  business_risk: "Business Risk",
  growth_potential: "Growth Potential",
  product_fit: "Product Fit",
  relationship_accessibility: "Relationship Access",
};

const CHART_COLORS = [
  "#4f46e5", // indigo
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
];

interface SearchResult {
  id: number;
  name: string;
  client_status: string;
  industry: string | null;
  overall_score: number | null;
}

function CompanyCard({
  company,
  onRemove,
  isRemoving,
}: {
  company: CompanyInWorkspace;
  onRemove: () => void;
  isRemoving: boolean;
}) {
  const scoreBadgeColor = (score: number | null) => {
    if (score === null) return "badge-ghost";
    if (score <= 1) return "badge-error";
    if (score <= 2) return "badge-warning";
    if (score <= 3) return "badge-info";
    if (score <= 4) return "badge-accent";
    return "badge-success";
  };

  return (
    <div className="card bg-base-100 shadow-sm border border-base-200">
      <div className="card-body p-4">
        <div className="flex items-start justify-between">
          <div>
            <Link
              href={`/companies/${company.id}`}
              className="font-semibold link link-hover"
            >
              {company.name}
            </Link>
            <div className="flex gap-2 mt-1 flex-wrap">
              <span className="badge badge-sm badge-outline">{company.status}</span>
              <span className="badge badge-sm badge-outline">{company.client_status}</span>
              {company.overall_score !== null && (
                <span className={`badge badge-sm ${scoreBadgeColor(company.overall_score)}`}>
                  Score: {company.overall_score?.toFixed(1) ?? "—"}
                </span>
              )}
            </div>
          </div>
          <button
            className="btn btn-xs btn-ghost text-error"
            onClick={onRemove}
            disabled={isRemoving}
            title="Remove from workspace"
          >
            {isRemoving ? (
              <span className="loading loading-spinner loading-xs"></span>
            ) : (
              "✕"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function CompanySearchAdd({
  workspaceId,
  existingCompanyIds,
}: {
  workspaceId: number;
  existingCompanyIds: number[];
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [canResearch, setCanResearch] = useState(false);
  const [isResearching, setIsResearching] = useState(false);
  const [researchMsg, setResearchMsg] = useState<string | null>(null);
  const addMutation = useAddCompanyToWorkspace(workspaceId);

  const handleSearch = async (value: string) => {
    setQuery(value);
    setCanResearch(false);
    setResearchMsg(null);
    if (value.length < 2) {
      setResults([]);
      return;
    }
    setIsSearching(true);
    try {
      const data = await get<{ results: SearchResult[]; can_research: boolean }>(`/companies/search?q=${encodeURIComponent(value)}`);
      const filtered = (data.results || []).filter((r) => !existingCompanyIds.includes(r.id));
      setResults(filtered);
      setCanResearch(data.can_research && filtered.length === 0);
    } catch {
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleAdd = async (companyId: number) => {
    await addMutation.mutateAsync(companyId);
    setQuery("");
    setResults([]);
  };

  const handleResearch = async () => {
    if (!query.trim() || isResearching) return;
    setIsResearching(true);
    setResearchMsg(null);
    try {
      const { post } = await import("@/lib/api");
      await post("/companies/research", { company_name: query.trim() });
      setResearchMsg(`Research started for "${query.trim()}". Check progress in the navbar.`);
      setQuery("");
      setResults([]);
      setCanResearch(false);
    } catch (err: unknown) {
      setResearchMsg(err instanceof Error ? err.message : "Failed to start research.");
    } finally {
      setIsResearching(false);
    }
  };

  return (
    <div className="relative">
      <input
        type="text"
        className="w-full px-3 py-2 text-[14px] rounded-lg border border-base-300 bg-base-100 focus:outline-none focus:border-primary/40 transition-colors"
        placeholder="Search or research a company..."
        value={query}
        onChange={(e) => handleSearch(e.target.value)}
      />
      {isSearching && (
        <span className="loading loading-spinner loading-xs absolute right-3 top-2.5"></span>
      )}
      {addMutation.error && (
        <p className="text-error text-xs mt-1">{addMutation.error.message}</p>
      )}
      {researchMsg && (
        <p className="text-sm mt-2 px-1" style={{ color: isResearching ? "#626260" : "#16a34a" }}>
          {researchMsg}
        </p>
      )}
      {/* Results dropdown */}
      {results.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-base-100 border border-base-300 rounded-lg shadow-lg max-h-52 overflow-y-auto">
          {results.map((r) => (
            <li key={r.id}>
              <button
                className="w-full text-left px-3 py-2 text-[13px] hover:bg-base-200 flex items-center justify-between transition-colors"
                onClick={() => handleAdd(r.id)}
                disabled={addMutation.isPending}
              >
                <span className="font-medium">{r.name}</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full" style={{
                  backgroundColor: r.client_status === "client" ? "#dcfce7" : r.client_status === "prospect" ? "#dbeafe" : "#f3f4f6",
                  color: r.client_status === "client" ? "#166534" : r.client_status === "prospect" ? "#1e40af" : "#374151",
                }}>
                  {r.client_status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* Research new company option */}
      {canResearch && query.length >= 2 && (
        <div className="mt-2 p-3 bg-base-100 border border-base-300 rounded-lg">
          <p className="text-[13px] text-secondary mb-2">
            No company found for &ldquo;{query}&rdquo;
          </p>
          <button
            className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg"
            onClick={handleResearch}
            disabled={isResearching}
          >
            {isResearching ? "Researching..." : `Research "${query.trim()}" with AI`}
          </button>
        </div>
      )}
    </div>
  );
}

function Leaderboard({ companies }: { companies: CompanyAnalytics[] }) {
  const sorted = [...companies].sort((a, b) => (b.overall_score ?? 0) - (a.overall_score ?? 0));

  return (
    <div className="overflow-x-auto">
      <table className="table table-sm">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Company</th>
            <th>Overall Score</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((company, idx) => (
            <tr key={company.id}>
              <td className="font-bold">{idx + 1}</td>
              <td>{company.name}</td>
              <td>
                <span className="badge badge-sm badge-primary">
                  {company.overall_score?.toFixed(1) ?? "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComparisonRadarChart({ companies }: { companies: CompanyAnalytics[] }) {
  const dimensions = Object.keys(DIMENSION_LABELS);
  const data = dimensions.map((dim) => {
    const point: Record<string, string | number> = { dimension: DIMENSION_LABELS[dim] };
    companies.forEach((c) => {
      point[c.name] = ((c as any)[dim] ?? 0);
    });
    return point;
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
        <PolarRadiusAxis domain={[1, 5]} tickCount={5} />
        {companies.map((c, idx) => (
          <Radar
            key={c.id}
            name={c.name}
            dataKey={c.name}
            stroke={CHART_COLORS[idx % CHART_COLORS.length]}
            fill={CHART_COLORS[idx % CHART_COLORS.length]}
            fillOpacity={0.15}
          />
        ))}
        <Legend />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function ComparisonBarChart({ companies }: { companies: CompanyAnalytics[] }) {
  const dimensions = Object.keys(DIMENSION_LABELS);
  const data = dimensions.map((dim) => {
    const point: Record<string, string | number> = { dimension: DIMENSION_LABELS[dim] };
    companies.forEach((c) => {
      point[c.name] = ((c as any)[dim] ?? 0);
    });
    return point;
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="dimension" tick={{ fontSize: 10 }} />
        <YAxis domain={[1, 5]} tickCount={5} />
        <Tooltip />
        <Legend />
        {companies.map((c, idx) => (
          <Bar
            key={c.id}
            dataKey={c.name}
            fill={CHART_COLORS[idx % CHART_COLORS.length]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function ScoreHistoryChart({
  scoreHistory,
}: {
  scoreHistory: Record<string, ScoreHistoryPoint[]>;
}) {
  // Flatten data for line chart — show overall_score over time per company
  const companyNames = Object.keys(scoreHistory);
  const hasEnoughData = companyNames.some(
    (name) => scoreHistory[name].length >= 2
  );

  if (!hasEnoughData) {
    return (
      <div className="alert alert-info text-sm">
        <span>Score history requires at least 2 data points to display trend charts.</span>
      </div>
    );
  }

  // Build unified timeline across all companies
  const allDates = new Set<string>();
  companyNames.forEach((name) => {
    scoreHistory[name].forEach((point) => allDates.add(point.scored_at));
  });
  const sortedDates = Array.from(allDates).sort();

  const data = sortedDates.map((date) => {
    const point: Record<string, string | number | null> = { date: new Date(date).toLocaleDateString() };
    companyNames.forEach((name) => {
      const match = scoreHistory[name].find((p) => p.scored_at === date);
      point[name] = match ? match.overall_score : null;
    });
    return point;
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
        <YAxis domain={[1, 5]} tickCount={5} />
        <Tooltip />
        <Legend />
        {companyNames.map((name, idx) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={CHART_COLORS[idx % CHART_COLORS.length]}
            connectNulls
            dot
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function WorkspaceDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const workspaceId = parseInt(params.id, 10);
  const { data: workspace, isLoading, error, refetch } = useWorkspaceDetail(workspaceId);
  const { data: analytics } = useWorkspaceAnalytics(workspaceId);
  const removeMutation = useRemoveCompanyFromWorkspace(workspaceId);
  const addMutation = useAddCompanyToWorkspace(workspaceId);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [isResearching, setIsResearching] = useState(false);
  const [researchMsg, setResearchMsg] = useState<string | null>(null);

  const handleRemove = async (companyId: number) => {
    setRemovingId(companyId);
    try {
      await removeMutation.mutateAsync(companyId);
    } finally {
      setRemovingId(null);
    }
  };

  const handleResearch = async () => {
    if (!companyName.trim()) return;
    setIsResearching(true);
    setResearchMsg(null);

    try {
      const { post } = await import("@/lib/api");
      const searchTerm = companyName.trim();

      // First check if company already exists with an EXACT name match
      const searchData = await get<{ results: SearchResult[]; can_research: boolean }>(`/companies/search?q=${encodeURIComponent(searchTerm)}`);

      // Only consider it "found" if the name matches closely (case-insensitive exact match)
      const exactMatch = searchData.results?.find(
        (r) => r.name.toLowerCase() === searchTerm.toLowerCase()
      );

      if (exactMatch) {
        // Company exists with exact name — add it to workspace directly
        try {
          await addMutation.mutateAsync(exactMatch.id);
          setResearchMsg(`"${exactMatch.name}" found and added to workspace.`);
        } catch {
          setResearchMsg(`"${exactMatch.name}" already exists — check your companies below.`);
        }
      } else {
        // No exact match — start fresh research (even if fuzzy results exist)
        const res = await post<{ id: number; name: string }>("/companies/research", { company_name: searchTerm });
        // Add to workspace
        try {
          await addMutation.mutateAsync(res.id);
        } catch {
          // May fail if limit reached or already there
        }
        setResearchMsg(`Research started for "${searchTerm}". Watch the progress below.`);
      }

      setCompanyName("");
      refetch();
    } catch (err: unknown) {
      setResearchMsg(err instanceof Error ? err.message : "Failed to research company.");
    } finally {
      setIsResearching(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 flex justify-center">
        <span className="loading loading-spinner loading-lg"></span>
      </div>
    );
  }

  if (error || !workspace) {
    return (
      <div className="p-8">
        <div className="bg-error/10 border border-error/20 rounded-lg p-4 text-error text-sm">
          Failed to load workspace.
        </div>
      </div>
    );
  }

  const readyCompanies = workspace.companies.filter((c) => c.status === "ready");
  const hasComparisonData = analytics && analytics.companies.length >= 2;

  return (
    <div className="p-6 md:p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link href="/workspaces" className="text-[13px] text-secondary hover:text-base-content">
            ← Back to Workspaces
          </Link>
          <h1 className="text-2xl font-medium mt-1" style={{ letterSpacing: "-0.5px" }}>
            {workspace.name}
          </h1>
        </div>
        <div className="flex gap-2">
          <Link href={`/workspaces/${workspaceId}/compare`} className="btn btn-sm btn-ghost border border-base-300 rounded-lg text-[13px]">
            Compare
          </Link>
          <Link href={`/workspaces/${workspaceId}/chat`} className="btn btn-sm btn-ghost border border-base-300 rounded-lg text-[13px]">
            Chat
          </Link>
        </div>
      </div>

      {/* Research Input */}
      <div className="bg-base-100 rounded-xl border border-base-300 p-5">
        <h2 className="text-[14px] font-medium mb-3">Add Company</h2>
        <div className="flex gap-3">
          <input
            type="text"
            className="flex-1 px-3 py-2 text-[14px] rounded-lg border border-base-300 bg-base-100 focus:outline-none focus:border-primary/40 transition-colors"
            placeholder="Enter company name (e.g. PT Bank BCA, Pertamina, Telkom)"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleResearch()}
            disabled={isResearching || workspace.company_count >= workspace.company_limit}
          />
          <button
            onClick={handleResearch}
            disabled={!companyName.trim() || isResearching || workspace.company_count >= workspace.company_limit}
            className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg px-5"
          >
            {isResearching ? "Searching..." : "Research"}
          </button>
        </div>
        {workspace.company_count >= workspace.company_limit && (
          <p className="text-[12px] text-error mt-2">Workspace limit reached ({workspace.company_limit} companies max).</p>
        )}
        {researchMsg && (
          <p className="text-[13px] mt-2" style={{ color: "#16a34a" }}>{researchMsg}</p>
        )}
        <p className="text-[12px] mt-2" style={{ color: "#9c9fa5" }}>
          {workspace.company_count}/{workspace.company_limit} companies · If the company exists it will be added instantly, otherwise AI research starts automatically.
        </p>
      </div>

      {/* Company Cards */}
      {workspace.companies.length > 0 && (
        <section>
          <h2 className="text-[15px] font-medium mb-3">Companies</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {workspace.companies.map((company) => (
              <div
                key={company.id}
                className="bg-base-100 rounded-xl border border-base-300 p-4 relative group"
              >
                {/* Delete button */}
                <button
                  className="absolute top-3 right-3 text-[11px] text-error/50 hover:text-error opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => handleRemove(company.id)}
                  disabled={removingId === company.id}
                  title="Remove from workspace"
                >
                  {removingId === company.id ? "..." : "✕ Remove"}
                </button>

                <Link href={`/companies/${company.id}`} className="block">
                  <h3 className="text-[15px] font-medium text-base-content hover:underline pr-16">
                    {company.name}
                  </h3>
                </Link>

                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  {/* Status badge */}
                  <span
                    className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                    style={{
                      backgroundColor:
                        company.status === "ready" ? "#dcfce7" :
                        company.status === "failed" ? "#fef2f2" :
                        "#fff7ed",
                      color:
                        company.status === "ready" ? "#166534" :
                        company.status === "failed" ? "#b91c1c" :
                        "#9a3412",
                    }}
                  >
                    {company.status === "ready" ? "✓ Ready" :
                     company.status === "failed" ? "✕ Failed" :
                     `⏳ ${company.status}`}
                  </span>

                  {/* Client status */}
                  <span
                    className="text-[11px] px-2 py-0.5 rounded-full"
                    style={{
                      backgroundColor:
                        company.client_status === "client" ? "#dbeafe" :
                        company.client_status === "prospect" ? "#ede9fe" :
                        "#f3f4f6",
                      color:
                        company.client_status === "client" ? "#1e40af" :
                        company.client_status === "prospect" ? "#5b21b6" :
                        "#374151",
                    }}
                  >
                    {company.client_status}
                  </span>

                  {/* Score */}
                  {company.overall_score !== null && (
                    <span className="text-[11px] font-semibold" style={{ color: company.overall_score >= 3.5 ? "#16a34a" : company.overall_score >= 2.5 ? "#ca8a04" : "#dc2626" }}>
                      {company.overall_score?.toFixed(1) ?? "—"}/5.0
                    </span>
                  )}
                </div>

                {company.industry && (
                  <p className="text-[12px] mt-1.5" style={{ color: "#7b7b78" }}>{company.industry}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Analytics — only show if useful */}
      {readyCompanies.length >= 2 && hasComparisonData && (
        <section>
          <h2 className="text-[15px] font-medium mb-3">Analytics</h2>
          <div className="bg-base-100 rounded-xl border border-base-300 p-5 space-y-6">
            <Leaderboard companies={analytics.companies} />
            <ComparisonBarChart companies={analytics.companies} />
            <ComparisonRadarChart companies={analytics.companies} />
          </div>
        </section>
      )}
    </div>
  );
}
