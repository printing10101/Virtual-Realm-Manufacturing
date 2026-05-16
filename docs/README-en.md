# Virtual-Realm-Manufacturing

[![Lint](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/lint.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/lint.yml)
[![Test](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/test.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/test.yml)
[![Build](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/build.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/build.yml)

Virtual-Realm-Manufacturing is an AI-powered desktop application designed for the manufacturing industry. It addresses a core challenge in mechanical machining: the inefficiency, high skill barrier, and data security risks across the entire "drawing-to-NC-code" pipeline. It automatically parses engineering orthographic views, reconstructs 3D models, plans machining processes, and generates machine-ready NC code — all running locally on-device with zero cloud dependency. Built around a "data stays on-premise" security principle, it integrates local large language models, process knowledge graphs, and mathematical programming solvers to deliver high-precision, production-ready machining solutions while keeping enterprise工艺 data fully protected. This empowers small and mid-size manufacturers with industrial-grade AI tools that truly serve the shop floor.

## Features

- **2D Drawing Parsing** — Automatically recognizes orthographic views (front, top, side) and reconstructs accurate 3D models
- **Intelligent Process Planning** — Generates optimized machining process plans based on model geometry and material properties
- **NC Code Generation** — Produces machine-ready G-code that can be directly deployed to CNC equipment
- **Local-Only Processing** — All computation runs on-device; no data ever leaves the factory network
- **AI Decision Audit** — Full traceability of AI recommendations, user modifications, and final execution actions
- **Agent Token Management** — Granular permission scopes (Read/Write/Train/Notify/Manage/Execute) for external AI tool integration
- **Adaptive Autonomy Levels** — Five-tier AI autonomy from fully manual to fully automatic, configurable per user preference
- **Real-Time Health Dashboard** — Live monitoring of backend status, memory, CPU, active models, and inference performance

## Tech Stack

- **Frontend**: Vue 3 + TypeScript + Vite + Element Plus
- **Desktop Shell**: Tauri 2.x (Rust-based cross-platform runtime)
- **Backend**: Python FastAPI sidecar with LNN neural network inference engine
- **Database**: SQLite + Redis + Prometheus metrics
- **AI Engine**: Local LLM (Ollama) + PyTorch + custom neural process models

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Rust toolchain (for Tauri builds)
- Python 3.11+ with pip

### Installation

```bash
# Clone the repository
git clone https://github.com/printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing

# Install frontend dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt

# Start development server
npm run tauri dev
```

### Build for Production

```bash
npm run tauri build
```

## Internationalization (i18n)

The application supports both **Chinese (zh-CN)** and **English (en)** interfaces. Language preference is stored in `localStorage` and persists across sessions. You can switch languages at any time from the **Settings** page.

### Adding a New Language

1. Create a new locale file at `src/locales/<lang-code>.ts` following the structure of existing locale files
2. Register the locale in `src/i18n/index.ts` by importing and adding it to the `messages` object
3. Add the language option to the settings page in `src/views/Settings.vue`
4. (Optional) Import the corresponding Element Plus locale from `element-plus/es/locale/lang/<lang-code>`

## Project Structure

```
├── src/                      # Vue 3 frontend source
│   ├── components/           # Reusable UI components
│   ├── views/                # Page-level components
│   ├── stores/               # Pinia state management
│   ├── locales/              # i18n language packs (zh-CN, en)
│   ├── i18n/                 # Vue-i18n configuration
│   └── router/               # Vue Router configuration
├── src-tauri/                # Tauri Rust backend
│   ├── src/                  # Rust source code
│   ├── Cargo.toml            # Rust dependencies
│   └── tauri.conf.json       # Tauri app configuration
├── python/                   # Python sidecar (FastAPI + LNN)
│   ├── app/                  # Application source
│   └── tests/                # Python test suite
├── docs/                     # Project documentation
└── scripts/                  # Build and utility scripts
```

## License

MIT
