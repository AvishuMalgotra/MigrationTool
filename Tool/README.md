# Azure Migration Evaluator

A robust, AI-powered tool for assessing and migrating Azure resources across subscriptions. This agent combines strict compatibility logic with **AI Reasoning** (Groq/OpenAI/Gemini) to validate migration feasibility and orchestrate safe moves.

## 🚀 Key Features

### 1. Intelligent Inventory & Assessment
- **Deep Discovery**: Scans Azure subscriptions for all resources and maps dependencies.
- **AI-Powered Analysis**: Uses LLMs to reason about "move support" for edge cases where official docs are unclear.
- **Strict Validation**: Hardcoded safety checks for known blockers (e.g., specific SKUs, disconnected NICs, classic resources).

### 2. Comprehensive Exports
- **Excel Reports**: Professional-grade status reports with pivot tables.
- **ARM Template Export**:
    - **Official Schema**: Exports resources exactly as seen in Azure Portal.
    - **Hierarchy**: Organizes templates by Resource Type and Name.
- **Enhanced Data Exports (CSV/JSON)**:
    - **RBAC**: Full role assignments with **Principal Names resolved via Microsoft Graph**.
    - **Public IPs**: Detailed IP configurations and associations.
    - **Virtual Machines**: Status, OS, Size, and Public IP mapping.

### 3. Safe Migration Orchestration
- **Validation Phase**: Pre-checks move requests against Azure's `validateMoveResources` API.
- **Dependency Awareness**: Ensures resources are moved in the correct order (e.g., VNETs before VMs).
- **Rollback Capability**: Monitors long-running operations and reports failures instantly.

---

## 🏗️ Project Structure

- **`/backend`** (FastAPI): Core logic, SQLite DB, AI Integration, Azure Connector (Management & Graph APIs).
- **`/portal`** (Next.js 14): Modern dashboard for triggering jobs, viewing real-time status, and downloading reports.

---

## 🛠️ Setup & Running

### Prerequisites
- Python 3.10+
- Node.js 18+
- **Azure Service Principal** with:
    - **Subscription**: Reader (minimum) or Contributor (for migration).
    - **Graph API**: `User.Read.All` (Directory.Read.All) to resolve RBAC names.
- **AI API Key** (Groq, OpenAI, or Gemini)

### 1. Backend Setup
Create `backend/.env` (see `.env.example`):
```env
# Azure Credentials
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...

# AI Configuration (Example: OpenAI)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# App Config
ALLOWED_ORIGINS=http://localhost:3000
```

Run Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
*Docs available at: http://localhost:8000/docs*

### 2. Frontend Setup
Run Portal:
```bash
cd portal
npm install
npm run dev
```
*Dashboard available at: http://localhost:3000*

---

## 🤖 AI Configuration Options

### Option A: Groq (Recommended for Speed/Cost)
```env
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
```

### Option B: OpenAI (Standard)
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

### Option C: Google Gemini
```env
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash-exp
```

## 📄 License
MIT
