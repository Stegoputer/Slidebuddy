# SlideBuddy

LLM-powered presentation generator. Upload sources (PDF, PPTX, YouTube, etc.), plan chapters and sections with AI, then generate slides automatically.

## Tech Stack

- **Backend:** Python 3.11+ / FastAPI / SQLite / ChromaDB
- **Frontend:** Next.js 16 / React 19 / TailwindCSS / React Query
- **LLM:** Anthropic Claude, OpenAI, or Google Gemini (via LangChain)

## Setup

### 1. Clone & Python Environment

```bash
git clone https://github.com/YOUR_USER/SlideBuddy.git
cd SlideBuddy

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Start Development Server

```bash
# From the frontend/ directory, with venv activated:
npm run dev
```

This starts both servers concurrently:
- **Web UI:** http://localhost:3000
- **API / Swagger:** http://localhost:8000/docs

### 4. Configure API Keys

Open http://localhost:3000 and navigate to **Settings**. Add your API key for at least one LLM provider:
- Anthropic (Claude)
- OpenAI
- Google (Gemini)

## Project Structure

```
SlideBuddy/
  slidebuddy/          # Python backend
    api/               # FastAPI routers & schemas
    core/              # LLM planning & generation logic
    config/            # Settings & defaults
    db/                # SQLite models, queries, migrations
    export/            # PPTX export
    llm/               # LLM provider routing
    parsers/           # PDF, PPTX, Excel, HTML, YouTube parsers
    rag/               # ChromaDB vector search
  frontend/            # Next.js frontend
    src/app/           # App Router pages
    src/components/    # React components
    src/hooks/         # React Query hooks
    src/lib/           # API client & utilities
```

## Alternative Start (Windows)

Double-click `start.bat` in the project root (requires activated venv).
