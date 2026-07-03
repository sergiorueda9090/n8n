# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Aurora Financiera** is a landing page for a Colombian savings and credit cooperative (cooperativa de ahorro y crédito), built as a **Django 4.0 site** that serves the marketing page and proxies a multimodal chatbot ("Aurorita") to an n8n webhook.

The site is a single `landing` app. There are no database models yet — SQLite exists only for Django sessions (used to keep a stable `chat_id`) and admin. Content is a marketing page; the "backend" is essentially a thin chat proxy.

### Legacy file — do not edit
`index.html` (root, ~1,300 lines) is the **original standalone prototype** and is no longer served. The live site is `landing/templates/`. When making frontend changes, edit the templates and `landing/static/aurora/` assets, **not** `index.html`.

## Running the Project

The virtualenv lives in `env/` (not `venv/`). Settings module: `aurora.settings`.

```bash
source env/bin/activate
python manage.py runserver         # http://127.0.0.1:8000/
python manage.py collectstatic     # gather static into STATIC_ROOT (prod)
python manage.py migrate           # sessions/admin tables
```

There are no tests, linters, or build step configured.

### Configuration (python-decouple)
`aurora/settings.py` reads all secrets/config from a `.env` file in the project root via `python-decouple` (`config(...)`). `SECRET_KEY` is **required** — the app will not start without a `.env`. Copy `.env.produccion.example` as a starting point. Key vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `N8N_WEBHOOK_URL`, `DB_ENGINE`/`DB_*` (SQLite by default, PostgreSQL/Supabase optional), `STATIC_ROOT`.

## Routes & Views (`landing/`)

URLs are namespaced `landing:` (see `aurora/urls.py` → `landing/urls.py`):

| Path | View | Purpose |
|---|---|---|
| `/` | `home` | Marketing landing page (`landing/home.html`) |
| `/agente/` | `agent_dashboard` | Renders `landing/agent-dashboard.html` |
| `/kpis/` | `kpi_dashboard` | Executive dashboard; 6 KPIs computed live from Supabase (`landing/kpis.py`) |
| `/api/chat/` | `chat_api` | POST-only JSON proxy to n8n for the chatbot |
| `/admin/` | Django admin | — |

## Chatbot Architecture ("Aurorita")

The chat is a **server-side proxy**, not a direct browser→n8n call. Flow:

1. **Browser** (`aurora.js`) reads `data-chat-url` and `data-csrf` from the `#afBotForm` element and POSTs JSON to `/api/chat/` with the CSRF token. One modality per request: `{mensaje}` (text), `{audio}` (base64), or `{imagen, formato}` (base64 + MIME).
2. **`chat_api`** (`landing/views.py`) validates exactly-one-modality, enforces size limits (image 5 MB, audio 10 MB, formats JPG/PNG/WebP), strips any `data:...;base64,` prefix, and injects a **session-derived `chat_id`** (`web-<hex>`, stored in `request.session` — never trusted from the client).
3. **`n8n_client.py`** (`forward` / `extract_reply`) POSTs to `settings.N8N_WEBHOOK_URL` using only stdlib `urllib` (no extra deps). It tolerates n8n returning a list, plain text, or various reply keys (`respuesta`, `output`, `mensaje`, `text`, `reply`, `message`), and normalizes to `{respuesta: "..."}`.

Errors always return a friendly Spanish `{respuesta}` (400 on bad input, 502 on n8n failure) so the widget never shows a raw error.

**BOTAI Widget** (base.html, bottom): a third-party CloudFront/`v2.botai...` script is present but **commented out** — the custom `aurora.js` widget above is what's active.

## Frontend (`landing/`)

Django templates + a shared CSS/JS bundle. No framework, no build.

- `templates/base.html` — layout: `<head>` (CDN Bootstrap 5.3.3 + Bootstrap Icons + Google Fonts), NAVBAR, `{% block content %}`, FOOTER (`#contacto`), and the Aurorita chat widget markup. Child pages `{% extends "base.html" %}`.
- `templates/landing/home.html` — the marketing page body in DOM order: Hero (`#inicio`) → Trust indicators → Productos (`#productos`) → Beneficios (`#beneficios`) → Proceso → Asociados/testimonials (`#asociados`) → CTA.
- `static/aurora/css/aurora.css` (~616 lines) — all styles; CSS sections numbered in comments.
- `static/aurora/js/aurora.js` (~391 lines) — all behaviors (see below).
- `static/img/` — site images (Hero, clients, Aurorita), served via `{% static %}`. Root-level PNGs/JPEGs are duplicates ignored by git.

### Design system (`:root` in aurora.css)
| Variable | Value | Use |
|---|---|---|
| `--af-primary` | `#0B3D6B` | Navy — primary brand |
| `--af-primary-dark` | `#082c4f` | Hover states |
| `--af-primary-soft` | `#e7eef5` | Subtle backgrounds |
| `--af-accent` | `#1BB8A6` | Teal — CTAs, highlights |
| `--af-accent-dark` | `#149384` | Accent hover |
| `--af-bg-light` | `#F7FAFC` | Alternating section backgrounds |
| `--af-radius-lg/md/sm` | `24px / 16px / 10px` | Border radii |

Headings: **Poppins**. Body: **Inter**. All class names are prefixed `af-`.

### Key JS behaviors (`aurora.js`)
- **Navbar scroll**: adds `is-scrolled` class (white bg + shadow) after 40px scroll. The class is `is-scrolled`, not `scrolled`. Mobile menu (`#afNavCollapse`) uses Bootstrap Collapse and closes on link click.
- **Animated counters**: `IntersectionObserver` fires once at 40% threshold; targets read `data-target`, output formatted with `toLocaleString('es-CO')`.
- **Chat widget**: toggle `#afBotToggle` / window `#afBotWindow`, state via `is-open` class + `aria-hidden`. Supports typing, image attach (`#afBotFile`), and mic/audio (`#afBotMic`). `AF_CHAT_URL`/`AF_CSRF` are read from the form's `data-*` attributes.

### Accessibility
- `@media (prefers-reduced-motion)` sets animation/transition durations to `0.001ms`.
- Focus outlines: `3px solid var(--af-accent)` on interactive elements.
- Chat window has `role="dialog"`; messages container is `aria-live="polite"`.

## Deployment (`deploy/`, `DESPLIEGUE.md`)

Production runs on EC2 behind **Apache (reverse proxy + static) → Gunicorn → Django**. Full step-by-step is in `DESPLIEGUE.md` (Spanish; also `DESPLIEGUE.pdf`).

- `deploy/gunicorn.service` — systemd unit; Gunicorn binds `127.0.0.1:8001`, runs from `/var/www/aurora`, reads `.env` from `WorkingDirectory`. `User=ubuntu` (owns code + deploy key).
- `deploy/aurora-apache.conf` — Apache serves `/static/` directly (`ProxyPass /static/ !`) and proxies everything else to `:8001`. **HTTPS/proxy contract**: Apache must send `X-Forwarded-Proto`; `settings.py` sets `SECURE_PROXY_SSL_HEADER` accordingly and enables secure cookies when `DEBUG=False`. After Certbot creates the `:443` vhost, its `RequestHeader` must be `https`.
- Deploy model: git clone on the EC2 via a **read-only GitHub Deploy Key** (repo is private).

## Sensitive files (never commit)
`.gitignore` already excludes: `.env`, `n8n-bedrock-ocr_accessKeys.csv` (AWS access keys), `*.pem`, `db.sqlite3`, `/staticfiles/`, and root media duplicates. Do not remove these exclusions or commit the listed files.
