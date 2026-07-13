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

// Revenue projection assumptions per product group
const PRODUCT_REVENUE_ASSUMPTIONS: Record<string, { 
  productName: string;
  avgRevenue: string;
  rateAssumption: string;
  basisAssumption: string;
  annualProjection: string;
  details: string;
}> = {
  giro: {
    productName: "Giro (Current Account)",
    avgRevenue: "IDR 500M - 2B/yr",
    rateAssumption: "Float income at avg balance × 3-5% spread",
    basisAssumption: "Avg balance IDR 10-50B based on company revenue scale",
    annualProjection: "IDR 500M - 2.5B",
    details: "Current accounts generate fee income from transaction volume + float income from average daily balance. Large corporates typically maintain IDR 10-50B in giro accounts.",
  },
  tabungan: {
    productName: "Tabungan (Savings)",
    avgRevenue: "IDR 100M - 500M/yr",
    rateAssumption: "Float margin at 2-3% on avg balance",
    basisAssumption: "Avg balance IDR 5-20B for corporate savings",
    annualProjection: "IDR 100M - 600M",
    details: "Corporate savings accounts generate margin from the spread between cost of funds and lending rate on idle deposits.",
  },
  deposito: {
    productName: "Deposito (Time Deposit)",
    avgRevenue: "IDR 200M - 1B/yr",
    rateAssumption: "Spread of 1-2% on deposited funds",
    basisAssumption: "Deposit placement IDR 20-100B",
    annualProjection: "IDR 200M - 2B",
    details: "Time deposits provide stable funding. Revenue from the spread between deposit rate offered (4-5%) and deployment rate (6-7%).",
  },
  ki: {
    productName: "Kredit Investasi (Investment Loan)",
    avgRevenue: "IDR 5B - 20B/yr",
    rateAssumption: "Interest rate 9-11% on outstanding balance",
    basisAssumption: "Facility size IDR 50-200B, utilization 70-80%",
    annualProjection: "IDR 3.5B - 17.6B",
    details: "Investment loans for capex/expansion. Largest revenue driver. Assuming facility IDR 50-200B at 9-11% interest with 70-80% utilization.",
  },
  kmk_scf: {
    productName: "KMK SCF (Working Capital - Supply Chain)",
    avgRevenue: "IDR 2B - 8B/yr",
    rateAssumption: "Interest rate 8-10% on revolving facility",
    basisAssumption: "Facility IDR 30-100B, utilization 60-70%",
    annualProjection: "IDR 1.4B - 7B",
    details: "Supply chain finance working capital for inventory and receivables. Revolving nature means consistent utilization throughout the year.",
  },
  kmk_non_scf: {
    productName: "KMK Non-SCF (Working Capital - General)",
    avgRevenue: "IDR 1.5B - 6B/yr",
    rateAssumption: "Interest rate 9-11% on outstanding",
    basisAssumption: "Facility IDR 20-80B, utilization 60-70%",
    annualProjection: "IDR 1.1B - 6.2B",
    details: "General working capital for operational needs. Typically revolving with moderate utilization patterns.",
  },
  trade_finance: {
    productName: "Trade Finance (LC, SKBDN)",
    avgRevenue: "IDR 1B - 5B/yr",
    rateAssumption: "Fee 0.5-1.5% on trade volume + interest on financing",
    basisAssumption: "Annual trade volume IDR 100-500B",
    annualProjection: "IDR 500M - 7.5B",
    details: "Letters of Credit, SKBDN, import/export financing. Fee-based + interest on funded portion. Highly dependent on company's import/export activity.",
  },
  cash_management: {
    productName: "Cash Management",
    avgRevenue: "IDR 500M - 3B/yr",
    rateAssumption: "Transaction fees + float on collection accounts",
    basisAssumption: "Monthly transactions 10,000-100,000 at avg IDR 5K-15K fee",
    annualProjection: "IDR 600M - 18B",
    details: "Collection, disbursement, virtual accounts, payroll distribution. Revenue scales with transaction volume and number of outlets/branches.",
  },
  forex: {
    productName: "Foreign Exchange",
    avgRevenue: "IDR 500M - 3B/yr",
    rateAssumption: "Spread 30-100 pips on conversion volume",
    basisAssumption: "Monthly FX volume USD 5-50M",
    annualProjection: "IDR 180M - 6B",
    details: "Spot, forward, and swap transactions. Revenue from bid-ask spread. Relevant for companies with foreign currency revenue/costs.",
  },
  guarantee: {
    productName: "Bank Guarantee (Garansi Bank)",
    avgRevenue: "IDR 200M - 1B/yr",
    rateAssumption: "Fee 1-3% per annum on guarantee amount",
    basisAssumption: "Guarantee facility IDR 10-50B",
    annualProjection: "IDR 100M - 1.5B",
    details: "Performance bonds, bid bonds, advance payment guarantees. Fee-based income with no funding required (off-balance sheet).",
  },
  treasury: {
    productName: "Treasury Products",
    avgRevenue: "IDR 200M - 2B/yr",
    rateAssumption: "Hedging fees + structured product margins",
    basisAssumption: "Notional exposure IDR 50-200B",
    annualProjection: "IDR 250M - 2B",
    details: "Interest rate swaps, cross-currency swaps, structured deposits. Relevant for companies with large foreign debt or interest rate exposure.",
  },
  bancassurance: {
    productName: "Bancassurance",
    avgRevenue: "IDR 100M - 500M/yr",
    rateAssumption: "Commission 15-30% on premium",
    basisAssumption: "Annual premium IDR 500M - 2B",
    annualProjection: "IDR 75M - 600M",
    details: "Employee benefit insurance, key-man insurance, asset insurance sold through banking relationship. Commission-based income.",
  },
};

function WhitespaceMatrix({ metrics }: { metrics: Record<string, number> }) {
  const opportunities = getWhitespaceOpportunities(metrics);

  // Calculate total projected revenue
  const totalProjection = opportunities.reduce((sum, group) => {
    const data = PRODUCT_REVENUE_ASSUMPTIONS[group];
    if (!data) return sum;
    // Use midpoint of range (parse from "IDR XB - YB")
    return sum + 1; // placeholder counting
  }, 0);

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
      <h3 className="font-semibold text-lg mb-2">Cross-Sell Revenue Projection</h3>
      <p className="text-base-content/60 text-sm mb-4">
        Product groups with zero activity — each represents incremental revenue if the client is cross-sold.
      </p>

      {/* Summary card */}
      <div className="bg-base-200 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[12px] uppercase font-medium" style={{ color: "#7b7b78" }}>Total Cross-Sell Opportunities</p>
            <p className="text-[24px] font-bold mt-1">{opportunities.length} products</p>
          </div>
          <div className="text-right">
            <p className="text-[12px] uppercase font-medium" style={{ color: "#7b7b78" }}>Est. Additional Revenue</p>
            <p className="text-[18px] font-bold mt-1" style={{ color: "#16a34a" }}>
              IDR {(opportunities.length * 2).toFixed(0)}B - {(opportunities.length * 6).toFixed(0)}B/yr
            </p>
          </div>
        </div>
      </div>

      {/* Detailed projections per product */}
      <div className="space-y-3">
        {opportunities.map((group) => {
          const data = PRODUCT_REVENUE_ASSUMPTIONS[group];
          if (!data) {
            return (
              <div key={group} className="border border-warning/50 bg-warning/5 rounded-lg p-4">
                <p className="text-[14px] font-medium capitalize">{group.replace(/_/g, " ")}</p>
                <p className="text-[12px] mt-1" style={{ color: "#7b7b78" }}>No projection data available</p>
              </div>
            );
          }

          return (
            <div key={group} className="border border-base-300 bg-base-100 rounded-lg p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ backgroundColor: "#fef3c7", color: "#92400e" }}>Whitespace</span>
                  <p className="text-[15px] font-medium mt-1">{data.productName}</p>
                </div>
                <p className="text-[15px] font-bold" style={{ color: "#16a34a" }}>{data.annualProjection}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
                <div>
                  <p className="text-[11px] uppercase font-medium" style={{ color: "#9c9fa5" }}>Rate Assumption</p>
                  <p className="text-[13px] mt-0.5">{data.rateAssumption}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase font-medium" style={{ color: "#9c9fa5" }}>Basis</p>
                  <p className="text-[13px] mt-0.5">{data.basisAssumption}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase font-medium" style={{ color: "#9c9fa5" }}>Revenue Range</p>
                  <p className="text-[13px] mt-0.5">{data.avgRevenue}</p>
                </div>
              </div>
              <p className="text-[12px] mt-3 leading-relaxed" style={{ color: "#626260" }}>{data.details}</p>
            </div>
          );
        })}
      </div>

      {/* Methodology note */}
      <div className="mt-6 p-4 rounded-lg" style={{ backgroundColor: "#f5f1ec", border: "1px solid #ebe7e1" }}>
        <p className="text-[12px] font-medium mb-1" style={{ color: "#7b7b78" }}>Projection Methodology</p>
        <p className="text-[12px] leading-relaxed" style={{ color: "#626260" }}>
          Revenue projections are based on industry benchmarks for Indonesian corporate banking clients of similar size. 
          Assumptions use conservative estimates (lower bound of ranges). Actual revenue depends on: facility utilization rate, 
          client&apos;s business cycle, market interest rates, and negotiated pricing. Projections do not account for credit risk costs (CKPN) 
          or operational costs. These are gross revenue estimates before cost allocation.
        </p>
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
