"use client";

interface FinancialsTabProps {
  foundedYear: number | null;
  headquarters: string | null;
  employeeCount: number | null;
  annualRevenue: number | null;
  fundingTotal: number | null;
  marketCap: number | null;
  companyWebsite: string | null;
  linkedinUrl: string | null;
  ticker: string | null;
  industry: string | null;
}

/**
 * Formats a number with commas as thousands separators.
 */
function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

/**
 * Formats a monetary value with appropriate unit suffix.
 * - >= 1 trillion: "X.XXt"
 * - >= 1 billion: "X.XXB"
 * - >= 1 million: "X.XXM"
 * - >= 1 thousand: "X.XXK"
 * - Otherwise: formatted with commas
 */
function formatCurrency(value: number): string {
  const absValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (absValue >= 1_000_000_000_000) {
    return `${sign}$${(absValue / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (absValue >= 1_000_000_000) {
    return `${sign}$${(absValue / 1_000_000_000).toFixed(2)}B`;
  }
  if (absValue >= 1_000_000) {
    return `${sign}$${(absValue / 1_000_000).toFixed(2)}M`;
  }
  if (absValue >= 1_000) {
    return `${sign}$${(absValue / 1_000).toFixed(2)}K`;
  }
  return `${sign}$${formatNumber(absValue)}`;
}

/**
 * FinancialsTab displays extracted financial fields in a structured grid layout.
 * Each field is shown as a label + value pair.
 * Numbers are formatted with commas; revenue/market_cap use appropriate units.
 * Null values show "N/A". URLs are rendered as clickable links.
 *
 * Validates: Requirements 7.3
 */
export default function FinancialsTab({
  foundedYear,
  headquarters,
  employeeCount,
  annualRevenue,
  fundingTotal,
  marketCap,
  companyWebsite,
  linkedinUrl,
  ticker,
  industry,
}: FinancialsTabProps) {
  const fields: { label: string; value: React.ReactNode }[] = [
    {
      label: "Industry",
      value: industry ?? "N/A",
    },
    {
      label: "Founded Year",
      value: foundedYear !== null ? String(foundedYear) : "N/A",
    },
    {
      label: "Headquarters",
      value: headquarters ?? "N/A",
    },
    {
      label: "Employees",
      value: employeeCount !== null ? formatNumber(employeeCount) : "N/A",
    },
    {
      label: "Annual Revenue",
      value: annualRevenue !== null ? formatCurrency(annualRevenue) : "N/A",
    },
    {
      label: "Total Funding",
      value: fundingTotal !== null ? formatCurrency(fundingTotal) : "N/A",
    },
    {
      label: "Market Cap",
      value: marketCap !== null ? formatCurrency(marketCap) : "N/A",
    },
    {
      label: "Ticker",
      value: ticker ?? "N/A",
    },
    {
      label: "Website",
      value: companyWebsite ? (
        <a
          href={companyWebsite}
          target="_blank"
          rel="noopener noreferrer"
          className="link link-primary truncate block"
        >
          {companyWebsite}
        </a>
      ) : (
        "N/A"
      ),
    },
    {
      label: "LinkedIn",
      value: linkedinUrl ? (
        <a
          href={linkedinUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="link link-primary truncate block"
        >
          {linkedinUrl}
        </a>
      ) : (
        "N/A"
      ),
    },
  ];

  return (
    <div className="p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {fields.map((field) => (
          <div
            key={field.label}
            className="card bg-base-200 p-4 space-y-1"
          >
            <span className="text-xs font-semibold uppercase tracking-wide text-base-content/60">
              {field.label}
            </span>
            <span className="text-base font-medium text-base-content">
              {field.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
