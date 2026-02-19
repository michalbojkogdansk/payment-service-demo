from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import time
import threading
from datetime import datetime
from typing import Optional

app = FastAPI(title="payment-service-demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── State ────────────────────────────────────────────────────────────────────

class ServiceState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.status = "healthy"          # healthy | unhealthy | recovering
        self.chaos_mode = None           # connection_pool | timeout | random_crash
        self.started_at = time.time()
        self.incident_started_at: Optional[float] = None
        self.incident_resolved_at: Optional[float] = None
        self.runbook_steps = []          # list of {step, status, ts}
        self.runbook_running = False
        self.logs = []
        self.payment_counter = 0
        self._add_log("INFO", "payment-service started successfully")
        self._add_log("INFO", "Connected to database pool (max: 100 connections)")
        self._add_log("INFO", "Listening on :8080")

    def _add_log(self, level: str, message: str):
        entry = {
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.append(entry)
        if len(self.logs) > 50:
            self.logs = self.logs[-50:]

    def add_log(self, level: str, message: str):
        self._add_log(level, message)

state = ServiceState()

# ── Background log generator ─────────────────────────────────────────────────

def log_generator():
    amounts = [44, 88, 99, 142, 176, 210, 255, 304, 89, 133, 67, 198]
    while True:
        time.sleep(12)  # new log every ~12s (5 per minute for demo pace)
        if state.status == "healthy":
            amount = random.choice(amounts)
            state.add_log("INFO", f"Payment processed OK — ${amount} (txn #{state.payment_counter + 1000})")
            state.payment_counter += 1
        elif state.status == "unhealthy":
            if state.chaos_mode == "connection_pool":
                msgs = [
                    "ERROR: Connection pool exhausted (100/100 connections in use)",
                    "WARN: Retry 3/3 failed — no connections available",
                    "ERROR: DB timeout after 30s — connection pool saturated",
                    "ERROR: Payment rejected — cannot acquire DB connection",
                    "WARN: Queue depth: 847 pending requests",
                ]
            elif state.chaos_mode == "timeout":
                msgs = [
                    "ERROR: Request timeout after 30000ms",
                    "WARN: Downstream service not responding",
                    "ERROR: Circuit breaker OPEN — payment-service",
                    "ERROR: Health probe failed (3/3 retries)",
                ]
            else:
                msgs = [
                    "FATAL: Unexpected panic in payment handler",
                    "ERROR: nil pointer dereference at payment.go:142",
                    "ERROR: Service crashed — restarting (attempt 1/3)",
                    "ERROR: Restart failed — still crashing",
                ]
            state.add_log("ERROR", random.choice(msgs))

threading.Thread(target=log_generator, daemon=True).start()

# ── Runbook automation ────────────────────────────────────────────────────────

RUNBOOK_STEPS = [
    "🔍 Health check → UNHEALTHY detected",
    "📋 Fetching logs & analyzing root cause",
    "🔄 Restarting service",
    "✅ Verifying recovery",
    "📨 Notifying team — incident report sent",
]

def run_runbook():
    state.runbook_running = True
    state.runbook_steps = []
    state.add_log("INFO", "🤖 Runbook triggered automatically")

    for i, step_name in enumerate(RUNBOOK_STEPS):
        step = {"step": step_name, "status": "running", "ts": datetime.utcnow().strftime("%H:%M:%S")}
        state.runbook_steps.append(step)

        if i == 0:
            time.sleep(random.uniform(1.5, 3.5))
            step["status"] = "done"
            state.add_log("INFO", f"Runbook [1/5]: {step_name}")

        elif i == 1:
            time.sleep(random.uniform(2.0, 5.0))
            root_cause = {
                "connection_pool": "Connection pool exhausted (100/100)",
                "timeout": "Downstream timeout — circuit breaker tripped",
                "random_crash": "Nil pointer dereference in payment handler",
            }.get(state.chaos_mode, "Unknown error")
            step["status"] = "done"
            step["detail"] = root_cause
            state.add_log("INFO", f"Root cause identified: {root_cause}")

        elif i == 2:
            time.sleep(random.uniform(3.0, 6.0))
            state.status = "recovering"
            state.add_log("INFO", "Restarting payment-service...")
            time.sleep(random.uniform(2.0, 5.0))
            state.status = "healthy"
            state.incident_resolved_at = time.time()
            step["status"] = "done"
            state.add_log("INFO", "✅ Service restarted successfully — health check PASSED")

        elif i == 3:
            time.sleep(random.uniform(1.5, 3.5))
            step["status"] = "done"
            state.add_log("INFO", "Recovery verified — payment processing resumed")

        elif i == 4:
            time.sleep(random.uniform(0.5, 2.0))
            mttr = round(state.incident_resolved_at - state.incident_started_at)
            step["status"] = "done"
            state.add_log("INFO", f"📨 Incident report: MTTR={mttr}s | Root cause: {state.chaos_mode}")

    state.runbook_running = False

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": state.status}

@app.get("/logs")
def get_logs():
    return {"logs": state.logs[-5:]}

@app.get("/state")
def get_state():
    mttr = None
    if state.incident_resolved_at and state.incident_started_at:
        mttr = round(state.incident_resolved_at - state.incident_started_at)

    incident_elapsed = None
    if state.incident_started_at and not state.incident_resolved_at:
        incident_elapsed = round(time.time() - state.incident_started_at)

    root_cause = None
    for s in state.runbook_steps:
        if s.get("detail"):
            root_cause = s["detail"]

    return {
        "status": state.status,
        "chaos_mode": state.chaos_mode,
        "uptime": round(time.time() - state.started_at),
        "incident_started_at": state.incident_started_at,
        "incident_resolved_at": state.incident_resolved_at,
        "incident_elapsed": incident_elapsed,
        "mttr": mttr,
        "runbook_running": state.runbook_running,
        "runbook_steps": state.runbook_steps,
        "logs": state.logs[-5:],
        "root_cause": root_cause,
    }

class ChaosRequest(BaseModel):
    mode: str = "connection_pool"  # connection_pool | timeout | random_crash
    auto_runbook_delay: int = 8    # seconds before runbook auto-fires

@app.post("/admin/chaos")
def trigger_chaos(req: ChaosRequest):
    if state.status != "healthy":
        return {"error": "Service is not healthy — reset first"}

    state.status = "unhealthy"
    state.chaos_mode = req.mode
    state.incident_started_at = time.time()
    state.incident_resolved_at = None
    state.runbook_steps = []

    mode_labels = {
        "connection_pool": "Connection pool exhausted",
        "timeout": "Downstream timeout",
        "random_crash": "Service panic / crash",
    }
    state.add_log("ERROR", f"🚨 INCIDENT: {mode_labels.get(req.mode, req.mode)}")

    def delayed_runbook():
        time.sleep(req.auto_runbook_delay)
        if state.status == "unhealthy" and not state.runbook_running:
            run_runbook()

    threading.Thread(target=delayed_runbook, daemon=True).start()
    return {"ok": True, "mode": req.mode}

@app.post("/admin/reset")
def reset():
    state.reset()
    return {"ok": True}

@app.get("/")
def root():
    return {"service": "payment-service-demo", "status": state.status}
