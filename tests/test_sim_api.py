from fastapi.testclient import TestClient

import sim_api


def test_sim_state_shape():
    client = TestClient(sim_api.app)
    client.post("/sim/reset")

    response = client.get("/sim/state")
    assert response.status_code == 200
    payload = response.json()
    assert payload["body"]["backend"] == "sim"
    assert "world" in payload["body"]["sim"]
    assert "sensors" in payload["body"]["sim"]


def test_sim_command_routes_through_pipeline():
    client = TestClient(sim_api.app)
    client.post("/sim/reset")

    response = client.post("/sim/command", json={"command": "walk forward"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["event"]["action"] == "step_forward"
    assert payload["event"]["approved"] is False
    assert payload["snapshot"]["body"]["sim"]["robot"]["pose"]["x"] == 0.0


def test_sim_reset_restores_baseline():
    client = TestClient(sim_api.app)
    client.post("/sim/command", json={"command": "act curious"})
    assert client.get("/sim/state").json()["body"]["sim"]["robot"]["expression"] == "curious"

    response = client.post("/sim/reset")
    assert response.status_code == 200
    assert response.json()["body"]["sim"]["robot"]["expression"] == "neutral"


def test_scenarios_and_dashboard_static_hooks():
    client = TestClient(sim_api.app)
    scenarios = client.get("/sim/scenarios").json()["scenarios"]
    assert any(item["scenario_id"] == "blocked_walk" for item in scenarios)

    html = client.get("/").text
    assert "threeScene" in html
    assert "commandForm" in html
    assert "sensorPanel" in html
    assert "eventLog" in html
    assert "gatePanel" in html
    assert "readinessPanel" in html
    assert "proposalPanel" in html

    script = client.get("/sim_static/app.js").text
    assert "WebGLRenderer" in script
    assert "/sim/command" in script
    assert "/sim/readiness" in script
    assert "/sim/proposals/preview" in script


def test_manifest_readiness_events_export_and_replay():
    client = TestClient(sim_api.app)
    client.post("/sim/reset")
    client.post("/sim/command", json={"command": "chirp"})

    manifest = client.get("/sim/manifest").json()
    assert manifest["manifest_version"] == "robot_sim_manifest.v0.2"
    assert "play_chirp" in manifest["action_vocabulary"]

    readiness = client.get("/sim/readiness").json()
    assert readiness["advisory_only"] is True
    assert readiness["total"] >= 1

    exported = client.get("/sim/export").json()
    assert exported["export_schema"] == "robot_sim_export.v0.2"
    assert len(exported["event_log"]) >= 1

    replay = client.post("/sim/replay", json={"events": exported["event_log"]}).json()
    assert replay["final_state"]["last_action"] == "play_chirp"


def test_proposal_preview_is_review_only_until_approved():
    client = TestClient(sim_api.app)
    client.post("/sim/reset")

    preview = client.post("/sim/proposals/preview", json={"command": "act curious"}).json()["proposal"]
    assert preview["review_status"] == "pending"
    assert preview["execution_allowed"] is False
    assert client.get("/sim/state").json()["state"]["last_action"] is None

    approved = client.post(f"/sim/proposals/{preview['proposal_id']}/approve").json()
    assert approved["proposal"]["review_status"] == "approved_once"
    assert approved["snapshot"]["state"]["last_action"] == "express_curious"
