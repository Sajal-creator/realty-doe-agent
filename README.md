# 🏠 Realty AI — Autonomous Real Estate WhatsApp Agent + CRM Dashboard

Enterprise-grade, AI-powered real estate automation platform built on the **DOE (Directive, Orchestration, Execution)** framework. Features a fully autonomous WhatsApp chatbot, interactive CRM dashboard with live session canvas, lead qualification matrix, map visualization, and real-time WebSocket sync.

---

## 📁 Project Structure

```
realty-doe-agent/
│
├── directives/                    # 1. STRATEGY LAYER (Markdown playbooks)
│   ├── buyer_qualification_strategy.md
│   ├── seller_lead_capture_strategy.md
│   ├── nurture_re_engagement_strategy.md
│   ├── support_handling_strategy.md
│   ├── appointment_scheduling_strategy.md
│   ├── agent_handover_strategy.md
│   ├── faq_and_knowledge_strategy.md
│   └── general_conversation_strategy.md
│
├── orchestration/                 # 2. MANAGER LAYER (Python controllers)
│   ├── orchestrator.py            # Main cognitive controller engine
│   ├── state_manager.py           # Redis session & mode locker
│   ├── intent_router.py           # LLM semantic task assigner
│   ├── memory_compressor.py       # High-density summarization
│   ├── warmth_engine.py           # Lead warmth scoring (0-100)
│   ├── escalation_protocol.py     # High-intent escalation
│   ├── context_interleaver.py     # Non-linear conversation handler
│   ├── organic_handler.py         # Organic inbound classifier
│   ├── self_healer.py             # Self-annealing error recovery
│   └── config.py                  # Configuration
│
├── execution/                     # 3. WORKER LAYER (MCP tools)
│   ├── whatsapp_gateway.py        # Meta Cloud API interface
│   ├── whisper_processor.py       # Voice note transcription
│   ├── matrix_analyzer.py         # 4-D qualification extractor
│   ├── vector_mls_matcher.py      # pgvector property search
│   ├── calendar_scheduler.py      # Google Calendar integration
│   ├── dashboard_syncer.py        # Real-time WebSocket server
│   ├── hijack_controller.py       # AI-to-human chat takeover
│   ├── agent_router.py            # Multi-agent load balancer
│   ├── reengagement_cron.py       # Anti-ghosting nurture engine
│   ├── meta_flow_parser.py        # WhatsApp Flow form decoder
│   ├── sentiment_analyzer.py      # Real-time sentiment scoring
│   ├── lead_data_service.py       # Database CRUD operations
│   ├── notification_service.py    # Dashboard push notifications
│   ├── faq_vector_search.py       # Knowledge base RAG
│   ├── mls_data_fetcher.py        # MLS listing sync
│   ├── llm_client.py              # OpenAI async wrapper
│   └── worker_registry.py         # Tool registration & dispatch
│
├── skills/                        # 4. CAPABILITY LAYER (JSON prompts)
│   ├── buyer_discovery.json
│   ├── seller_valuation.json
│   ├── urgency_classifier.json
│   ├── handover_etiquette.json
│   ├── hyper_local_expert.json
│   └── objection_vault.json
│
├── backend/app/models/            # 5. DATABASE MODELS (SQLAlchemy)
│   ├── base.py                    # UUID + timestamp mixins
│   ├── agent.py                   # Agent model
│   ├── lead.py                    # Lead model (4-D matrix)
│   ├── session.py                 # Session model (AI/Agent state)
│   ├── message.py                 # Message model (all types)
│   ├── ticket.py                  # Support ticket model
│   ├── appointment.py             # Appointment model
│   ├── notification.py            # Notification model
│   └── property_listing.py        # Property + pgvector embeddings
│
├── dashboard/                     # 6. FRONTEND (Next.js + React)
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx             # Root layout + Socket.IO provider
│   │   ├── page.tsx               # Main 3-column dashboard
│   │   └── globals.css            # Dark theme + animations
│   ├── store/
│   │   ├── useStore.ts            # Zustand global state
│   │   └── dashboardStore.ts      # Dashboard-specific store
│   ├── hooks/
│   │   └── useSocket.ts           # Socket.IO event hook
│   ├── lib/
│   │   ├── api.ts                 # REST API client
│   │   └── utils.ts               # Utility functions
│   └── components/
│       ├── TopBar.tsx              # 64px header
│       ├── BottomStatusBar.tsx     # 32px status bar
│       ├── PipelinePanel.tsx       # Left: Kanban pipeline
│       ├── UnifiedInbox.tsx        # Center: Chat window
│       ├── LeadProfile.tsx         # Center-bottom: Lead details
│       ├── LeadMap.tsx             # Right: Mapbox map
│       ├── SessionCanvas.tsx       # React Flow live canvas
│       ├── SessionInspector.tsx    # Session detail split-view
│       ├── QualificationMatrix.tsx # 4-D matrix visualization
│       ├── NotificationPanel.tsx   # Toast + bell notifications
│       ├── ErrorBoundary.tsx       # Error handling
│       └── modals/
│           ├── ScheduleModal.tsx   # Viewing scheduler
│           ├── BulkMessageModal.tsx # Bulk message composer
│           ├── LeadDetailDrawer.tsx # Full lead edit drawer
│           └── SettingsModal.tsx   # Agent settings
│
├── docker/                        # 7. DEPLOYMENT
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
│
├── tmp/                           # Runtime temp files
│   ├── audio_cache/
│   └── session_snapshots/
│
├── .env.example                   # Environment variables template
└── requirements.txt               # Python dependencies
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Meta Business account with WhatsApp Cloud API access
- OpenAI API key
- Google Cloud project with Calendar API enabled
- Mapbox token

### 1. Clone & Configure
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Launch with Docker
```bash
cd docker
docker-compose up -d
```

### 3. Access
- **Dashboard**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 4. Configure WhatsApp Webhook
In Meta Business Suite → WhatsApp → Configuration:
- Webhook URL: `https://your-domain.com/webhook/whatsapp`
- Verify Token: (from your .env)
- Subscribe to: `messages`, `message_deliveries`

---

## 🧠 How It Works

### The DOE Framework

**Directive Layer** (`/directives/`) — Strategy playbooks in Markdown. The orchestrator reads these at runtime to understand goals, rules, and guardrails. Edit these to change AI behavior without touching code.

**Orchestration Layer** (`/orchestration/`) — The brain. Reads directives, reconstitutes conversation context, routes intents to the right tools, manages state transitions, and handles self-healing.

**Execution Layer** (`/execution/`) — The hands. 15+ specialized workers that do actual labor: send WhatsApp messages, transcribe voice notes, extract qualification data, search properties, book calendars, sync dashboards.

### Message Flow
```
WhatsApp Message → Meta Webhook → FastAPI Gateway → Redis Queue
    → Orchestrator reads directives + conversation history
    → Intent Router classifies intent
    → LLM generates response (with tool calls if needed)
    → Response sent back via WhatsApp Gateway
    → Dashboard synced via WebSocket in real-time
```

### 4-D Qualification Matrix
Every lead is scored on 4 dimensions:
- **Budget**: Extracted from conversation (0-100)
- **Timeline**: Urgency of move (ASAP=100, browsing=10)
- **Financing**: Cash=100, Pre-approved=85, In-progress=50
- **Deal-breakers**: Specificity of requirements

Combined into a **Warmth Score** (0-100) → HOT (≥80), WARM (≥50), COLD (<50)

### Advanced Agentic Behaviors
- **Agentic Loops**: If a tool fails, the orchestrator retries with adjusted parameters
- **Self-Annealing**: Error logs are analyzed and parameters auto-corrected
- **Memory Summarization**: Long conversations compressed to preserve context within token limits
- **Context Interleaving**: Support questions mid-qualification are handled gracefully without losing state

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Cache/Queue | Redis 7 |
| AI/LLM | OpenAI GPT-4o (function calling) |
| Audio | OpenAI Whisper API |
| Frontend | Next.js 15, React 18, TypeScript |
| State | Zustand |
| Real-time | Socket.IO |
| Visualization | React Flow, Mapbox GL JS, Recharts |
| Styling | Tailwind CSS (dark mode) |
| Animation | Framer Motion |
| Deployment | Docker Compose |

---

## 📊 Dashboard Features

- **Pipeline Kanban**: Drag-and-drop lead cards across Hot/Warm/Cold/New columns
- **Unified Inbox**: WhatsApp-like chat with AI/Agent/Human message differentiation
- **Live Session Canvas**: React Flow network showing agent-lead connections with glowing edges
- **Interactive Map**: Mapbox with color-coded lead pins, clustering, heatmap toggle
- **4-D Matrix Visualization**: Progress bars and gauges for qualification dimensions
- **Session Inspector**: Split-view with AI summary, qualification grid, and live chat
- **Notification System**: Toast alerts, bell dropdown, sound effects
- **Modals**: Schedule viewing, bulk message, lead detail drawer, settings

---

## 🔒 Security

- Webhook signature verification (HMAC-SHA256)
- JWT authentication for dashboard
- Room-based WebSocket isolation per agency
- Non-root Docker containers
- Environment variable secrets (never committed)
- GDPR/CCPA compliant data handling (deletion, export)

---

## 📄 License

MIT
