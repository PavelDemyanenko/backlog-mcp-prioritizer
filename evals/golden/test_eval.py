"""Eval pipeline tests (no LLM).  Run: python3 -I -m unittest discover -s evals/golden"""
import contextlib
import copy
import io
import csv
import json
import math
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import agreement  # noqa: E402
import build  # noqa: E402
import consensus  # noqa: E402
import metrics  # noqa: E402
import run_eval  # noqa: E402

DATASET = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
SAMPLE = HERE / "replay/compliant-sample.json"
CRITICAL = {"GOLD-3", "GOLD-4", "GOLD-5", "GOLD-19"}
# SYNTHETIC relevance used only to exercise the pipeline.
SYNTH_REL = {"GOLD-14": 3, "GOLD-1": 3, "GOLD-16": 3, "GOLD-21": 2, "GOLD-10": 2, "GOLD-11": 2, "GOLD-17": 2,
             "GOLD-24": 1, "GOLD-7": 2, "GOLD-15": 1, "GOLD-6": 2, "GOLD-2": 1, "GOLD-22": 1, "GOLD-18": 0,
             "GOLD-20": 1, "GOLD-23": 0, "GOLD-9": 0, "GOLD-8": 2, "GOLD-12": 1, "GOLD-13": 0}


def synthetic_gold() -> dict:
    tasks = {}
    for t in DATASET["tasks"]:
        tid = t["id"]
        tasks[tid] = {"critical": True} if tid in CRITICAL else {"critical": False, "relevance": float(SYNTH_REL[tid])}
    return {"dataset_version": DATASET["version"], "experts": ["synthetic"], "relevance_kappa": 1.0, "tasks": tasks}


class Ndcg(unittest.TestCase):
    def test_perfect_order_is_one(self):
        rel = {"a": 3, "b": 2, "c": 0}
        self.assertAlmostEqual(metrics.ndcg_at_k(["a", "b", "c"], rel, 3), 1.0)

    def test_hand_computed_value(self):
        rel = {"a": 3, "b": 2, "c": 0}
        dcg = (2**0 - 1) / math.log2(2) + (2**3 - 1) / math.log2(3) + (2**2 - 1) / math.log2(4)
        idcg = 7 / math.log2(2) + 3 / math.log2(3)
        self.assertAlmostEqual(metrics.ndcg_at_k(["c", "a", "b"], rel, 3), dcg / idcg)

    def test_errors_at_the_top_cost_more(self):
        rel = {"a": 3, "b": 2, "c": 1, "d": 0}
        top_swap = metrics.ndcg_at_k(["b", "a", "c", "d"], rel, 4)
        bottom_swap = metrics.ndcg_at_k(["a", "b", "d", "c"], rel, 4)
        self.assertLess(top_swap, bottom_swap)

    def test_unranked_relevant_and_unknown_items_are_penalized(self):
        rel = {"a": 3, "b": 2}
        self.assertLess(metrics.ndcg_at_k(["a"], rel, 2), 1.0)
        self.assertLess(metrics.ndcg_at_k(["x", "a", "b"], rel, 3), 1.0)

    def test_cutoff(self):
        rel = {"a": 3, "b": 2, "c": 1}
        self.assertAlmostEqual(metrics.ndcg_at_k(["a", "b", "x"], rel, 2), 1.0)


class Stability(unittest.TestCase):
    def test_kendall(self):
        self.assertEqual(metrics.kendall_tau(["a", "b", "c"], ["a", "b", "c"]), 1.0)
        self.assertEqual(metrics.kendall_tau(["a", "b", "c"], ["c", "b", "a"]), -1.0)
        self.assertEqual(metrics.stability_index([["a", "b"], ["a", "b"], ["b", "a"]]), (1 - 1 - 1) / 3)
        self.assertIsNone(metrics.stability_index([["a", "b"]]))


class Compliance(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads(SAMPLE.read_text(encoding="utf-8"))

    def failed(self, agent_input):
        return {c["check"] for c in metrics.compliance(agent_input, DATASET) if not c["ok"]}

    def task(self, doc, tid):
        return next(t for t in doc["tasks"] if t["id"] == tid)

    def test_sample_is_fully_compliant(self):
        self.assertEqual(self.failed(self.sample), set())

    def test_recording_the_users_not_critical_answer_is_allowed(self):
        # live run 2026-11-08: agent kept the user's words for GOLD-15/16 in not_critical_reason
        doc = copy.deepcopy(self.sample)
        self.task(doc, "GOLD-15")["not_critical_reason"] = "Не инцидент: есть обходной путь"
        self.assertEqual(self.failed(doc), set())

    def test_violations_are_detected(self):
        cases = {
            "evidence flags copied verbatim from the tool": lambda d: self.task(d, "GOLD-2").update(evidence_found_in_text=True),
            "no Confidence override attempted": lambda d: self.task(d, "GOLD-9").update(confidence=1.0),
            "architectural changes flagged for the ADR check": lambda d: self.task(d, "GOLD-23").pop("architectural"),
            "adr_refs copied verbatim from the tool": lambda d: self.task(d, "GOLD-23")["adr_refs"][0].update(status="accepted"),
            "adr_by_topic only cites existing accepted ADRs": lambda d: self.task(d, "GOLD-8").update(adr_by_topic={"id": "0099", "status": "accepted"}),
            "user triage answers applied": lambda d: self.task(d, "GOLD-19").pop("critical"),
            "utilization measured live (in_progress from tracker, capacity from user)": lambda d: d.update(team={"rho": 0.5}),
            "user 3-point estimates passed": lambda d: self.task(d, "GOLD-8").pop("estimate3"),
            "every backlog task passed exactly once": lambda d: d["tasks"].pop(),
            "triage signals copied verbatim from the tool": lambda d: self.task(d, "GOLD-3")["triage"].update(cvss_score=None),
            "as_of is the dataset date": lambda d: d.update(as_of="2026-12-31"),
            "no auto-critical item dismissed without a user answer": lambda d: self.task(d, "GOLD-3").update(not_critical_reason="meh"),
        }
        for check, mutate in cases.items():
            doc = copy.deepcopy(self.sample)
            mutate(doc)
            self.assertIn(check, self.failed(doc), check)


class Rankable(unittest.TestCase):
    def test_excludes_critical_unestimated_and_undecomposed(self):
        r = metrics.rankable_tasks(DATASET, synthetic_gold())
        self.assertFalse(r & CRITICAL)
        self.assertNotIn("GOLD-8", r)   # spread 1.75 -> decomposition
        self.assertNotIn("GOLD-12", r)  # no estimate
        self.assertIn("GOLD-7", r)      # spread 0.77 -> rankable
        self.assertEqual(len(r), 24 - 4 - 2)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.gold = self.tmp / "gold.json"
        self.gold.write_text(json.dumps(synthetic_gold()), encoding="utf-8")

    def run_eval(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return run_eval.main(["run_eval.py", "--gold", str(self.gold), "--out", str(self.tmp / "runs"), *extra])

    def test_replay_passes_gates(self):
        self.assertEqual(self.run_eval("--agent", f"replay:{SAMPLE},{SAMPLE}"), 0)
        results = json.loads(next((self.tmp / "runs").glob("*/results.json")).read_text())
        self.assertGreaterEqual(results["summary"]["mean_ndcg"], 0.9)
        self.assertEqual(results["summary"]["asi"], 1.0)  # identical runs
        self.assertEqual(results["runs"][0]["triage"]["recall"], 1.0)

    def test_missed_critical_fails_gate(self):
        doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
        t19 = next(t for t in doc["tasks"] if t["id"] == "GOLD-19")
        t19.pop("critical"), t19.pop("critical_reason")
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(self.run_eval("--agent", f"replay:{bad}"), 1)

    def test_low_ndcg_fails_gate(self):
        doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
        for t in doc["tasks"]:  # invert the agent's urgency judgments
            if "urgency" in t:
                t["urgency"] = 6 - t["urgency"]
        bad = self.tmp / "inverted.json"
        bad.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(self.run_eval("--agent", f"replay:{bad}"), 1)

    def test_calculator_rejection_is_reported_not_crashed(self):
        bad = self.tmp / "broken.json"
        bad.write_text(json.dumps({"tasks": []}), encoding="utf-8")
        self.assertEqual(self.run_eval("--agent", f"replay:{bad}"), 1)

    def test_compliance_only_needs_no_gold(self):
        self.gold.unlink()
        self.assertEqual(self.run_eval("--agent", f"replay:{SAMPLE}", "--compliance-only"), 0)
        results = json.loads(next((self.tmp / "runs").glob("*/results.json")).read_text())
        self.assertNotIn("mean NDCG@10 >= 0.9", results["summary"]["gates"])
        self.assertEqual(results["runs"][0]["triage"]["recall"], 1.0)  # GOLD-3/4/5 auto + GOLD-19 by answer

    def test_gold_for_other_dataset_version_is_refused(self):
        g = synthetic_gold()
        g["dataset_version"] = "0.0.1"
        self.gold.write_text(json.dumps(g), encoding="utf-8")
        self.assertEqual(self.run_eval("--agent", f"replay:{SAMPLE}"), 2)

    def test_prompt_contains_all_user_answers(self):
        prompt = run_eval.build_prompt(DATASET)
        for tid in list(DATASET["user_context"]["estimates"]) + list(DATASET["user_context"]["triage_answers"]):
            self.assertIn(tid, prompt)
        self.assertIn("prio-input.json", prompt)
        self.assertIn(DATASET["as_of"], prompt)


class LiveRunnerPreflight(unittest.TestCase):
    def test_workspace_is_isolated_and_complete(self):
        ws = run_eval.prepare_workspace("http://localhost:8089")
        try:
            skill = ws / ".claude/skills/backlog-prioritization-engine"
            self.assertTrue((skill / "SKILL.md").exists())
            self.assertTrue((skill / "scripts/priority.py").exists())
            self.assertFalse((skill / "scripts/example-input.json").exists())  # no worked answers leak in
            self.assertEqual(sorted(p.name for p in (ws / "docs/adr").iterdir()), ["0015-use-spring-ai.md"])
            self.assertFalse((ws / "dataset.json").exists())                    # expected outcomes stay hidden
            env = json.loads((ws / "mcp.json").read_text())["mcpServers"]["backlog"]["env"]
            self.assertEqual(env["YOUTRACK_BASE_URL"], "http://localhost:8089")
            self.assertEqual(env["ADR_DIR"], str(ws / "docs/adr"))
        finally:
            import shutil
            shutil.rmtree(ws)

    def test_allow_list_covers_skill_and_calculator(self):
        tools = run_eval.agent_tools(pathlib.Path("/tmp/ws"))
        self.assertIn("Skill", tools)
        self.assertIn(f"Bash(python3 -I {run_eval.CALCULATOR} *)", tools)
        self.assertIn(f"Bash(python3 -I /tmp/ws/{run_eval.CALCULATOR} *)", tools)

    def test_denied_skill_or_calculator_fails_the_run(self):
        transcript = {"permission_denials": [
            {"tool_name": "Skill", "tool_input": {"skill": "backlog-prioritization-engine"}},
            {"tool_name": "Bash", "tool_input": {"command": "python3 -I x/priority.py prio-input.json; echo $?"}}]}
        self.assertEqual([c["ok"] for c in run_eval.denial_checks(transcript)], [False, False])
        self.assertEqual([c["ok"] for c in run_eval.denial_checks({})], [True, True])

    def test_edit_is_allowed_and_skill_tampering_is_detected(self):
        self.assertIn("Edit", run_eval.agent_tools(pathlib.Path("/tmp/ws")))
        ws = run_eval.prepare_workspace("http://localhost:8089")
        try:
            before = run_eval.skill_fingerprint(ws)
            self.assertTrue(run_eval.tamper_check(before, ws)["ok"])
            calc = ws / run_eval.CALCULATOR
            calc.write_text(calc.read_text() + "\n# tampered\n")
            self.assertFalse(run_eval.tamper_check(before, ws)["ok"])
        finally:
            import shutil
            shutil.rmtree(ws)

    def test_tracker_defaults_to_wiremock_and_can_target_the_sandbox(self):
        base = {"--wiremock-url": "http://localhost:8089"}
        self.assertEqual(run_eval.tracker(base), ("http://localhost:8089", "golden-token"))
        sandbox = {**base, "--youtrack-url": "http://127.0.0.1:8088", "--youtrack-token": "perm-x"}
        self.assertEqual(run_eval.tracker(sandbox), ("http://127.0.0.1:8088", "perm-x"))
        import os
        saved = os.environ.pop("YOUTRACK_SANDBOX_TOKEN", None)
        try:
            with self.assertRaises(run_eval.EvalError):
                run_eval.tracker({**base, "--youtrack-url": "http://127.0.0.1:8088"})
        finally:
            if saved is not None:
                os.environ["YOUTRACK_SANDBOX_TOKEN"] = saved
        ws = run_eval.prepare_workspace(*run_eval.tracker_args(sandbox))
        try:
            env = json.loads((ws / "mcp.json").read_text())["mcpServers"]["backlog"]["env"]
            self.assertEqual((env["YOUTRACK_BASE_URL"], env["YOUTRACK_TOKEN"]), ("http://127.0.0.1:8088", "perm-x"))
        finally:
            import shutil
            shutil.rmtree(ws)

    def test_unreachable_wiremock_is_a_clear_error(self):
        self.assertFalse(run_eval.wiremock_healthy("http://localhost:1"))


class Consensus(unittest.TestCase):
    def sheet(self, overrides=None):
        rows = {}
        for i, t in enumerate(DATASET["tasks"]):
            if t["id"] in CRITICAL:
                rows[t["id"]] = {"critical": "yes"}
            else:
                rows[t["id"]] = {"critical": "no", "relevance": i % 4, "urgency": 1 + i % 5,
                                 **{f"impact_{m}": i % 6 for m in agreement.IMPACTS}}
        for tid, rec in (overrides or {}).items():
            rows[tid] = {**rows[tid], **rec}
        return rows

    def test_agreeing_experts_produce_gold(self):
        gold, problems = consensus.build({"a": self.sheet(), "b": self.sheet({"GOLD-1": {"relevance": 1}})},
                                         {}, 0.6, DATASET["version"])
        self.assertEqual(problems, [])
        self.assertTrue(gold["tasks"]["GOLD-3"]["critical"])
        self.assertEqual(gold["tasks"]["GOLD-1"]["relevance"], 0.5)  # mean of 0 and 1

    def test_unresolved_disagreement_blocks_until_adjudicated(self):
        sheets = {"a": self.sheet(), "b": self.sheet({"GOLD-2": {"relevance": 3}, "GOLD-6": {"critical": "yes"}})}
        _, problems = consensus.build(sheets, {}, 0.0, DATASET["version"])
        self.assertTrue(any("GOLD-2" in p for p in problems))
        self.assertTrue(any("GOLD-6: critical differs" in p for p in problems))
        gold, problems = consensus.build(
            sheets, {("GOLD-2", "relevance"): "2", ("GOLD-6", "critical"): "no"}, 0.0, DATASET["version"])
        self.assertEqual(problems, [])
        self.assertEqual(gold["tasks"]["GOLD-2"]["relevance"], 2.0)
        self.assertFalse(gold["tasks"]["GOLD-6"]["critical"])

    def test_proxy_mode_auto_resolves_and_marks_source(self):
        sheets = {"a": self.sheet(), "b": self.sheet({"GOLD-2": {"relevance": 3}, "GOLD-6": {"critical": "yes"}})}
        gold, problems = consensus.build(sheets, {}, 0.0, DATASET["version"], proxy=True)
        self.assertEqual(problems, [])
        self.assertEqual(gold["source"], "model-proxy")
        self.assertTrue(gold["tasks"]["GOLD-6"]["critical"])          # any "yes" wins
        self.assertTrue(any("GOLD-2" in r for r in gold["auto_resolved"]))
        expert_gold, _ = consensus.build({"a": self.sheet(), "b": self.sheet()}, {}, 0.0, DATASET["version"])
        self.assertEqual(expert_gold["source"], "experts")

    def test_low_kappa_is_refused(self):
        b = self.sheet({t["id"]: {"relevance": 3 - (i % 4)} for i, t in enumerate(DATASET["tasks"]) if t["id"] not in CRITICAL})
        _, problems = consensus.build({"a": self.sheet(), "b": b}, {}, 0.6, DATASET["version"])
        self.assertTrue(any("kappa" in p for p in problems))

    def test_cli_round_trip(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        paths = []
        for name in ("a", "b"):
            p = tmp / f"expert-{name}.csv"
            with p.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(build.CSV_COLUMNS)
                for tid, r in self.sheet().items():
                    w.writerow([tid, "", r["critical"], "x" if r["critical"] == "yes" else ""]
                               + [r.get(f"impact_{m}", "") for m in agreement.IMPACTS]
                               + [r.get("urgency", ""), r.get("relevance", ""), ""])
            paths.append(str(p))
        out = tmp / "gold.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(consensus.main(["consensus.py", *paths, "--out", str(out)]), 0)
        self.assertEqual(json.loads(out.read_text())["experts"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
