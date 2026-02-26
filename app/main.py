from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
import os
import random
import time
import threading
from datetime import datetime
from typing import Optional

app = FastAPI(title="payment-service-demo")

DEMO_SECRET = os.environ.get("DEMO_SECRET")
if not DEMO_SECRET:
    raise RuntimeError("DEMO_SECRET env var is required — set it in Render environment variables")

def require_secret(x_demo_secret: str = Header(default="")):
    if DEMO_SECRET and x_demo_secret != DEMO_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

_runbook_lock = threading.Lock()

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://michalbojkogdansk.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Demo-Secret"],
)

# ── Service State ─────────────────────────────────────────────────────────────

class ServiceState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.status = "healthy"
        self.chaos_mode = None
        self.started_at = time.time()
        self.incident_started_at: Optional[float] = None
        self.incident_resolved_at: Optional[float] = None
        self.runbook_steps = []
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

# ── Challenge State ───────────────────────────────────────────────────────────

CHALLENGE_STEPS = [
    {
        "id": 0,
        "title": "Step 1 — Alert Received",
        "situation": "It's 2:47 AM. CRITICAL alert fires:\n'Payment Service Latency > 2s'\n\nWhat do you do first?",
        "options": {
            "A": "Check the logs to understand the error",
            "B": "Restart the service immediately",
            "C": "Probably a false positive — go back to sleep",
            "D": "Call the database team immediately"
        },
        "correct": "A",
        "hint": "67% of alerts are false positives — but CRITICAL means $5,600/min. Always diagnose first.",
        "explanation": "Blind restarts can corrupt active transactions. Diagnose before acting."
    },
    {
        "id": 1,
        "title": "Step 2 — Reading Logs",
        "situation": "You open the logs and see:\n\nERROR: Connection pool exhausted (100/100)\nWARN:  Retry 3/3 failed — no connections available\nERROR: Payment rejected — cannot acquire DB connection\n\nWhat is the root cause?",
        "options": {
            "A": "Network connectivity failure",
            "B": "Memory leak in application",
            "C": "Connection pool exhausted — too many open DB connections",
            "D": "Database server crashed"
        },
        "correct": "C",
        "hint": "The log says it directly: 'Connection pool exhausted (100/100)'",
        "explanation": "Always read what the error message tells you directly before assuming."
    },
    {
        "id": 2,
        "title": "Step 3 — Assess the Problem",
        "situation": "You check system metrics:\n\nCPU:            23%   (normal)\nMemory:         44%   (normal)\nDB connections: 100/100  (MAXED)\nNetwork:        OK\n\nWhat type of problem is this?",
        "options": {
            "A": "Infrastructure problem — call DevOps",
            "B": "DDoS attack — block incoming traffic",
            "C": "Database server down — call DBA",
            "D": "Application-level issue — DB connection management"
        },
        "correct": "D",
        "hint": "CPU and memory are fine. The bottleneck is application logic, not infrastructure.",
        "explanation": "Knowing the problem type directs you to the right team and the right runbook."
    },
    {
        "id": 3,
        "title": "Step 4 — Find the Runbook",
        "situation": "You open the runbook library:\n\nNET-001  Network Outage\nDB-003   Connection Pool Exhaustion\nAPP-007  Memory Leak\nSEC-002  DDoS Mitigation\n\nWhich procedure applies?",
        "options": {
            "A": "DB-003: Connection Pool Exhaustion",
            "B": "NET-001: Network Outage",
            "C": "APP-007: Memory Leak",
            "D": "SEC-002: DDoS Mitigation"
        },
        "correct": "A",
        "hint": "Match the root cause to the procedure — Connection Pool maps to DB section",
        "explanation": "A precise runbook match prevents wasted steps and directly reduces MTTR."
    },
    {
        "id": 4,
        "title": "Step 5 — Drain Connections",
        "situation": "DB-003 runbook says:\n'Before restarting, gracefully drain active connections'\n\nWhich command do you run?",
        "options": {
            "A": "kill -9 $(pgrep payment-service)",
            "B": "systemctl stop payment-service",
            "C": "./drain.sh --graceful --timeout 10",
            "D": "pkill -SIGTERM payment"
        },
        "correct": "C",
        "hint": "Graceful drain lets active transactions complete — prevents data loss",
        "explanation": "Force-kill drops active DB transactions mid-flight. Graceful drain is the safe path."
    },
    {
        "id": 5,
        "title": "Step 6 — Under Pressure",
        "situation": "Drain is running. 8 seconds remaining.\nYour manager pings Slack:\n'FIX IT NOW — CEO is watching the dashboard!'\n\nWhat do you do?",
        "options": {
            "A": "Interrupt drain and restart immediately",
            "B": "Ask manager to make the decision",
            "C": "Escalate to VP Engineering",
            "D": "Reply 'on it' and wait for drain to finish"
        },
        "correct": "D",
        "hint": "8 seconds vs potential data corruption — the math is clear",
        "explanation": "Pressure-driven shortcuts in incident response cause secondary incidents."
    },
    {
        "id": 6,
        "title": "Step 7 — Service Restart",
        "situation": "Connections drained. Ready to restart.\nSystem warning: 'Restart during peak traffic hours?'\n\nThe service is already down. What do you do?",
        "options": {
            "A": "Postpone until off-peak hours",
            "B": "Proceed — service is already failing",
            "C": "Roll back to previous version instead",
            "D": "Scale horizontally — add more instances"
        },
        "correct": "B",
        "hint": "The service is already down. Delaying the restart only extends downtime.",
        "explanation": "A timing warning is irrelevant when the service is already failing customers."
    },
    {
        "id": 7,
        "title": "Step 8 — Monitor Recovery",
        "situation": "Service restarted.\nFirst health check returns:\n\nHTTP 200 OK\n\nIs the incident resolved?",
        "options": {
            "A": "No — wait for 3 consecutive healthy responses",
            "B": "Yes — close the incident immediately",
            "C": "No — monitor for at least 30 minutes",
            "D": "Yes — notify the team right now"
        },
        "correct": "A",
        "hint": "Services often flap after restart — one 200 OK can be a fluke",
        "explanation": "3 consecutive healthy responses is a reasonable signal. 1 is not enough."
    },
    {
        "id": 8,
        "title": "Step 9 — Recovery Confirmed",
        "situation": "3x consecutive HTTP 200 OK\nLogs: 'Payment processed OK — $142 (txn #1247)'\nDB connections: 23/100\n\nService is healthy. What is next?",
        "options": {
            "A": "Go back to sleep — it is 3:15 AM",
            "B": "Add more DB connection slots to prevent recurrence",
            "C": "Write incident report while details are fresh",
            "D": "Deploy a hotfix immediately"
        },
        "correct": "C",
        "hint": "Without documentation, this same incident will repeat in 2 weeks",
        "explanation": "Blameless post-mortems close the loop and prevent repeat incidents."
    },
    {
        "id": 9,
        "title": "Step 10 — Post-Mortem",
        "situation": "You open the incident report template.\n\nWhat is the single most important field to fill in?",
        "options": {
            "A": "Timeline of events (minute by minute)",
            "B": "Root cause + corrective action to prevent recurrence",
            "C": "Names of engineers involved",
            "D": "Business impact in dollars"
        },
        "correct": "B",
        "hint": "Timeline and impact are useful — but root cause is what stops the next 2 AM wake-up",
        "explanation": "Root cause + corrective action is the only field that prevents recurrence."
    }
]


class ChallengeState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.step = -1
        self.started_at: Optional[float] = None
        self.step_started_at: Optional[float] = None
        self.votes: dict = {}        # {step_id: {"A": 0, ...}}
        self.revealed: set = set()   # set of step_ids where answer was revealed
        self.crowd_correct = 0
        self.step_results: list = []
        self.total_votes_cast = 0


challenge = ChallengeState()

# ── Background log generator ──────────────────────────────────────────────────

def log_generator():
    amounts = [44, 88, 99, 142, 176, 210, 255, 304, 89, 133, 67, 198]
    while True:
        time.sleep(12)
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
    with _runbook_lock:
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

# ── Service Endpoints ─────────────────────────────────────────────────────────

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

VALID_CHAOS_MODES = {"connection_pool", "timeout", "random_crash"}

class ChaosRequest(BaseModel):
    mode: str = "connection_pool"
    auto_runbook_delay: int = 8

    @validator('mode')
    def mode_must_be_valid(cls, v):
        if v not in VALID_CHAOS_MODES:
            raise ValueError(f"mode must be one of {VALID_CHAOS_MODES}")
        return v

@app.post("/admin/chaos")
def trigger_chaos(req: ChaosRequest, _: str = Depends(require_secret)):
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
def reset(_: str = Depends(require_secret)):
    state.reset()
    return {"ok": True}

@app.get("/")
def root():
    return {"service": "payment-service-demo", "status": state.status}

# ── Challenge Endpoints ───────────────────────────────────────────────────────

@app.get("/challenge/state")
def get_challenge_state():
    elapsed = round(time.time() - challenge.started_at) if challenge.started_at else 0
    step_elapsed = round(time.time() - challenge.step_started_at) if challenge.step_started_at else 0
    done = challenge.step >= len(CHALLENGE_STEPS)

    current_step_data = None
    if 0 <= challenge.step < len(CHALLENGE_STEPS):
        s = CHALLENGE_STEPS[challenge.step]
        votes = challenge.votes.get(challenge.step, {"A": 0, "B": 0, "C": 0, "D": 0})
        total_votes = sum(votes.values())
        is_revealed = challenge.step in challenge.revealed
        current_step_data = {
            "id": s["id"],
            "title": s["title"],
            "situation": s["situation"],
            "options": s["options"],
            "votes": votes,
            "total_votes": total_votes,
            "revealed": is_revealed,
            "correct": s["correct"] if is_revealed else None,
            "hint": s["hint"] if is_revealed else None,
            "explanation": s["explanation"] if is_revealed else None,
        }

    results = None
    if done:
        results = {
            "crowd_correct": challenge.crowd_correct,
            "total_steps": len(CHALLENGE_STEPS),
            "crowd_accuracy_pct": round(challenge.crowd_correct / len(CHALLENGE_STEPS) * 100),
            "total_votes": challenge.total_votes_cast,
            "elapsed": elapsed,
        }

    return {
        "active": challenge.active,
        "step": challenge.step,
        "total_steps": len(CHALLENGE_STEPS),
        "elapsed": elapsed,
        "step_elapsed": step_elapsed,
        "current_step": current_step_data,
        "done": done,
        "results": results,
    }


class VoteRequest(BaseModel):
    step_id: int
    option: str


@app.post("/challenge/vote")
def submit_vote(req: VoteRequest):
    if not challenge.active:
        return {"error": "Challenge not active"}
    if req.step_id != challenge.step:
        return {"error": "Wrong step"}
    if req.option not in ["A", "B", "C", "D"]:
        return {"error": "Invalid option"}
    if req.step_id not in challenge.votes:
        challenge.votes[req.step_id] = {"A": 0, "B": 0, "C": 0, "D": 0}
    challenge.votes[req.step_id][req.option] += 1
    challenge.total_votes_cast += 1
    total = sum(challenge.votes[req.step_id].values())
    return {"ok": True, "total": total}


@app.post("/challenge/start")
def start_challenge(_: str = Depends(require_secret)):
    if challenge.active:
        return {"ok": True, "message": "Already running"}
    challenge.reset()
    challenge.active = True
    challenge.step = 0
    challenge.started_at = time.time()
    challenge.step_started_at = time.time()
    challenge.votes[0] = {"A": 0, "B": 0, "C": 0, "D": 0}
    return {"ok": True}


@app.post("/challenge/reveal")
def reveal_answer(_: str = Depends(require_secret)):
    if not challenge.active or challenge.step < 0:
        return {"error": "Not active"}
    if challenge.step in challenge.revealed:
        return {"ok": True, "already_revealed": True}

    votes = challenge.votes.get(challenge.step, {"A": 0, "B": 0, "C": 0, "D": 0})
    total = sum(votes.values())
    correct = CHALLENGE_STEPS[challenge.step]["correct"]

    if total > 0:
        majority = max(votes, key=lambda k: votes[k])
        crowd_was_correct = majority == correct
    else:
        majority = None
        crowd_was_correct = False

    if crowd_was_correct:
        challenge.crowd_correct += 1

    challenge.step_results.append({
        "step_id": challenge.step,
        "correct_option": correct,
        "majority_option": majority,
        "crowd_was_correct": crowd_was_correct,
    })

    challenge.revealed.add(challenge.step)
    return {"ok": True, "correct": correct}


@app.post("/challenge/next")
def next_step(_: str = Depends(require_secret)):
    if not challenge.active:
        return {"error": "Not active"}
    # Auto-reveal current step if not yet revealed
    if challenge.step >= 0 and challenge.step not in challenge.revealed:
        reveal_answer()

    challenge.step += 1
    challenge.step_started_at = time.time()
    if challenge.step < len(CHALLENGE_STEPS):
        challenge.votes[challenge.step] = {"A": 0, "B": 0, "C": 0, "D": 0}
    else:
        challenge.active = False
    return {"ok": True, "step": challenge.step}


@app.post("/challenge/reset")
def reset_challenge(_: str = Depends(require_secret)):
    challenge.reset()
    return {"ok": True}
