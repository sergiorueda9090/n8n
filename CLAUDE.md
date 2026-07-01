# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Aurora Financiera** is a landing page for a Colombian savings and credit cooperative (cooperativa de ahorro y crédito). It has two layers:

1. **Static frontend** — `index.html` (1,127 lines), fully self-contained; no build step.
2. **Django skeleton** — `manage.py` + `aurora/` package, SQLite DB. Currently only exposes Django admin (`/admin/`). No custom apps or views yet.

## Running the Project

**Frontend only** (no server needed; CDN resources require internet):
```bash
open index.html          # macOS
xdg-open index.html      # Linux
# or:
python3 -m http.server 8080
```

**Django backend:**
```bash
source env/bin/activate
python manage.py runserver
```

The virtual environment lives in `env/` (not `venv/`). Django settings module: `aurora.settings`. Database: `db.sqlite3` (SQLite, development only).

## Frontend Architecture (`index.html`)

File is structured top-to-bottom:

| Block | Lines (approx) | Content |
|---|---|---|
| `<head>` | 1–18 | CDN imports: Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Google Fonts |
| `<style>` | 19–579 | CSS with sections numbered 1–10 in comments |
| `<body>` | 580–945 | HTML sections in order (see below) |
| Chatbot widget | 947–988 | Demo placeholder for "Aurorita" |
| `<script>` inline | 993–1117 | Vanilla JS behaviors |
| BOTAI widget | 1118–1125 | Real bot integration script |

**Body sections in DOM order:** NAVBAR → Hero → Trust indicators → Productos (`#productos`) → Beneficios (`#beneficios`) → Proceso → Asociados/testimonials (`#asociados`) → CTA → Footer (`#contacto`)

## Design System

CSS custom properties on `:root`:

| Variable | Value | Use |
|---|---|---|
| `--af-primary` | `#0B3D6B` | Navy blue — primary brand |
| `--af-primary-dark` | `#082c4f` | Hover states |
| `--af-primary-soft` | `#e7eef5` | Subtle backgrounds |
| `--af-accent` | `#1BB8A6` | Teal — CTAs, highlights |
| `--af-accent-dark` | `#149384` | Accent hover |
| `--af-bg-light` | `#F7FAFC` | Alternating section backgrounds |
| `--af-radius-lg/md/sm` | `24px / 16px / 10px` | Border radii |

Headings: **Poppins**. Body: **Inter**. All class names are prefixed `af-`.

## Key JavaScript Behaviors

- **Navbar scroll**: adds `is-scrolled` class (white bg + shadow) after 40px scroll. Class name is `is-scrolled`, not `scrolled`.
- **Animated counters**: `IntersectionObserver` on `.af-trust` section; fires once at 40% threshold. Targets use `data-target` attribute; output formatted with `toLocaleString('es-CO')`.
- **Chatbot widget ("Aurorita")**: toggle button `#afBotToggle` / window `#afBotWindow`. State tracked via `is-open` class + `aria-hidden`. The inline `afBotForm` submit handler (line ~1105) is a demo placeholder — replace with real API call when integrating.
- **BOTAI widget** (lines 1118–1125): real bot script loaded from CloudFront with `data-agent-id` and `data-tenant-id`. This overrides the demo placeholder at runtime.

## Image Assets

Large PNGs in the project root (Hero.png ~7.6 MB, client photos ~7 MB each). All use `loading="lazy"`. If optimizing: convert to WebP and serve via CDN.

## Accessibility

- `@media (prefers-reduced-motion)` sets all animation/transition durations to `0.001ms`.
- Focus outlines: `3px solid var(--af-accent)` on all interactive elements.
- Semantic heading hierarchy h1 → h2 → h3 throughout.
- Chat window has `role="dialog"` and `aria-live="polite"` on the messages container.

## Warning: Sensitive File

`n8n-bedrock-ocr_accessKeys.csv` in the project root contains AWS access keys. Do not commit or share this file; add it to `.gitignore` if not already excluded.
