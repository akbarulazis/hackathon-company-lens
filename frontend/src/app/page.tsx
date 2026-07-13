import Link from "next/link";

export default function HomePage() {
  return (
    <div style={{ backgroundColor: "#f5f1ec", minHeight: "100vh" }}>
      {/* Nav */}
      <nav
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 32px",
          maxWidth: "1200px",
          margin: "0 auto",
        }}
      >
        <span style={{ fontSize: "20px", fontWeight: 600, color: "#111111", letterSpacing: "-0.5px" }}>
          Company Lens
        </span>
        <div style={{ display: "flex", gap: "12px" }}>
          <Link
            href="/login"
            style={{
              padding: "9px 18px",
              fontSize: "14px",
              fontWeight: 500,
              color: "#111111",
              backgroundColor: "#ffffff",
              border: "1px solid #d3cec6",
              borderRadius: "8px",
              textDecoration: "none",
            }}
          >
            Sign in
          </Link>
          <Link
            href="/register"
            style={{
              padding: "9px 18px",
              fontSize: "14px",
              fontWeight: 500,
              color: "#ffffff",
              backgroundColor: "#111111",
              borderRadius: "8px",
              textDecoration: "none",
            }}
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section style={{ textAlign: "center", padding: "96px 24px 64px", maxWidth: "800px", margin: "0 auto" }}>
        <p style={{ fontSize: "14px", fontWeight: 500, color: "#ff5600", marginBottom: "16px" }}>
          AI-Powered Client Acquisition Intelligence
        </p>
        <h1 style={{ fontSize: "56px", fontWeight: 500, color: "#111111", letterSpacing: "-1.4px", lineHeight: 1.1, margin: "0 0 24px" }}>
          Know every prospect before the first meeting
        </h1>
        <p style={{ fontSize: "18px", color: "#626260", lineHeight: 1.6, maxWidth: "600px", margin: "0 auto 40px" }}>
          Company Lens researches companies automatically using AI — generating acquisition briefs, scoring fit, mapping relationships, and surfacing warm introduction paths to help your team close faster.
        </p>
        <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
          <Link
            href="/register"
            style={{
              padding: "12px 24px",
              fontSize: "15px",
              fontWeight: 500,
              color: "#ffffff",
              backgroundColor: "#111111",
              borderRadius: "8px",
              textDecoration: "none",
            }}
          >
            Start for free
          </Link>
          <Link
            href="/login"
            style={{
              padding: "12px 24px",
              fontSize: "15px",
              fontWeight: 500,
              color: "#111111",
              backgroundColor: "#ffffff",
              border: "1px solid #d3cec6",
              borderRadius: "8px",
              textDecoration: "none",
            }}
          >
            Sign in
          </Link>
        </div>
      </section>

      {/* Features Grid */}
      <section style={{ padding: "64px 24px", maxWidth: "1100px", margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "24px" }}>
          {/* Feature 1 */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6", padding: "32px" }}>
            <div style={{ fontSize: "28px", marginBottom: "16px" }}>🔍</div>
            <h3 style={{ fontSize: "20px", fontWeight: 500, color: "#111111", marginBottom: "8px", letterSpacing: "-0.3px" }}>
              AI Research Pipeline
            </h3>
            <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.6 }}>
              Search a company name — if we don&apos;t know it yet, our AI pipeline researches it in real-time. Tavily web search, URL crawling, and GPT-4o extraction produce a full acquisition brief in under 2 minutes.
            </p>
          </div>

          {/* Feature 2 */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6", padding: "32px" }}>
            <div style={{ fontSize: "28px", marginBottom: "16px" }}>📊</div>
            <h3 style={{ fontSize: "20px", fontWeight: 500, color: "#111111", marginBottom: "8px", letterSpacing: "-0.3px" }}>
              5-Dimension Scoring
            </h3>
            <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.6 }}>
              Every company is scored across Financial Health, Business Risk, Growth Potential, Product Fit, and Relationship Accessibility. Scores drive prioritization — pursue the warmest prospects first.
            </p>
          </div>

          {/* Feature 3 */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6", padding: "32px" }}>
            <div style={{ fontSize: "28px", marginBottom: "16px" }}>🕸️</div>
            <h3 style={{ fontSize: "20px", fontWeight: 500, color: "#111111", marginBottom: "8px", letterSpacing: "-0.3px" }}>
              Relationship Graph
            </h3>
            <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.6 }}>
              Automatically maps parents, subsidiaries, vendors, customers, and partners. Discover warm paths — &quot;this prospect supplies two of our existing clients&quot; — and turn cold leads warm.
            </p>
          </div>

          {/* Feature 4 */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6", padding: "32px" }}>
            <div style={{ fontSize: "28px", marginBottom: "16px" }}>💬</div>
            <h3 style={{ fontSize: "20px", fontWeight: 500, color: "#111111", marginBottom: "8px", letterSpacing: "-0.3px" }}>
              RAG Chatbot
            </h3>
            <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.6 }}>
              Ask natural-language questions about any company in your workspace. Answers are grounded in real research data — no hallucinations. Streaming responses arrive in real-time.
            </p>
          </div>

          {/* Feature 5 */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6", padding: "32px" }}>
            <div style={{ fontSize: "28px", marginBottom: "16px" }}>⚔️</div>
            <h3 style={{ fontSize: "20px", fontWeight: 500, color: "#111111", marginBottom: "8px", letterSpacing: "-0.3px" }}>
              Side-by-Side Compare
            </h3>
            <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.6 }}>
              Select 2–3 prospects and get an AI-generated comparison report — who to pursue first, what product to lead with, and which to deprioritize. Persisted with a shareable permalink.
            </p>
          </div>

          {/* Feature 6 */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6", padding: "32px" }}>
            <div style={{ fontSize: "28px", marginBottom: "16px" }}>📁</div>
            <h3 style={{ fontSize: "20px", fontWeight: 500, color: "#111111", marginBottom: "8px", letterSpacing: "-0.3px" }}>
              Portfolio & Whitespace
            </h3>
            <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.6 }}>
              Import your internal bank portfolio data (CSV/TSV). See KPI dashboards, product-mix charts, and a whitespace matrix highlighting cross-sell opportunities for existing clients.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section style={{ padding: "64px 24px 96px", maxWidth: "800px", margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontSize: "40px", fontWeight: 500, color: "#111111", letterSpacing: "-0.8px", marginBottom: "48px" }}>
          How it works
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "32px", textAlign: "left" }}>
          {[
            { step: "1", title: "Search a company", desc: "Type a name — we search our database and the open web instantly." },
            { step: "2", title: "AI researches it", desc: "If it's new, our pipeline crawls the web, generates an acquisition brief, scores the company, and maps its relationships." },
            { step: "3", title: "Review the dossier", desc: "Profile, financials, 5-dimension scores, relationship graph, and portfolio data — all in one tabbed view." },
            { step: "4", title: "Compare & decide", desc: "Add prospects to workspaces, compare side-by-side, chat with the AI, and identify your warmest targets." },
          ].map((item) => (
            <div key={item.step} style={{ display: "flex", gap: "20px", alignItems: "flex-start" }}>
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  backgroundColor: "#111111",
                  color: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "14px",
                  fontWeight: 600,
                  flexShrink: 0,
                }}
              >
                {item.step}
              </div>
              <div>
                <h3 style={{ fontSize: "18px", fontWeight: 500, color: "#111111", marginBottom: "4px" }}>{item.title}</h3>
                <p style={{ fontSize: "15px", color: "#626260", lineHeight: 1.5 }}>{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding: "0 24px 96px", maxWidth: "800px", margin: "0 auto" }}>
        <div
          style={{
            backgroundColor: "#ffffff",
            borderRadius: "16px",
            border: "1px solid #d3cec6",
            padding: "48px",
            textAlign: "center",
          }}
        >
          <h2 style={{ fontSize: "28px", fontWeight: 500, color: "#111111", letterSpacing: "-0.5px", marginBottom: "12px" }}>
            Ready to find your next client?
          </h2>
          <p style={{ fontSize: "16px", color: "#626260", marginBottom: "28px" }}>
            Start researching companies in under 2 minutes. No credit card required.
          </p>
          <Link
            href="/register"
            style={{
              display: "inline-block",
              padding: "12px 28px",
              fontSize: "15px",
              fontWeight: 500,
              color: "#ffffff",
              backgroundColor: "#111111",
              borderRadius: "8px",
              textDecoration: "none",
            }}
          >
            Get started free
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: "1px solid #ebe7e1", padding: "32px", textAlign: "center" }}>
        <p style={{ fontSize: "13px", color: "#7b7b78" }}>
          © 2024 Company Lens. AI-powered client acquisition intelligence.
        </p>
      </footer>
    </div>
  );
}
