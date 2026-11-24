# Kirana Khata Agent

**Kirana Khata Agent** is an MCP-powered owner operations workbench (*ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್*). Customers send WhatsApp or Telegram orders in Kannada text or voice; the agent parses items, verifies stock and customer credit limits, proposes smart substitutes, drafts gentle staged UPI payment reminders, manages low-stock supplier reorders, and enforces explicit owner approval before updating inventory, khata, or sending replies.

---

## Architecture & Repository Structure

```text
KiranaKhataAgent/
├── .env.example
├── README.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint + SQLite/PostgreSQL lifespan seeding
│   │   ├── config.py                # Env-driven configuration (zero hardcoded secrets)
│   │   ├── database.py              # SQLAlchemy engine & session factory
│   │   ├── models.py                # Relational schema (Customers, Products, Orders, Khata, Approvals, AuditLogs)
│   │   ├── schemas.py               # Pydantic v2 typed request/response contracts
│   │   ├── seed.py                  # Deterministic seed data (20 SKUs, 6 customers, 3 suppliers)
│   │   ├── mcp_tools.py             # Official Python MCP SDK (MCPServer) with 14 tools
│   │   ├── adapters/
│   │   │   ├── interfaces.py        # Protocol contracts for all external integrations
│   │   │   ├── mock/                # Seeded offline/demo adapters (WhatsApp, Sheets, Razorpay, STT, OCR)
│   │   │   └── production/          # Env-driven production adapters (WhatsApp Cloud, Sheets, Razorpay, STT, OCR)
│   │   ├── services/
│   │   │   ├── parser.py            # Kannada/Tanglish/English order, repeat-order, substitute & voice parser
│   │   │   ├── approvals.py         # Approval gating engine & immutable audit logging
│   │   │   └── workflow.py          # Core end-to-end business workflows
│   │   └── routers/                 # FastAPI REST endpoints (/api/*)
│   └── tests/
│       └── test_kirana_workflows.py # Pytest suite covering parsing, credit checks, gating & payments
└── frontend/
    ├── .env.example
    └── src/
        ├── app/
        │   ├── page.tsx             # Overview Dashboard (KPIs, Needs Approval queue, Timeline, Daily Summary)
        │   ├── orders/page.tsx      # WhatsApp-style Inbox + 9-step order processing + Smart Substitutes
        │   ├── khata/page.tsx       # Digital Khata Ledger, Customer Drawer, Reminder Stages & UPI Payment Match
        │   ├── inventory/page.tsx   # 20-SKU Stock Table & Supplier-Bill Photo OCR Intake
        │   ├── suppliers/page.tsx   # 3 Suppliers & Low-Stock Reorder Draft Workbench
        │   ├── approvals/page.tsx   # Full Owner Approval Queue & Immutable Audit Trail
        │   └── reports/page.tsx     # 9 PM Daily Summary, Kannada Voice Playback & Recharts Analytics
        ├── components/              # AppShell, ApprovalCard, VoiceCommandModal, shadcn-style UI primitives
        └── lib/                     # Typed API client, bilingual EN/ಕನ್ನಡ context, formatters
```

---

## Local Setup & Running

### 1. Backend (FastAPI + Python MCP SDK + SQLite)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run FastAPI server on http://localhost:8000
uvicorn app.main:app --reload --port 8000
```

The backend automatically initializes the SQLite database (`kirana_khata.db`) and seeds realistic kirana data on startup if empty.

### 2. Run Backend Tests

```bash
cd backend
.venv/bin/pytest -v
```

### 3. Run Standalone MCP Server (stdio)

```bash
cd backend
.venv/bin/python -m app.mcp_tools
```

### 4. Frontend (Next.js + Tailwind CSS + Recharts + Lucide)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Cloud Deployment (Vercel + Render)

1. **Backend (Render)**:
   - Create a Web Service from this GitHub repo using the included `render.yaml` (`rootDir: backend`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
   - Set environment variables: `FRONTEND_ORIGIN=https://<your-vercel-domain>.vercel.app`, and optionally `TELEGRAM_BOT_TOKEN`.
2. **Frontend (Vercel)**:
   - Import this GitHub repo in Vercel with **Root Directory** set to `frontend`.
   - Set `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`.

---

## Switching from SQLite Demo to PostgreSQL / Supabase

All persistence runs through SQLAlchemy in `backend/app/database.py`. To switch to PostgreSQL or Supabase:

1. Set `DATABASE_URL` in `.env`:
   ```env
   DATABASE_URL=postgresql+psycopg2://postgres:<password>@db.<project>.supabase.co:5432/postgres
   ```
2. Set `APP_MODE=production` and configure the environment variables in `.env` for WhatsApp Cloud API, Google Sheets, Razorpay UPI, Kannada STT, and Bill OCR.

---

## Registered MCP Tools (`backend/app/mcp_tools.py`)

Built using the official Python MCP SDK (`mcp.server.mcpserver.MCPServer`):

| MCP Tool | Access Mode | Purpose |
| :--- | :--- | :--- |
| `get_customer_balance(customer_id)` | Read | Fetch current khata balance, credit limit, overdue days, and reminder stage. |
| `check_credit_limit(customer_id, proposed_amount)` | Read | Evaluate whether a new credit order exceeds the customer's limit and compute overage. |
| `get_inventory(product_id)` | Read | Inspect product stock quantity, reorder threshold, price, and supplier. |
| `update_inventory(product_id, quantity_change)` | **Approval-Gated** | Mutates product stock only when backed by an `approved` `ApprovalRequest`. |
| `create_khata_entry(customer_id, amount, order_id)` | **Approval-Gated** | Records a credit ledger entry only after owner approval. |
| `create_payment_link(customer_id, amount)` | Write Link | Creates a Razorpay UPI payment link (mocked in demo mode). |
| `record_payment(payment_link_id, amount)` | Webhook Match | Matches full or partial UPI payment, updates khata, stages Kannada thank-you approval. |
| `get_overdue_customers()` | Read | Returns overdue customers sorted by risk and days overdue. |
| `create_reminder_draft(customer_id)` | **Approval-Gated** | Generates stage-appropriate Kannada/English reminder with UPI link for approval. |
| `send_approved_whatsapp_message(message_id)` | **Approval-Gated** | Sends WhatsApp message only when linked to an approved request. |
| `create_supplier_order(supplier_id, items)` | **Approval-Gated** | Drafts a supplier purchase order & WhatsApp message requiring owner approval. |
| `generate_daily_summary()` | Read/Write | Computes 9 PM daily sales, credit, collections, top overdue, and Kannada voice script. |
| `transcribe_kannada_voice(audio_file)` | Read | Transcribes Kannada customer voice notes and owner voice commands via STT adapter. |
| `extract_supplier_bill(image_file)` | **Approval-Gated** | Runs OCR on supplier bill photo and stages stock-intake approval before adding stock. |

Every approval, rejection, stock mutation, khata entry, payment match, and sent WhatsApp message writes an immutable row to `audit_logs`.
