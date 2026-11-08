#!/usr/bin/env python3
"""Seeds a local YouTrack sandbox with the Golden Dataset and issues a permanent token.

  docker compose -f docker-compose.e2e.yml --profile sandbox up -d --wait youtrack
  python3 -I e2e/youtrack-sandbox/seed.py            # project GOLD + 24 backlog + 9 In Progress issues
  python3 -I e2e/youtrack-sandbox/seed.py --reset    # delete project GOLD first

Prints `export YOUTRACK_SANDBOX_URL=... YOUTRACK_SANDBOX_TOKEN=...` and writes them to
e2e/youtrack-sandbox/.env (git-ignored). Local sandbox only: admin/admin, bound to 127.0.0.1.
Real API behaviour is the point: our WireMock fixtures are hand-written, this checks them.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = "http://127.0.0.1:8088"
AUTH = "Basic " + base64.b64encode(b"admin:admin").decode()
PROJECT = "GOLD"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via HTTP_PROXY


class ApiError(RuntimeError):
    pass


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": AUTH, "Accept": "application/json",
                                          "Content-Type": "application/json"})
    try:
        with OPENER.open(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise ApiError(f"{method} {path} -> {e.code}: {e.read().decode(errors='replace')[:400]}") from None


def wait_ready(timeout_s: int = 300) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            call("GET", "/api/users/me?fields=id")
            return
        except (ApiError, OSError):
            time.sleep(5)
    raise SystemExit(f"YouTrack not ready at {BASE} after {timeout_s}s")


def project_fields(pid: str) -> dict:
    fields = call("GET", f"/api/admin/projects/{pid}/customFields?fields=id,field(name),bundle(id,values(name))&$top=100")
    return {f["field"]["name"]: f for f in fields}


def ensure_bundle_values(kind: str, bundle: dict, names: set[str], extra: dict | None = None) -> None:
    existing = {v["name"] for v in bundle.get("values", [])}
    for name in sorted(names - existing):
        call("POST", f"/api/admin/customFieldSettings/bundles/{kind}/{bundle['id']}/values?fields=id",
             {"name": name, **(extra or {})})


def global_field(name: str, field_type: str) -> str:
    for f in call("GET", "/api/admin/customFieldSettings/customFields?fields=id,name&$top=200"):
        if f["name"] == name:
            return f["id"]
    return call("POST", "/api/admin/customFieldSettings/customFields?fields=id",
                {"name": name, "fieldType": {"id": field_type}, "isAutoAttached": False})["id"]


def epoch_noon_utc(date: str) -> int:
    d = dt.date.fromisoformat(date)
    return int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp() * 1000)


def tag_id(name: str, cache: dict) -> str:
    if name not in cache:
        found = [t for t in call("GET", f"/api/tags?fields=id,name&query={urllib.request.quote(name)}&$top=50")
                 if t["name"] == name]
        cache[name] = found[0]["id"] if found else call("POST", "/api/tags?fields=id", {"name": name})["id"]
    return cache[name]


def main(argv: list[str]) -> int:
    ds = json.loads((ROOT / "evals/golden/dataset.json").read_text(encoding="utf-8"))
    wait_ready()
    me = call("GET", "/api/users/me?fields=id")["id"]

    existing = [p for p in call("GET", "/api/admin/projects?fields=id,shortName&$top=200") if p["shortName"] == PROJECT]
    if existing and "--reset" in argv:
        call("DELETE", f"/api/admin/projects/{existing[0]['id']}")
        for _ in range(60):  # deletion is asynchronous; name/shortName stay taken until it finishes
            if not any(p["shortName"] == PROJECT or p["name"] == "Golden Dataset"
                       for p in call("GET", "/api/admin/projects?fields=shortName,name&$top=200")):
                break
            time.sleep(2)
        else:
            raise SystemExit(f"project {PROJECT} still exists 120 s after DELETE")
        existing = []
    if existing:
        raise SystemExit(f"project {PROJECT} already exists; rerun with --reset to recreate it")
    pid = call("POST", "/api/admin/projects?fields=id", {"name": "Golden Dataset", "shortName": PROJECT,
                                                        "leader": {"id": me}})["id"]

    # field values the dataset uses that a default YouTrack project lacks
    tasks = ds["tasks"]
    pf = project_fields(pid)
    ensure_bundle_values("state", pf["State"]["bundle"], {t["state"] for t in tasks} | {"In Progress"}, {"isResolved": False})
    ensure_bundle_values("enum", pf["Type"]["bundle"], {t["type"] for t in tasks})
    ensure_bundle_values("enum", pf["Priority"]["bundle"], {t["priority"] for t in tasks})

    # multi-value "Subsystems" (default "Subsystem" is single-value; GOLD-4 has two)
    subsystems = sorted({s for t in tasks for s in t["subsystem"]})
    bundle = call("POST", "/api/admin/customFieldSettings/bundles/ownedField?fields=id",
                  {"$type": "OwnedBundle", "name": f"{PROJECT} Subsystems {int(time.time())}",
                   "values": [{"$type": "OwnedBundleElement", "name": s} for s in subsystems]})
    call("POST", f"/api/admin/projects/{pid}/customFields?fields=id",
         {"field": {"id": global_field("Subsystems", "ownedField[*]")}, "bundle": {"id": bundle["id"], "$type": "OwnedBundle"},
          "$type": "OwnedProjectCustomField", "canBeEmpty": True})
    call("POST", f"/api/admin/projects/{pid}/customFields?fields=id",
         {"field": {"id": global_field("Story points", "float")}, "$type": "SimpleProjectCustomField", "canBeEmpty": True})
    if "Due Date" not in pf:
        call("POST", f"/api/admin/projects/{pid}/customFields?fields=id",
             {"field": {"id": global_field("Due Date", "date")}, "$type": "SimpleProjectCustomField", "canBeEmpty": True})

    tags: dict[str, str] = {}

    def create(summary, description, state, type_, priority, subs, due, sp, tag_names) -> str:
        fields = [
            {"name": "State", "$type": "StateIssueCustomField", "value": {"name": state}},
            {"name": "Type", "$type": "SingleEnumIssueCustomField", "value": {"name": type_}},
            {"name": "Priority", "$type": "SingleEnumIssueCustomField", "value": {"name": priority}},
            {"name": "Subsystems", "$type": "MultiOwnedIssueCustomField", "value": [{"name": s} for s in subs]},
        ]
        if due:
            fields.append({"name": "Due Date", "$type": "DateIssueCustomField", "value": epoch_noon_utc(due)})
        if sp is not None:
            fields.append({"name": "Story points", "$type": "SimpleIssueCustomField", "value": sp})
        issue = call("POST", "/api/issues?fields=id,idReadable",
                     {"project": {"id": pid}, "summary": summary, "description": description, "customFields": fields})
        for name in tag_names:
            call("POST", f"/api/issues/{issue['id']}/tags?fields=id", {"id": tag_id(name, tags)})
        return issue["idReadable"]

    for t in tasks:  # created in dataset order, so ids are GOLD-1 .. GOLD-24
        got = create(t["summary"], t["description"], t["state"], t["type"], t["priority"], t["subsystem"],
                     t["due_date"], t["story_points"], t["tags"])
        if got != t["id"]:
            raise SystemExit(f"expected {t['id']}, YouTrack assigned {got}: recreate with --reset")
    for w in ds["wip"]:
        create(w["summary"], "", "In Progress", "Task", "Normal", [], None, 3, [])

    # permanent token for the MCP server (scope: YouTrack service)
    hub_me = call("GET", "/hub/api/rest/users/me?fields=id")["id"]
    service = next(s["id"] for s in call("GET", "/hub/api/rest/services?fields=id,applicationName&$top=50")["services"]
                   if s.get("applicationName") == "YouTrack")
    token = call("POST", f"/hub/api/rest/users/{hub_me}/permanenttokens?fields=token",
                 {"name": f"backlog-mcp-sandbox-{int(time.time())}", "scope": [{"id": service}]})["token"]

    env = f"export YOUTRACK_SANDBOX_URL={BASE}\nexport YOUTRACK_SANDBOX_TOKEN={token}\n"
    (HERE / ".env").write_text(env, encoding="utf-8")
    print(f"seeded {len(tasks)} backlog + {len(ds['wip'])} In Progress issues in {PROJECT}", file=sys.stderr)
    print(env, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
