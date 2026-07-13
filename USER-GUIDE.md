# Company Lens — User Guide

A step-by-step guide to using every feature of Company Lens.

---

## Table of Contents

1. [Create an Account](#1-create-an-account)
2. [Log In](#2-log-in)
3. [Search a Company](#3-search-a-company)
4. [Research a New Company](#4-research-a-new-company)
5. [View a Company Dossier](#5-view-a-company-dossier)
6. [Create a Workspace (Target List)](#6-create-a-workspace-target-list)
7. [Add Companies to a Workspace](#7-add-companies-to-a-workspace)
8. [Compare Companies](#8-compare-companies)
9. [Chat with the AI Assistant](#9-chat-with-the-ai-assistant)
10. [Upload Documents](#10-upload-documents)
11. [View the Relationship Graph](#11-view-the-relationship-graph)
12. [Refresh Research](#12-refresh-research)
13. [Import Portfolio Data (Admin)](#13-import-portfolio-data-admin)
14. [View Portfolio & Whitespace](#14-view-portfolio--whitespace)

---

## 1. Create an Account

1. Go to the homepage at `http://localhost:3000`
2. Click **"Get started"** or **"Create one"** on the login page
3. Fill in:
   - **Username**: 3–50 characters (letters, digits, `_`, `-`)
   - **Email**: valid email address
   - **Password**: at least 8 characters with uppercase, lowercase, digit, and special character
4. Watch the green checkmarks confirm each password rule
5. Click **"Create Account"**
6. You'll be redirected to the login page

---

## 2. Log In

1. Go to `http://localhost:3000/login`
2. Enter your **username** and **password**
3. Click **"Sign in"**
4. You'll be redirected to the workspaces page

> **Note:** After 5 failed login attempts, your account is locked for 15 minutes.

---

## 3. Search a Company

1. After logging in, use the **search bar** at the top of the page
2. Type at least **2 characters** of a company name
3. Results appear as a dropdown showing:
   - Company name
   - Status badge: **Client** (green), **Prospect** (blue), or **Unknown** (gray)
   - Industry
   - Overall score (if researched)
4. Click a result to view its dossier

---

## 4. Research a New Company

If a company isn't in the system:

1. Search for it — if no results found, you'll see **"Research [company name]"** button
2. Click it to start the AI research pipeline
3. Watch the real-time progress via WebSocket notifications:
   - 🔍 **Searching** — Tavily web search
   - 🌐 **Crawling** — extracting content from discovered URLs
   - 📝 **Profiling** — generating the acquisition brief
   - 📊 **Scoring** — calculating 5-dimension scores
4. When complete, the company dossier opens automatically

> **Pipeline takes 1–2 minutes** depending on available web sources.

---

## 5. View a Company Dossier

Once a company is researched, its dossier has **5 tabs**:

### Profile Tab
- Full AI-generated acquisition brief
- Sections: Executive Summary, Business Model, Financial Profile, Market Position, Risks, Growth Indicators, Relationships
- Document upload widget at the bottom

### Financials Tab
- Structured grid: Founded Year, Headquarters, Employees, Revenue, Funding, Market Cap, Website, LinkedIn, Ticker, Industry
- All extracted automatically from the research

### Scores Tab
- **Overall Score** badge with color coding:
  - ≤1.0 red | ≤2.0 orange | ≤3.0 yellow | ≤4.0 teal | >4.0 green
- Five dimension cards with individual scores and insights
- Radar chart (spider web) showing all 5 dimensions
- Bar chart comparison

### Portfolio Tab (Clients only)
- KPI tiles: Profitability, NII, Fee Income, Loan Outstanding, DPK Balance
- Trend lines across snapshots
- Product-mix donut charts
- Whitespace matrix (cross-sell opportunities)
- Shows "Portfolio data is only available for existing clients" for non-clients

### Connections Tab
- Interactive **React Flow** relationship graph
- Nodes colored by status: Client (green), Prospect (blue), Unknown (gray)
- Edges labeled: parent, subsidiary, vendor, customer, partner
- **Warm path** highlighted in amber if one exists to a client
- Click any **Unknown** node to research it with one click

---

## 6. Create a Workspace (Target List)

Workspaces are how you organize prospects for a campaign:

1. Go to **Workspaces** page (after login)
2. Click **"+ Create Workspace"**
3. Enter a name (1–100 characters)
4. Click **"Create"**

Each workspace can hold up to **3 companies** (configurable).

---

## 7. Add Companies to a Workspace

1. Open a workspace
2. Use the **search box** labeled "Search companies to add..."
3. Type a company name — results appear (filtered to exclude already-added ones)
4. Click a result to add it
5. The company appears as a card in the workspace

**Limit:** 3 companies per workspace (shown in the progress bar).

To **remove** a company: click the ✕ button on its card.

---

## 8. Compare Companies

1. Open a workspace that has **2–3 companies** with status "ready"
2. Click **"Compare"** link
3. Select 2–3 companies using checkboxes
4. Click **"Compare"** button
5. Wait for the AI to generate the comparison report (usually 30–60 seconds)
6. The HTML report appears with:
   - Executive Summary
   - Key Metrics table
   - Score Analysis
   - Strategic Fit
   - Pursuit Recommendation (who to target first)

> **Fallback:** If the AI fails, a structured score comparison table is shown instead.

---

## 9. Chat with the AI Assistant

1. Open a workspace
2. Click **"Chat"** link
3. Type a question about the companies in your workspace, e.g.:
   - "Which company has stronger financials?"
   - "What banking products would fit Company X?"
   - "Compare the risk profiles of all companies"
4. The AI responds using **only** the stored research data (no hallucinations)
5. Responses stream in real-time token by token
6. Chat history is saved per workspace

> **Note:** The workspace must have at least 1 company. If empty, you'll get a prompt to add companies first.

---

## 10. Upload Documents

Add PDF documents to enrich a company's knowledge base:

1. Open a company's dossier (Profile tab)
2. Scroll to the **"Upload Document"** section
3. Click the file input and select a PDF (max 20MB, max 200 pages)
4. Click **"Upload"**
5. Watch the status update in real-time:
   - 🟡 **Pending** — queued for processing
   - 🔵 **Processing** — extracting text, generating key points, creating embeddings
   - 🟢 **Ready** — incorporated into the company's knowledge base
   - 🔴 **Failed** — extraction error (invalid PDF, no text, etc.)

After processing, the document's content:
- Feeds into the RAG chatbot (you can ask questions about it)
- May update the company's scores (automatic re-scoring)

---

## 11. View the Relationship Graph

1. Open a company dossier
2. Click the **"Connections"** tab
3. The graph shows:
   - **Center node** = the company you're viewing
   - **Connected nodes** = related companies (parents, subsidiaries, vendors, customers, partners)
   - **Colors**: Green = Client, Blue = Prospect, Gray = Unknown
   - **Amber highlight** = warm path (shortest route to an existing client)
4. **Click an Unknown (gray) node** → modal asks "Research this company?" → click to start research
5. **Warm path info** banner shows hop count to nearest client

---

## 12. Refresh Research

To get up-to-date information for a prospect:

1. Open the company's dossier
2. The company must be a **Prospect** with status **"ready"**
3. Click **"Refresh"** (or POST `/api/companies/{id}/refresh`)
4. The pipeline re-runs, replacing old data with fresh research
5. Progress streams via WebSocket just like initial research

> **Note:** Clients cannot be refreshed (their data comes from internal systems). Only Prospects qualify.

---

## 13. Import Portfolio Data (Admin)

Upload your bank's monthly portfolio extract:

1. Go to **POST `/api/portfolio/import`** (via API or admin UI)
2. Upload a CSV or TSV file with the standard column format:
   - `{division}_{product_group}_{subproduct}_{metric}` for metric columns
   - `nama_nasabah` column for company names
   - `nama_group`, `nama_subholding` for group relationships
3. The system will:
   - Parse column names into the metric catalog
   - Match customer names to existing companies (exact → alias → fuzzy)
   - Store sparse snapshots (zero-value metrics are skipped)
   - Promote matched companies to **Client** status
   - Create group-member relationship edges
4. Unmatched names go to the **reconciliation queue** (`GET /api/portfolio/queue`)
5. Resolve them manually: accept (link to a company) or reject

---

## 14. View Portfolio & Whitespace

For companies with Client status and imported portfolio data:

1. Open the company dossier
2. Click **"Portfolio"** tab
3. See:
   - **KPI Tiles** — profitability, NII, fee income, loan balance, DPK balance
   - **Trend Lines** — how metrics change over monthly snapshots
   - **Product-Mix Donuts** — DPK split (giro/tabungan/deposito), Loan split (KI/KMK)
   - **Fee Income Bars** — by category (trade, cash management, forex, guarantee)
   - **Whitespace Matrix** — product groups with ZERO activity = cross-sell targets

> **Cross-sell tip:** The whitespace matrix is the RM's #1 conversation starter — "I see you don't use our trade finance products yet..."

---

## Quick API Reference

| Action | Method | Endpoint |
|--------|--------|----------|
| Register | POST | `/api/auth/register` |
| Login | POST | `/api/auth/login` |
| Search | GET | `/api/companies/search?q=name` |
| Research | POST | `/api/companies/research` |
| Company detail | GET | `/api/companies/{id}` |
| Graph | GET | `/api/companies/{id}/graph?depth=1` |
| Warm path | GET | `/api/companies/{id}/warm-path` |
| Create workspace | POST | `/api/workspaces` |
| Compare | POST | `/api/workspaces/{id}/compare` |
| Chat | POST | `/api/workspaces/{id}/chat` |
| Upload doc | POST | `/api/companies/{id}/documents` |
| Import portfolio | POST | `/api/portfolio/import` |

Full Swagger docs: **http://localhost:8000/api/docs**

---

## Tips

- **Workspaces are personal** — only you can see your workspaces and their contents
- **Research is global** — once a company is researched, any user can find it via search
- **Portfolio data is never sent to AI** — all LLM calls use only public research data
- **WebSocket notifications** appear as toasts in the bottom-right corner
- **Score color bands** help you quickly identify strong (green) vs weak (red) prospects
- **The graph's warm path** is your highest-probability acquisition path — leverage it
