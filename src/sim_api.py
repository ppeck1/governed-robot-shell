from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from sim.manifest import build_sim_manifest, calculate_readiness
from sim.proposals import ProposalQueue
from sim.scenarios import list_scenarios, new_sim_runtime, run_all_scenarios, run_scenario

app = FastAPI(title="LLM Robot Shell Simulator", version="0.1.0")
RUNTIME = new_sim_runtime()
PROPOSALS = ProposalQueue()
STATIC_DIR = Path(__file__).parent / "sim_static"


class CommandRequest(BaseModel):
    command: str


class ReplayRequest(BaseModel):
    events: list[dict[str, Any]]


class ProposalRequest(BaseModel):
    command: str


class RejectRequest(BaseModel):
    reason: str = ""


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/sim_static/{filename}")
def static_file(filename: str) -> FileResponse:
    allowed = {"app.js", "styles.css", "three-lite.js"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="static file not found")
    return FileResponse(STATIC_DIR / filename)


@app.get("/sim/state")
def sim_state() -> dict[str, Any]:
    return RUNTIME.snapshot()


@app.get("/sim/events")
def sim_events() -> dict[str, Any]:
    return {"events": RUNTIME.snapshot()["event_log"]}


@app.get("/sim/export")
def sim_export() -> dict[str, Any]:
    return RUNTIME.export()


@app.post("/sim/replay")
def sim_replay(payload: ReplayRequest) -> dict[str, Any]:
    return RUNTIME.replay(payload.events)


@app.post("/sim/command")
def sim_command(payload: CommandRequest) -> dict[str, Any]:
    event = RUNTIME.process_command(payload.command, source="dashboard")
    return {"event": event, "snapshot": RUNTIME.snapshot()}


@app.post("/sim/reset")
def sim_reset() -> dict[str, Any]:
    global RUNTIME, PROPOSALS
    RUNTIME = new_sim_runtime()
    PROPOSALS = ProposalQueue()
    return RUNTIME.snapshot()


@app.get("/sim/scenarios")
def sim_scenarios() -> dict[str, Any]:
    return {"scenarios": list_scenarios()}


@app.post("/sim/scenarios/{scenario_id}/run")
def sim_scenario_run(scenario_id: str) -> dict[str, Any]:
    scenario_ids = {item["scenario_id"] for item in list_scenarios()}
    if scenario_id not in scenario_ids:
        raise HTTPException(status_code=404, detail="scenario not found")
    return run_scenario(scenario_id)


@app.post("/sim/scenarios/run-all")
def sim_scenario_run_all() -> dict[str, Any]:
    results = run_all_scenarios()
    return {
        "results": results,
        "passed": all(result["passed"] for result in results),
        "scenario_count": len(results),
    }


@app.get("/sim/manifest")
def sim_manifest() -> dict[str, Any]:
    return build_sim_manifest(RUNTIME.snapshot())


@app.get("/sim/readiness")
def sim_readiness() -> dict[str, Any]:
    return calculate_readiness(RUNTIME.snapshot())


@app.get("/sim/proposals")
def sim_proposals() -> dict[str, Any]:
    return {"proposals": PROPOSALS.list()}


@app.post("/sim/proposals/preview")
def sim_proposal_preview(payload: ProposalRequest) -> dict[str, Any]:
    return {"proposal": PROPOSALS.preview(payload.command, RUNTIME)}


@app.post("/sim/proposals/{proposal_id}/approve")
def sim_proposal_approve(proposal_id: str) -> dict[str, Any]:
    proposal = PROPOSALS.approve_once(proposal_id, RUNTIME)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return {"proposal": proposal, "snapshot": RUNTIME.snapshot()}


@app.post("/sim/proposals/{proposal_id}/reject")
def sim_proposal_reject(proposal_id: str, payload: RejectRequest | None = None) -> dict[str, Any]:
    proposal = PROPOSALS.reject(proposal_id, payload.reason if payload else "")
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return {"proposal": proposal}
