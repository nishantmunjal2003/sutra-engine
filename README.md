# Sutra Press: Manuscript Conversion Engine

[![Build and Publish Docker Image to GHCR](https://github.com/nishantmunjal2003/sutra-engine/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/nishantmunjal2003/sutra-engine/actions/workflows/docker-publish.yml)
[![Docker Image](https://img.shields.io/badge/GHCR-ghcr.io%2Fnishantmunjal2003%2Fsutra--engine-blue?logo=docker)](https://github.com/nishantmunjal2003/sutra-engine/pkgs/container/sutra-engine)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Sutra Press** (*Sūtra* / सूत्र = thread) is an open-standards-based manuscript conversion and typesetting engine for academic publishing. It takes author manuscripts (`.docx`) and produces synchronized parallel outputs from a single shared internal representation (IR):

1. **Strictly Validated JATS XML 1.3** — Ready for Open Journal Systems (OJS), PubMed Central (PMC), DOAJ, and Crossref.
2. **Typeset Camera-Ready PDF** — Generated via LaTeX templates and the modern [Tectonic](https://tectonic-typesetting.github.io/) typesetting engine.

Because both JATS XML and PDF are emitted as sibling branches from a single IR, they **never desynchronize**.

---

## 🚀 Key Features

- **Single-Source Publishing**: One shared intermediate model drives both JATS XML and LaTeX/PDF outputs.
- **Interactive Visual Editor**: Split-screen editing with real-time synchronized live PDF preview.
- **Journal Profiles & Automatic Style Extraction**: Extract layout geometries, typography, columns, and logos directly from reference sample PDFs.
- **Multi-Model AI Cascading Fallback**:
  - Automatically queries `Gemini` → `OpenAI (GPT-4o)` → `Anthropic (Claude)` → **`Local Semantic Classifier`**.
  - Works 100% offline using deterministic rule-based triage if no cloud API keys are provided.
- **Enterprise-Grade Security**:
  - LaTeX command injection sanitization and blocklisting (`\input`, `\exec`, `\write`, `\shellescape`).
  - XML external entity (XXE) and billion laughs bomb protection via defused parsing and lxml hardening.
  - Project data at rest encrypted using AES symmetric encryption (`cryptography.fernet`).
- **Container Ready**: Pre-configured Dockerfile, Docker Compose, and automated publishing to GitHub Container Registry (`ghcr.io`).

---

## 🐳 Quick Start with Docker (GHCR)

The fastest way to run Sutra Engine is using the pre-built container from GitHub Container Registry:

```bash
# Pull the latest image
docker pull ghcr.io/nishantmunjal2003/sutra-engine:latest

# Run the container
docker run -d \
  -p 8010:8010 \
  -v sutra_data:/app/build \
  --name sutra-engine \
  ghcr.io/nishantmunjal2003/sutra-engine:latest
```

Open your browser at **`http://localhost:8010`**.

### Using Docker Compose

Clone the repository and run:

```bash
docker compose up -d
```

To stop:

```bash
docker compose down
```

---

## 💻 Local Installation (Python)

### 1. Prerequisites

- Python 3.12+
- [Pandoc](https://pandoc.org/installing.html) installed and available on system `PATH`
- (Optional) System [Tectonic](https://tectonic-typesetting.github.io/); if absent, Sutra automatically downloads and caches the standalone binary.

### 2. Clone and Install

```bash
git clone https://github.com/nishantmunjal2003/sutra-engine.git
cd sutra-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 3. Launch Web Server

```bash
python run_web.py
```

The web application will be accessible at:
👉 **`http://localhost:8010`**

### 4. CLI Usage

You can also run batch conversions from the terminal:

```bash
# Convert DOCX to both JATS XML and compiled PDF
sutra convert path/to/manuscript.docx --out ./output

# Validate existing JATS XML against official NLM/NCBI 1.3 XSD schemas
sutra validate output/manuscript.jats.xml
```

---

## ⚙️ Configuration & Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8010` | Port for the FastAPI web server |
| `HOST` | `0.0.0.0` | Host IP binding (`0.0.0.0` for Docker, `127.0.0.1` for local) |
| `RELOAD` | `false` | Enable Uvicorn live reload during development |
| `GEMINI_API_KEY` | *(optional)* | Google Gemini API key for AI-assisted classification |
| `OPENAI_API_KEY` | *(optional)* | OpenAI API key for AI fallback |
| `ANTHROPIC_API_KEY` | *(optional)* | Claude API key for AI fallback |
| `SUTRA_SECRET_KEY` | *(auto-generated)* | 32-byte Fernet key for encrypting manuscripts at rest |

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all unit and integration tests
pytest

# Run specific test suites
pytest tests/test_web_app.py
pytest tests/test_latex_generator.py
pytest tests/test_jats_generator.py
pytest tests/test_latex_safety.py
pytest tests/test_xml_safety.py
```

---

## 📂 Project Architecture

```
sutra-engine/
├── .github/workflows/       # CI/CD: Automated GHCR Docker publish
├── sutra/                   # Core Python package
│   ├── ai/                  # Multi-model cascade router & classifiers
│   ├── generator/           # JATS 1.3 XML & LaTeX generators
│   ├── parser/              # DOCX AST parser & deterministic triage scanner
│   ├── resources/           # JATS 1.3 XSD schemas & LaTeX article templates
│   ├── tools/               # PDF layout analyzer & journal registry
│   ├── utils/               # XML validators, LaTeX compiler, AES persistence
│   └── web/                 # FastAPI routes, templates, and vanilla CSS/JS UI
├── tests/                   # Pytest test suites (unit, security, web flows)
├── inputandoutput/          # Reference manuscripts and test fixtures
├── Dockerfile               # Multi-stage production container definition
├── docker-compose.yml       # Local and staging orchestration
├── requirements.txt         # Pinned runtime dependencies
└── run_web.py               # Web server entrypoint
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
