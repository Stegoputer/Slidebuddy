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

Folgende Programme müssen installiert sein. Nach jeder Installation **ein neues Terminal-Fenster öffnen**, damit der Befehl erkannt wird.

### Python 3.11+

1. Herunterladen: https://www.python.org/downloads/ → "Download Python 3.x.x"
2. Installer starten — **wichtig:** Haken bei **"Add python.exe to PATH"** setzen, bevor du auf "Install Now" klickst
3. Installation prüfen (neues Terminal):
   ```
   py --version
   ```
   Falls `py` nicht erkannt wird:
   ```
   python --version
   ```
   Mindestens `Python 3.11.x` muss erscheinen. Falls keiner der Befehle funktioniert → Python deinstallieren und Schritt 2 wiederholen (PATH-Haken nicht vergessen).

### Node.js 18+

1. Herunterladen: https://nodejs.org → **LTS-Version** (linke Schaltfläche)
2. Installer starten — Standardeinstellungen übernehmen, einfach durchklicken
3. Installation prüfen (neues Terminal):
   ```
   node --version
   npm --version
   ```
   Beide Befehle müssen eine Versionsnummer ausgeben.

### Git

1. Herunterladen: https://git-scm.com/download/win
2. Installer starten — Standardeinstellungen übernehmen
3. Installation prüfen:
   ```
   git --version
   ```

### API-Key

Mindestens einen API-Key von einem dieser Anbieter:
- **Anthropic (Claude):** https://console.anthropic.com
- **OpenAI (GPT):** https://platform.openai.com
- **Google (Gemini):** https://aistudio.google.com

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/Stegoputer/Slidebuddy.git
cd Slidebuddy
```

### 2. Python-Umgebung einrichten

**Windows:**
```bash
py -m venv .venv
```
> Falls `py` nicht erkannt wird, stattdessen `python -m venv .venv` verwenden.

```bash
.venv\Scripts\pip install -r requirements.txt
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend-Abhängigkeiten installieren

```bash
cd frontend
npm install
cd ..
```

### 4. App starten

**Windows (empfohlen):** Doppelklick auf `start.bat` im Projektordner. Es öffnen sich zwei Terminalfenster — eines für das Backend (Port 8000), eines für das Frontend (Port 3000).

Oder manuell — zwei Terminals öffnen:

Terminal 1 (Backend):
```bash
# Windows
.venv\Scripts\python.exe -m uvicorn slidebuddy.api.app:app --port 8000 --reload --reload-dir slidebuddy

# macOS/Linux
.venv/bin/python -m uvicorn slidebuddy.api.app:app --port 8000 --reload --reload-dir slidebuddy
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Danach im Browser öffnen:
- **App:** http://localhost:3000
- **API-Dokumentation:** http://localhost:8000/docs

### 5. API-Keys eintragen

Öffne http://localhost:3000 → **Settings** → API-Keys eintragen.

Die Schlüssel werden sicher im **OS-Keyring** gespeichert (Windows Credential Manager / macOS Keychain) — niemals in Dateien oder `.env`.

---

## Häufige Probleme (Windows)

**`py` oder `python` wird nicht erkannt:**
- Versuche den jeweils anderen Befehl: statt `py` → `python`, statt `python` → `py`
- Funktioniert keiner: Python wurde ohne PATH-Option installiert → Python deinstallieren, neu installieren und dabei **"Add python.exe to PATH"** ankreuzen

**`npm` wird nicht erkannt nach Installation:**
Schließe das Terminal komplett und öffne ein neues Fenster.

**`npm`-Skripte werden blockiert:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Backend startet nicht / `No module named uvicorn`:**
Die Python-Pakete wurden nicht in der virtuellen Umgebung installiert. Führe im Projektordner aus:
```bash
.venv\Scripts\pip install -r requirements.txt
```

**Frontend zeigt `ECONNREFUSED` auf Port 8000:**
Das Backend-Fenster wurde geschlossen oder ist nicht gestartet. `start.bat` erneut ausführen und sicherstellen, dass beide Fenster (API + Web) offen bleiben.

---

## Updates

Um die neuesten Daten, Projekte und Quellen zu laden:

```bash
cd Slidebuddy
git pull
```

Das Repository enthält die App-Datenbank, den Vektorspeicher (ChromaDB) und vorhandene Quell-Dateien. Nach einem `git pull` sind alle Projekte und Quellen sofort verfügbar, ohne erneutes Einlesen.

---

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
