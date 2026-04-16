# SlideBuddy

KI-gestützte Präsentationserstellung aus eigenen Quellen. Lade Dokumente hoch (PDF, PPTX, Excel, Web, YouTube), lass die KI Kapitel und Abschnitte planen, und generiere daraus automatisch Folien — exportiert als echte `.pptx`-Datei mit deinem eigenen Master-Template.

## Features

- **Quellenimport** — PDF, PPTX, Excel, Web-URLs und YouTube-Videos als Wissensbasis
- **RAG-Suche** — ChromaDB-Vektorspeicher liefert pro Folie die relevantesten Quell-Ausschnitte
- **KI-Kapitelplanung** — strukturierte Gliederung mit KI-Vorschlag und manueller Bearbeitung
- **Template-gestützte Generation** — Folien werden anhand deines PPTX-Masters analysiert und befüllt (Titelfolie, Aufzählung, Vergleich, Entwicklung u.v.m.)
- **PPTX-Export** — echter `.pptx`-Export mit originalem Layout und Schriftarten
- **Multi-LLM** — Anthropic Claude, OpenAI GPT oder Google Gemini frei wählbar

## Tech Stack

- **Backend:** Python 3.11+ / FastAPI / SQLite / ChromaDB
- **Frontend:** Next.js / React / TailwindCSS / React Query
- **LLM:** Anthropic Claude, OpenAI, Google Gemini (via LangChain)

## Voraussetzungen

- Python 3.11+
- Node.js 18+
- API-Key für mindestens einen LLM-Anbieter (Anthropic, OpenAI oder Google)

## Installation

### 1. Repository klonen & Python-Umgebung einrichten

```bash
git clone https://github.com/Stegoputer/Slidebuddy.git
cd Slidebuddy

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Frontend-Abhängigkeiten installieren

```bash
cd frontend
npm install
```

### 3. Entwicklungsserver starten

```bash
# Aus dem frontend/-Verzeichnis, mit aktivierter venv:
npm run dev
```

Startet beide Server gleichzeitig:
- **Web-UI:** http://localhost:3000
- **API / Swagger:** http://localhost:8000/docs

### 4. API-Keys konfigurieren

Öffne http://localhost:3000 → **Settings** → API-Keys eintragen.

Die Schlüssel werden sicher im **OS-Keyring** gespeichert (Windows Credential Manager / macOS Keychain) — niemals in Dateien oder `.env`.

## Datenbasis

Das Repository enthält die App-Datenbank, den Vektorspeicher (ChromaDB) und vorhandene Quell-Dateien. Nach einem `git pull` sind alle Projekte und Quellen sofort verfügbar, ohne erneutes Einlesen.

## Projektstruktur

```
SlideBuddy/
  slidebuddy/          # Python-Backend
    api/               # FastAPI Routers & Schemas
    core/              # LLM-Planung & Generierungslogik
    config/            # Einstellungen & Defaults
    db/                # SQLite-Modelle, Queries, Migrationen
    export/            # PPTX-Export
    llm/               # LLM-Provider-Routing
    parsers/           # PDF, PPTX, Excel, HTML, YouTube
    prompts/           # Prompt-Templates
    rag/               # ChromaDB-Vektorsuche
    data/              # Laufzeitdaten (DB, Chroma, Uploads, Masters)
  frontend/            # Next.js-Frontend
    src/app/           # App Router Pages
    src/components/    # React-Komponenten
    src/hooks/         # React Query Hooks
    src/lib/           # API-Client & Utilities
```

## Windows-Quickstart

Doppelklick auf `start.bat` im Projektverzeichnis (aktivierte venv vorausgesetzt).
Öffnet zwei Terminalfenster für Backend und Frontend.
