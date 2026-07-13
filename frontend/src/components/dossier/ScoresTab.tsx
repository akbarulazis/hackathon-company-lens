"use client";

import RadarChart from "@/components/charts/RadarChart";
import BarChart from "@/components/charts/BarChart";

// --- Types ---

interface ScoresTabProps {
  overallScore: number | null;
  financialHealth: number | null;
  businessRisk: number | null;
  growthPotential: number | null;
  productFit: number | null;
  relationshipAccessibility: number | null;
  financialHealthInsight?: string | null;
  businessRiskInsight?: string | null;
  growthPotentialInsight?: string | null;
  productFitInsight?: string | null;
  relationshipAccessibilityInsight?: string | null;
  overallInsight?: string | null;
  revenueProjection?: {
    estimated_loan_size: string;
    estimated_annual_interest_income: string;
    estimated_fee_income: string;
    estimated_total_annual_revenue: string;
    product_mix: string;
    assumptions: string;
    payback_assessment: string;
  } | null;
}

interface DimensionInfo {
  key: string;
  label: string;
  score: number | null;
  insight: string;
}

// --- Helpers ---

/** Returns the appropriate badge color class for a score based on color banding */
function getScoreBadgeClass(score: number): string {
  if (score <= 1) return "badge-error"; // red
  if (score <= 2) return "badge-warning"; // orange
  if (score <= 3) return "badge-warning text-yellow-800 bg-yellow-300 border-yellow-300"; // yellow
  if (score <= 4) return "bg-teal-500 border-teal-500 text-white"; // teal
  return "badge-success"; // green
}

/** Returns inline style color for the score badge (for cases where DaisyUI classes aren't enough) */
function getScoreBadgeStyle(score: number): React.CSSProperties {
  if (score <= 1) return { backgroundColor: "#f87272", borderColor: "#f87272", color: "#fff" };
  if (score <= 2) return { backgroundColor: "#fb923c", borderColor: "#fb923c", color: "#fff" };
  if (score <= 3) return { backgroundColor: "#facc15", borderColor: "#facc15", color: "#422006" };
  if (score <= 4) return { backgroundColor: "#2dd4bf", borderColor: "#2dd4bf", color: "#fff" };
  return { backgroundColor: "#36d399", borderColor: "#36d399", color: "#fff" };
}

/** Generate an insight placeholder for each dimension */
function getDimensionInsight(key: string, score: number | null): string {
  if (score === null) return "No score available";
  if (score >= 4) return "Strong performance in this area";
  if (score >= 3) return "Average performance — room for improvement";
  if (score >= 2) return "Below average — warrants further investigation";
  return "Significant concern — high priority for due diligence";
}

// --- Component ---

/**
 * ScoresTab displays the Overall_Score badge with color banding,
 * five Score_Dimension cards, and radar/bar chart visualizations.
 *
 * Requirements: 7.4, 17.1
 */
export default function ScoresTab({
  overallScore,
  financialHealth,
  businessRisk,
  growthPotential,
  productFit,
  relationshipAccessibility,
  financialHealthInsight,
  businessRiskInsight,
  growthPotentialInsight,
  productFitInsight,
  relationshipAccessibilityInsight,
  overallInsight,
  revenueProjection,
}: ScoresTabProps) {
  const dimensions: DimensionInfo[] = [
    {
      key: "financial_health",
      label: "Financial Health",
      score: financialHealth,
      insight: financialHealthInsight || getDimensionInsight("financial_health", financialHealth),
    },
    {
      key: "business_risk",
      label: "Business Risk",
      score: businessRisk,
      insight: businessRiskInsight || getDimensionInsight("business_risk", businessRisk),
    },
    {
      key: "growth_potential",
      label: "Growth Potential",
      score: growthPotential,
      insight: growthPotentialInsight || getDimensionInsight("growth_potential", growthPotential),
    },
    {
      key: "product_fit",
      label: "Product Fit",
      score: productFit,
      insight: productFitInsight || getDimensionInsight("product_fit", productFit),
    },
    {
      key: "relationship_accessibility",
      label: "Relationship Accessibility",
      score: relationshipAccessibility,
      insight: relationshipAccessibilityInsight || getDimensionInsight("relationship_accessibility", relationshipAccessibility),
    },
  ];

  // Prepare chart data (only include dimensions with valid scores)
  const radarData = dimensions
    .filter((d) => d.score !== null)
    .map((d) => ({
      dimension: d.label,
      score: d.score as number,
      fullMark: 5,
    }));

  const barData = dimensions
    .filter((d) => d.score !== null)
    .map((d) => ({
      dimension: d.label,
      score: d.score as number,
    }));

  return (
    <div className="space-y-6 p-4">
      {/* Overall Score Badge */}
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold">Overall Score</h2>
        {overallScore !== null ? (
          <span
            className="badge badge-lg font-bold text-base"
            style={getScoreBadgeStyle(overallScore)}
          >
            {overallScore.toFixed(2)}
          </span>
        ) : (
          <span className="badge badge-ghost badge-lg">N/A</span>
        )}
      </div>

      {/* Overall Insight */}
      {overallInsight && (
        <div className="bg-base-100 rounded-lg border border-base-300 p-4">
          <p className="text-[14px] leading-relaxed" style={{ color: "#333" }}>
            {overallInsight}
          </p>
        </div>
      )}

      {/* Score Dimension Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {dimensions.map((dim) => (
          <div key={dim.key} className="card bg-base-200 shadow-sm">
            <div className="card-body p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="card-title text-sm">{dim.label}</h3>
                {dim.score !== null ? (
                  <span
                    className="badge font-semibold"
                    style={getScoreBadgeStyle(dim.score)}
                  >
                    {dim.score.toFixed(2)}
                  </span>
                ) : (
                  <span className="badge badge-ghost">N/A</span>
                )}
              </div>
              <p className="text-xs text-base-content/70">{dim.insight}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {radarData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Radar Chart */}
          <div className="card bg-base-200 shadow-sm">
            <div className="card-body p-4">
              <h3 className="card-title text-sm mb-2">Score Radar</h3>
              <RadarChart data={radarData} />
            </div>
          </div>

          {/* Bar Chart */}
          <div className="card bg-base-200 shadow-sm">
            <div className="card-body p-4">
              <h3 className="card-title text-sm mb-2">Score Breakdown</h3>
              <BarChart data={barData} useColorBanding />
            </div>
          </div>
        </div>
      )}

      {/* Revenue Projection */}
      {revenueProjection && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-3">💰 Revenue Projection (if acquired as client)</h2>
          <div className="bg-base-100 rounded-xl border border-base-300 p-5 space-y-4">
            {/* Key numbers */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-base-200 rounded-lg p-3">
                <p className="text-[11px] uppercase font-medium" style={{ color: "#7b7b78" }}>Est. Loan Size</p>
                <p className="text-[16px] font-semibold mt-1">{revenueProjection.estimated_loan_size}</p>
              </div>
              <div className="bg-base-200 rounded-lg p-3">
                <p className="text-[11px] uppercase font-medium" style={{ color: "#7b7b78" }}>Interest Income/yr</p>
                <p className="text-[16px] font-semibold mt-1" style={{ color: "#16a34a" }}>{revenueProjection.estimated_annual_interest_income}</p>
              </div>
              <div className="bg-base-200 rounded-lg p-3">
                <p className="text-[11px] uppercase font-medium" style={{ color: "#7b7b78" }}>Fee Income/yr</p>
                <p className="text-[16px] font-semibold mt-1" style={{ color: "#16a34a" }}>{revenueProjection.estimated_fee_income}</p>
              </div>
              <div className="bg-base-200 rounded-lg p-3" style={{ border: "1px solid #d3cec6" }}>
                <p className="text-[11px] uppercase font-medium" style={{ color: "#7b7b78" }}>Total Revenue/yr</p>
                <p className="text-[18px] font-bold mt-1" style={{ color: "#111" }}>{revenueProjection.estimated_total_annual_revenue}</p>
              </div>
            </div>

            {/* Product mix */}
            <div>
              <p className="text-[12px] uppercase font-medium mb-1" style={{ color: "#7b7b78" }}>Recommended Product Mix</p>
              <p className="text-[14px] leading-relaxed">{revenueProjection.product_mix}</p>
            </div>

            {/* Assumptions */}
            <div className="bg-base-200 rounded-lg p-4">
              <p className="text-[12px] uppercase font-medium mb-1" style={{ color: "#7b7b78" }}>Assumptions</p>
              <p className="text-[13px] leading-relaxed" style={{ color: "#626260" }}>{revenueProjection.assumptions}</p>
            </div>

            {/* Payback */}
            <div>
              <p className="text-[12px] uppercase font-medium mb-1" style={{ color: "#7b7b78" }}>Payback Assessment</p>
              <p className="text-[14px] leading-relaxed">{revenueProjection.payback_assessment}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
