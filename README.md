# 💳 payment-service-demo

> **Failure Fatigue** conference demo — live runbook automation vs manual incident response.

## 🎬 What it does

A realistic payment microservice with a chaos engine and automated runbook. Built for live conference demos showing the impact of **Failure Fatigue** and the power of **Runbook as Code**.

### Demo flow
1. Open the dashboard — service is green, logs stream normally
2. Press **Trigger Chaos** (hidden from audience)
3. Service turns red — error logs appear
4. Automated runbook fires in ~8 seconds — steps visible in real time
5. Manual timeline ticks in parallel (showing what a human would take: **47 minutes**)
6. Incident resolved — MTTR summary appears with speedup factor

## 🏗️ Architecture

```
GitHub Pages (frontend)  →  Render.com (FastAPI backend)
        ↕ polls every 3s via REST
```

## 🚀 Deployment

### Backend (Render.com)
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect this GitHub repo
3. Settings are auto-detected from `render.yaml`
4. Copy the deployed URL (e.g. `https://payment-service-demo-xxxx.onrender.com`)

### Frontend (GitHub Pages)
1. Go to repo Settings → Pages
2. Source: `Deploy from branch` → `main` → `/docs`
3. Open `https://michalbojkogdansk.github.io/payment-service-demo`
4. Paste the Render URL in the "Connect" field

## 🎛️ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health status |
| GET | `/logs` | Last 5 log entries |
| GET | `/state` | Full state (status, runbook, MTTR) |
| POST | `/admin/chaos` | Trigger chaos mode |
| POST | `/admin/reset` | Reset to healthy |

### Chaos modes
```json
{ "mode": "connection_pool", "auto_runbook_delay": 8 }
{ "mode": "timeout",         "auto_runbook_delay": 8 }
{ "mode": "random_crash",    "auto_runbook_delay": 8 }
```

## 📊 MTTR comparison

| Response type | MTTR |
|--------------|------|
| 🤖 Automated runbook | ~15–20 seconds |
| 👤 Manual response   | ~47 minutes    |
| **Speedup**          | **~140×**      |

---
*Built for "Failure Fatigue" talk — Michał Bojko, Dynatrace*
