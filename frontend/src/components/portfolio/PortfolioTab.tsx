"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  BarChart as RechartsBarChart,
  Bar,
} from "recharts";

// --- Types ---

interface SnapshotData {
  id: number;
  as_of_date: string;
  metrics: Record<string, number>;
}

interface PortfolioResponse {
  company_id: number;
  company_name: string;
  client_status: string;
  latest_snapshot: SnapshotData | null;
  history: SnapshotData[];
  products_held: string[];
  message: string | null;
}

interface PortfolioTabProps {
  companyId: number;
  clientStatus: string;
}

// --- Constants ---

const KPI_KEYS = [
  { key: "profitability", label: "Customer Profitability", prefix: "Rp " },
  { key: "nii_ytd", label: "Net Interest Income YTD", prefix: "Rp " },
  { key: "fee_income_ytd", label: "Fee-Based Income YTD", prefix: "Rp " },
  { key: "loan_outstanding", label: "Total Loan Outstanding", prefix: "Rp " },
  { key: "dpk_balance", label: "Total DPK Balance", prefix: "Rp " },
];

const TREND_METRICS = [
  { key: "profitability", label: "Profitability", color: "#36d399" },
  { key: "nii_ytd", label: "NII YTD", color: "#3abff8" },
  { key: "fee_income_ytd", label: "Fee Income YTD", color: "#f87272" },
  { key: "loan_outstanding", label: "Loan Outstanding", color: "#fbbd23" },
  { key: "dpk_balance", label: "DPK Balance", color: "#a78bfa" },
];

const DPK_CATEGORIES = [
  { key: "giro", label: "Giro", color: "#36d399" },
  { key: "tabungan", label: "Tabungan", color: "#3abff8" },
  { key: "deposito", label: "Deposito", color: "#f87272" },
];

const LOAN_CATEGORIES = [
  { key: "ki", label: "KI", color: "#fbbd23" },
  { key: "kmk_scf", label: "KMK SCF", color: "#a78bfa" },
  { key: "kmk_non_scf", label: "KMK Non-SCF", color: "#f472b6" },
  { key: "others", label: "Others", color: "#94a3b8" },
];

const FEE_CATEGORIES = [
  { key: "trade_finance", label: "Trade Finance" },
  { key: "cash_management", label: "Cash Management" },
  { key: "forex", label: "Forex" },
  { key: "guarantee", label: "Guarantee" },
  { key: "others", label: "Others" },
];

const FEE_COLORS = ["#36d399", "#3abff8", "#f87272", "#fbbd23", "#a78bfa"];

// All known product groups for whitespace analysis
const ALL_PRODUCT_GROUPS = [
  "giro",
  "tabungan",
  "deposito",
  "ki",
  "kmk_scf",
  "kmk_non_scf",
  "trade_finance",
  "cash_management",
  "forex",
  "guarantee",
  "treasury",
  "bancassurance",
];

// --- Utility Functions ---

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000_000) {
    return `Rp ${(value / 1_000_000_000).toFixed(1)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `Rp ${(value / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `Rp ${(value / 1_000).toFixed(1)}K`;
  }
  return `Rp ${value.toLocaleString()}`;
}

function extractMetricValue(
  metrics: Record<string, number>,
  key: string
): number {
  // Try exact key match first, then search for partial match in metric keys
  if (metrics[key] !== undefined) return metrics[key];

  // Search for keys containing the target key name
  const matchingKey = Object.keys(metrics).find(
    (k) => k.toLowerCase().includes(key.toLowerCase())
  );
  return matchingKey ? metrics[matchingKey] : 0;
}

function extractCategoryValues(
  metrics: Record<string, number>,
  categories: { key: string; label: string }[]
): { name: string; value: number }[] {
  return categories
    .map((cat) => ({
      name: cat.label,
      value: extractMetricValue(metrics, cat.key),
    }))
    .filter((item) => item.value > 0);
}

function getWhitespaceOpportunities(
  metrics: Record<string, number>
): string[] {
  return ALL_PRODUCT_GROUPS.filter((group) => {
    // Check if any metric key contains this product group with a non-zero value
    const hasActivity = Object.entries(metrics).some(
      ([key, value]) => key.toLowerCase().includes(group) && value !== 0
    );
    return !hasActivity;
  });
}

// --- Sub-components ---

function KPITiles({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {KPI_KEYS.map(({ key, label }) => {
        const value = extractMetricValue(metrics, key);
        return (
          <div key={key} className="stat bg-base-200 rounded-box p-4">
            <div className="stat-title text-xs">{label}</div>
            <div className="stat-value text-lg">{formatCurrency(value)}</div>
          </div>
        );
      })}
    </div>
  );
}

function TrendLineCharts({ history }: { history: SnapshotData[] }) {
  // Build data array sorted by date
  const sortedHistory = [...history].sort(
    (a, b) => new Date(a.as_of_date).getTime() - new Date(b.as_of_date).getTime()
  );

  const chartData = sortedHistory.map((snapshot) => ({
    date: snapshot.as_of_date,
    ...TREND_METRICS.reduce(
      (acc, metric) => ({
        ...acc,
        [metric.key]: extractMetricValue(snapshot.metrics, metric.key),
      }),
      {} as Record<string, number>
    ),
  }));

  return (
    <div className="space-y-6">
      <h3 className="font-semibold text-lg">Portfolio Trends</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatCurrency(v)} />
          <Tooltip formatter={(value: number) => formatCurrency(value)} />
          <Legend />
          {TREND_METRICS.map((metric) => (
            <Line
              key={metric.key}
              type="monotone"
              dataKey={metric.key}
              stroke={metric.color}
              name={metric.label}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProductMixDonutCharts({ metrics }: { metrics: Record<string, number> }) {
  const dpkData = extractCategoryValues(metrics, DPK_CATEGORIES);
  const loanData = extractCategoryValues(metrics, LOAN_CATEGORIES);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* DPK Split */}
      <div>
        <h4 className="font-medium text-sm mb-2 text-center">DPK Split (Giro / Tabungan / Deposito)</h4>
        {dpkData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={dpkData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {dpkData.map((_, index) => (
                  <Cell key={`dpk-${index}`} fill={DPK_CATEGORIES[index]?.color ?? "#94a3b8"} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-base-content/60 text-sm text-center py-8">No DPK data available</p>
        )}
      </div>

      {/* Loan Split */}
      <div>
        <h4 className="font-medium text-sm mb-2 text-center">Loan Split (KI / KMK SCF / KMK Non-SCF / Others)</h4>
        {loanData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={loanData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {loanData.map((_, index) => (
                  <Cell key={`loan-${index}`} fill={LOAN_CATEGORIES[index]?.color ?? "#94a3b8"} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-base-content/60 text-sm text-center py-8">No loan data available</p>
        )}
      </div>
    </div>
  );
}

function FeeIncomeBarChart({ metrics }: { metrics: Record<string, number> }) {
  const feeData = FEE_CATEGORIES.map((cat) => ({
    category: cat.label,
    value: extractMetricValue(metrics, cat.key),
  })).filter((item) => item.value > 0);

  if (feeData.length === 0) {
    return (
      <div>
        <h3 className="font-semibold text-lg mb-2">Fee Income by Category</h3>
        <p className="text-base-content/60 text-sm py-4">No fee income data available</p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="font-semibold text-lg mb-2">Fee Income by Category</h3>
      <ResponsiveContainer width="100%" height={250}>
        <RechartsBarChart data={feeData} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="category" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatCurrency(v)} />
          <Tooltip formatter={(value: number) => formatCurrency(value)} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {feeData.map((_, index) => (
              <Cell key={`fee-${index}`} fill={FEE_COLORS[index % FEE_COLORS.length]} />
            ))}
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
}

function WhitespaceMatrix({ metrics }: { metrics: Record<string, number> }) {
  const opportunities = getWhitespaceOpportunities(metrics);

  if (opportunities.length === 0) {
    return (
      <div>
        <h3 className="font-semibold text-lg mb-2">Cross-Sell Opportunities</h3>
        <p className="text-base-content/60 text-sm">
          All product groups have activity. No whitespace opportunities detected.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="font-semibold text-lg mb-2">Cross-Sell Opportunities (Whitespace)</h3>
      <p className="text-base-content/60 text-sm mb-4">
        Product groups with zero activity in the latest snapshot — potential cross-sell targets.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {opportunities.map((group) => (
          <div
            key={group}
            className="border border-warning/50 bg-warning/10 rounded-lg p-3 text-center"
          >
            <span className="badge badge-warning badge-sm mb-1">Opportunity</span>
            <p className="text-sm font-medium capitalize">{group.replace(/_/g, " ")}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Main Component ---

export default function PortfolioTab({ companyId, clientStatus }: PortfolioTabProps) {
  // If not a Client, show access message
  if (clientStatus.toLowerCase() !== "client") {
    return (
      <div className="p-6">
        <div className="alert alert-info">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            className="stroke-current shrink-0 w-6 h-6"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>Portfolio data is only available for existing clients.</span>
        </div>
      </div>
    );
  }

  return <PortfolioContent companyId={companyId} />;
}

function PortfolioContent({ companyId }: { companyId: number }) {
  const {
    data: portfolio,
    isLoading,
    error,
  } = useQuery<PortfolioResponse>({
    queryKey: ["portfolio", companyId],
    queryFn: () => get<PortfolioResponse>(`/companies/${companyId}/portfolio`),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <span className="loading loading-spinner loading-lg"></span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="alert alert-error">
          <span>Failed to load portfolio data.</span>
        </div>
      </div>
    );
  }

  // No snapshots available
  if (!portfolio?.latest_snapshot) {
    return (
      <div className="p-6">
        <div className="alert alert-warning">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            className="stroke-current shrink-0 w-6 h-6"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
          <span>No portfolio data has been imported yet.</span>
        </div>
      </div>
    );
  }

  const { latest_snapshot, history } = portfolio;
  const hasMultipleSnapshots = history.length >= 2;

  return (
    <div className="p-4 space-y-8">
      {/* KPI Tiles */}
      <section>
        <h3 className="font-semibold text-lg mb-3">Key Metrics</h3>
        <KPITiles metrics={latest_snapshot.metrics} />
      </section>

      {/* Trend Line Charts (only if ≥2 snapshots) */}
      {hasMultipleSnapshots && (
        <section>
          <TrendLineCharts history={history} />
        </section>
      )}

      {/* Product-Mix Donut Charts */}
      <section>
        <h3 className="font-semibold text-lg mb-3">Product Mix</h3>
        <ProductMixDonutCharts metrics={latest_snapshot.metrics} />
      </section>

      {/* Fee Income Bar Chart */}
      <section>
        <FeeIncomeBarChart metrics={latest_snapshot.metrics} />
      </section>

      {/* Whitespace Matrix */}
      <section>
        <WhitespaceMatrix metrics={latest_snapshot.metrics} />
      </section>
    </div>
  );
}
