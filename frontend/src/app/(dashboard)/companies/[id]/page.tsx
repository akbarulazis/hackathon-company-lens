"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get } from "@/lib/api";
import PortfolioTab from "@/components/portfolio/PortfolioTab";
import ProfileTab from "@/components/dossier/ProfileTab";
import FinancialsTab from "@/components/dossier/FinancialsTab";
import ScoresTab from "@/components/dossier/ScoresTab";
import DocumentUpload from "@/components/dossier/DocumentUpload";
import RelationshipGraph from "@/components/graph/RelationshipGraph";
import ChatSidebar from "@/components/ChatSidebar";

// --- Types ---

interface CompanyDetail {
  id: number;
  name: string;
  status: string;
  client_status: string;
  industry: string | null;
  acquisition_brief: string | null;
  founded_year: number | null;
  headquarters: string | null;
  employee_count: number | null;
  annual_revenue: number | null;
  funding_total: number | null;
  market_cap: number | null;
  company_website: string | null;
  linkedin_url: string | null;
  ticker: string | null;
  overall_score: number | null;
  financial_health: number | null;
  business_risk: number | null;
  growth_potential: number | null;
  product_fit: number | null;
  relationship_accessibility: number | null;
  financial_health_insight: string | null;
  business_risk_insight: string | null;
  growth_potential_insight: string | null;
  product_fit_insight: string | null;
  relationship_accessibility_insight: string | null;
  overall_insight: string | null;
  revenue_projection: {
    estimated_loan_size: string;
    estimated_annual_interest_income: string;
    estimated_fee_income: string;
    estimated_total_annual_revenue: string;
    product_mix: string;
    assumptions: string;
    payback_assessment: string;
  } | null;
}

type TabName = "Profile" | "Financials" | "Scores" | "Portfolio" | "Connections";

const TABS: TabName[] = ["Profile", "Financials", "Scores", "Portfolio", "Connections"];

// ScoresTab is imported from @/components/dossier/ScoresTab

// --- Progress Indicator with Live Log ---

function PipelineProgress({ status, companyId }: { status: string; companyId: number }) {
  const stages = ["pending", "researching", "profiling", "scoring"];
  const currentIndex = stages.indexOf(status);
  const queryClient = useQueryClient();
  const [startTime] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [logs, setLogs] = useState<{ time: string; message: string; status: string }[]>([
    { time: new Date().toLocaleTimeString(), message: "Research job queued", status: "pending" },
  ]);

  // Elapsed time counter
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  // Poll company status every 3 seconds to update progress
  const { data: latestData } = useQuery({
    queryKey: ["company-poll", companyId],
    queryFn: () => get<{ status: string; name: string }>(`/companies/${companyId}`),
    refetchInterval: 3000,
    enabled: status !== "ready" && status !== "failed",
  });

  // When polled status changes, add a log entry and invalidate main query
  useEffect(() => {
    if (!latestData) return;
    const newStatus = latestData.status;
    
    setLogs((prev) => {
      const lastLog = prev[prev.length - 1];
      if (lastLog?.status === newStatus) return prev;
      
      const messages: Record<string, string> = {
        researching: "🔍 Searching web sources via Tavily API...",
        profiling: "📝 Generating acquisition brief with GPT-4o-mini...",
        scoring: "📊 Scoring company across 5 dimensions...",
        ready: "✅ Research complete! Loading dossier...",
        failed: "❌ Research failed. Check the logs for details.",
      };

      return [
        ...prev,
        {
          time: new Date().toLocaleTimeString(),
          message: messages[newStatus] || `Status changed to: ${newStatus}`,
          status: newStatus,
        },
      ];
    });

    if (newStatus === "ready" || newStatus === "failed") {
      // Invalidate the main company query to reload the full dossier
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["company", companyId] });
      }, 1000);
    }
  }, [latestData, companyId, queryClient]);

  const displayStatus = latestData?.status || status;
  const displayIndex = stages.indexOf(displayStatus);

  return (
    <div className="max-w-xl mx-auto py-12 space-y-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-2">
          {displayStatus !== "ready" && displayStatus !== "failed" && (
            <svg className="animate-spin h-5 w-5 text-primary" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          <p className="text-lg font-medium">Research in progress</p>
        </div>
        <p className="text-[13px]" style={{ color: "#626260" }}>
          Elapsed: <span className="font-mono font-medium" style={{ color: "#111" }}>{formatElapsed(elapsed)}</span>
          {" · "}Typically takes 2–5 minutes
        </p>
      </div>

      {/* Steps */}
      <div className="flex items-center justify-center gap-2">
        {stages.map((stage, idx) => (
          <div key={stage} className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium"
              style={{
                backgroundColor: idx <= displayIndex ? "#111111" : "#ebe7e1",
                color: idx <= displayIndex ? "#ffffff" : "#7b7b78",
              }}
            >
              {idx < displayIndex ? "✓" : idx + 1}
            </div>
            <span className="text-[12px]" style={{ color: idx <= displayIndex ? "#111111" : "#9c9fa5" }}>
              {stage.charAt(0).toUpperCase() + stage.slice(1)}
            </span>
            {idx < stages.length - 1 && (
              <div className="w-8 h-px" style={{ backgroundColor: idx < displayIndex ? "#111111" : "#d3cec6" }} />
            )}
          </div>
        ))}
      </div>

      {/* Live Log Panel */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{ backgroundColor: "#1a1a1a", borderColor: "#333" }}
      >
        <div className="px-4 py-2 border-b" style={{ borderColor: "#333", backgroundColor: "#222" }}>
          <span className="text-[12px] font-medium" style={{ color: "#9c9fa5" }}>
            Research Log
          </span>
        </div>
        <div className="p-4 max-h-[240px] overflow-y-auto space-y-2 font-mono">
          {logs.map((log, idx) => (
            <div key={idx} className="flex gap-3 text-[12px]">
              <span style={{ color: "#626260", flexShrink: 0 }}>{log.time}</span>
              <span
                style={{
                  color:
                    log.status === "ready" ? "#4ade80" :
                    log.status === "failed" ? "#f87171" :
                    "#e5e5e5",
                }}
              >
                {log.message}
              </span>
            </div>
          ))}
          {displayStatus !== "ready" && displayStatus !== "failed" && (
            <div className="flex gap-3 text-[12px]">
              <span style={{ color: "#626260" }}>{new Date().toLocaleTimeString()}</span>
              <span className="animate-pulse" style={{ color: "#ff5600" }}>● Processing...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Main Page ---

export default function CompanyDossierPage({
  params,
}: {
  params: { id: string };
}) {
  const companyId = parseInt(params.id, 10);
  const [activeTab, setActiveTab] = useState<TabName>("Profile");

  const {
    data: company,
    isLoading,
    error,
  } = useQuery<CompanyDetail>({
    queryKey: ["company", companyId],
    queryFn: () => get<CompanyDetail>(`/companies/${companyId}`),
    enabled: !isNaN(companyId),
  });

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      </div>
    );
  }

  if (error || !company) {
    return (
      <div className="container mx-auto p-6">
        <div className="alert alert-error">
          <span>Failed to load company details.</span>
        </div>
      </div>
    );
  }

  // Show progress indicator if status is not "ready"
  if (company.status !== "ready") {
    return (
      <div className="p-6 md:p-8">
        <h1 className="text-2xl font-medium mb-2" style={{ letterSpacing: "-0.5px" }}>{company.name}</h1>
        <PipelineProgress status={company.status} companyId={companyId} />
      </div>
    );
  }

  // Render active tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case "Profile":
        return (
          <div className="space-y-6">
            <ProfileTab acquisitionBrief={company.acquisition_brief} />
            <DocumentUpload companyId={companyId} />
          </div>
        );
      case "Financials":
        return (
          <FinancialsTab
            foundedYear={company.founded_year}
            headquarters={company.headquarters}
            employeeCount={company.employee_count}
            annualRevenue={company.annual_revenue}
            fundingTotal={company.funding_total}
            marketCap={company.market_cap}
            companyWebsite={company.company_website}
            linkedinUrl={company.linkedin_url}
            ticker={company.ticker}
            industry={company.industry}
          />
        );
      case "Scores":
        return (
          <ScoresTab
            overallScore={company.overall_score}
            financialHealth={company.financial_health}
            businessRisk={company.business_risk}
            growthPotential={company.growth_potential}
            productFit={company.product_fit}
            relationshipAccessibility={company.relationship_accessibility}
            financialHealthInsight={company.financial_health_insight}
            businessRiskInsight={company.business_risk_insight}
            growthPotentialInsight={company.growth_potential_insight}
            productFitInsight={company.product_fit_insight}
            relationshipAccessibilityInsight={company.relationship_accessibility_insight}
            overallInsight={company.overall_insight}
            revenueProjection={company.revenue_projection}
          />
        );
      case "Portfolio":
        return <PortfolioTab companyId={companyId} clientStatus={company.client_status} />;
      case "Connections":
        return <RelationshipGraph companyId={companyId} />;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Page Header */}
      <h1 className="text-2xl font-bold">{company.name}</h1>

      {/* Tabbed Interface */}
      <div role="tablist" className="tabs tabs-bordered">
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            className={`tab ${activeTab === tab ? "tab-active" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[200px]">{renderTabContent()}</div>
    </div>
  );
}
