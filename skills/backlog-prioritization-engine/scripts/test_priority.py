"""Rule tests for priority.py.  Run: python3 -I -m unittest discover -s skills/backlog-prioritization-engine/scripts"""
import json
import pathlib
import unittest

import priority as p

HERE = pathlib.Path(__file__).parent


def task(**kw):
    base = {"id": "T-1", "evidence_found_in_text": True, "story_points": 5,
            "impacts": {"scaling": 5}, "urgency": 3}
    base.update(kw)
    return base


def run(tasks, team=None):
    return p.run({"team": team or {"rho": 0.5}, "tasks": tasks})


class QueuePenalty(unittest.TestCase):
    def test_thresholds_are_strictly_greater(self):
        self.assertEqual(p.queue_penalty(0.85), 1.0)
        self.assertEqual(p.queue_penalty(0.86), 1.5)
        self.assertEqual(p.queue_penalty(0.95), 1.5)
        self.assertEqual(p.queue_penalty(0.951), 3.0)

    def test_rho_from_wip_and_capacity(self):
        r = run([task()], {"in_progress": 10, "capacity": 10})
        self.assertEqual(r["queue"]["penalty"], 3.0)

    def test_penalty_cannot_be_skipped(self):
        with self.assertRaises(p.InputError):
            p.run({"tasks": [task()]})


class EvidenceRules(unittest.TestCase):
    def test_no_evidence_caps_impact_and_halves_confidence(self):
        s = run([task(evidence_found_in_text=False)])["ranked"][0]
        self.assertEqual(s["confidence"], 0.5)
        self.assertAlmostEqual(s["value"], 0.30 * 3 / 5 * 0.5)

    def test_confidence_cannot_be_raised_by_input(self):
        s = run([task(evidence_found_in_text=False, confidence=1.0)])["ranked"][0]
        self.assertEqual(s["confidence"], 0.5)

    def test_architectural_change_without_adr_discounts_even_with_flag(self):
        s = run([task(architectural=True)])["ranked"][0]
        self.assertEqual(s["confidence"], 0.5)

    def test_architectural_change_with_accepted_adr_keeps_confidence(self):
        ref = {"id": "0015", "title": "x", "status": "accepted", "superseded_by": None}
        self.assertEqual(run([task(architectural=True, adr_refs=[ref])])["ranked"][0]["confidence"], 1.0)

    def test_missing_superseded_or_proposed_adr_does_not_count(self):
        for ref in ({"id": "0031", "status": "missing"}, {"id": "0003", "status": "superseded", "superseded_by": "0007"},
                    {"id": "0022", "status": "proposed"}, {"id": "0015", "status": "unverified"}):
            s = run([task(architectural=True, adr_refs=[ref])])["ranked"][0]
            self.assertEqual(s["confidence"], 0.5, ref)
        notes = run([task(architectural=True, adr_refs=[{"id": "0003", "status": "superseded", "superseded_by": "0007"}])])
        self.assertIn("superseded by 0007", " ".join(notes["ranked"][0]["notes"]))

    def test_adr_found_by_topic_counts_and_asks_for_link(self):
        s = run([task(architectural=True, adr_by_topic={"id": "0015", "status": "accepted"})])["ranked"][0]
        self.assertEqual(s["confidence"], 1.0)
        self.assertIn("add the link", " ".join(s["notes"]))

    def test_old_flag_is_rejected(self):
        with self.assertRaises(p.InputError):
            run([task(architectural_without_adr=True)])

    def test_flag_is_mandatory(self):
        with self.assertRaises(p.InputError):
            run([task(evidence_found_in_text=None)])


class CostAndRanking(unittest.TestCase):
    def test_formula(self):
        s = run([task()])["ranked"][0]
        self.assertAlmostEqual(s["priority"], (0.30 * 5 / 5) * 3 / 5 ** 0.7)

    def test_uncertainty_over_1_requires_decomposition(self):
        r = run([task(estimate3={"opt": 1, "real": 2, "pess": 4})])
        self.assertEqual(r["refused"][0]["status"], "NEEDS_DECOMPOSITION")
        ok = run([task(estimate3={"opt": 2, "real": 3, "pess": 5})])["ranked"][0]
        self.assertAlmostEqual(ok["base_cost"], round((2 + 12 + 5) / 6, 2))

    def test_zero_value_is_never_ranked(self):
        r = run([task(impacts={}, urgency=5)])
        self.assertEqual(r["refused"][0]["status"], "ZERO_VALUE")
        self.assertEqual(r["ranked"], [])

    def test_missing_estimate(self):
        self.assertEqual(run([task(story_points=None)])["refused"][0]["status"], "NEEDS_ESTIMATE")

    def test_tie_lower_cost_wins(self):
        # identical priority at 2dp: P = V*U/C^0.7 ; pick costs giving same 2dp value
        a = task(id="A", story_points=5.0, impacts={"scaling": 5}, urgency=3)
        b = task(id="B", story_points=5.02, impacts={"scaling": 5}, urgency=3)
        r = run([b, a])
        self.assertEqual(r["ranked"][0]["priority_2dp"], r["ranked"][1]["priority_2dp"])
        self.assertEqual([s["id"] for s in r["ranked"]], ["A", "B"])

    def test_critical_skips_scoring(self):
        r = run([{"id": "C-1", "critical": True}])
        self.assertEqual(len(r["critical"]), 1)

    def test_worked_example_is_stable(self):
        r = p.run(json.loads((HERE / "example-input.json").read_text()))
        self.assertEqual([s["id"] for s in r["ranked"]], ["DEV-1", "DEV-6", "OPS-3", "OPS-4", "DEV-2"])
        self.assertEqual(r["triage_candidates"][0]["id"], "OPS-4")
        self.assertEqual(sorted(s["id"] for s in r["critical"]), ["DEV-3", "DEV-7"])
        self.assertEqual(r["queue"]["penalty"], 1.5)


class DocsExample(unittest.TestCase):
    """docs/example.md must stay reproducible: the saved report equals the calculator's output."""

    def test_saved_example_output_matches_calculator(self):
        import contextlib, io
        root = HERE.parents[2]
        example = root / "docs/example"
        if not example.exists():
            self.skipTest("installed skill without the repository docs")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(p.main(["priority.py", str(example / "prio-input.json")]), 0)
        self.assertEqual(out.getvalue(), (example / "ranking.md").read_text(encoding="utf-8"))


class ComplianceRisk(unittest.TestCase):
    def test_compliance_risk_counts_like_the_top_metric(self):
        plain = run([task(impacts={"tech_risk": 4, "reliability": 1})])["ranked"][0]
        comp = run([task(impacts={"tech_risk": 4, "reliability": 1},
                         triage={"labels": ["compliance", "pci"]})])["ranked"][0]
        self.assertAlmostEqual(plain["value"], (0.05 * 4 + 0.15 * 1) / 5)
        self.assertAlmostEqual(comp["value"], 0.30 * 4 / 5)
        self.assertIn("WSJF risk reduction", " ".join(comp["notes"]))

    def test_never_lowers_value_and_respects_evidence_rules(self):
        high = run([task(impacts={"scaling": 5, "tech_risk": 1}, triage={"labels": ["gdpr"]})])["ranked"][0]
        self.assertAlmostEqual(high["value"], (0.30 * 5 + 0.05 * 1) / 5)      # normal V is higher: kept
        capped = run([task(evidence_found_in_text=False, impacts={"tech_risk": 5},
                           triage={"components": ["Compliance"]})])["ranked"][0]
        self.assertAlmostEqual(capped["value"], 0.30 * 3 / 5 * 0.5)           # cap 3 and Confidence 0.5 still apply

    def test_non_compliance_security_work_is_unchanged(self):
        s = run([task(impacts={"tech_risk": 5}, triage={"labels": ["security"]})])["ranked"][0]
        self.assertAlmostEqual(s["value"], 0.05 * 5 / 5)


class ProjectConfig(unittest.TestCase):
    def tearDown(self):
        p.configure(None)

    def test_custom_metrics_replace_the_defaults(self):
        p.configure({"metrics": [{"id": "revenue", "weight": 0.6}, {"id": "risk", "weight": 0.4}],
                     "risk_metric": "risk"})
        s = run([task(impacts={"revenue": 5})])["ranked"][0]
        self.assertAlmostEqual(s["value"], 0.6 * 5 / 5)
        with self.assertRaises(p.InputError):
            run([task(impacts={"scaling": 5})])          # default metric no longer exists

    def test_weights_must_sum_to_one_and_ids_be_valid(self):
        for bad in ({"metrics": [{"id": "a", "weight": 0.5}]},
                    {"metrics": [{"id": "a b", "weight": 1.0}]},
                    {"metrics": [{"id": "a", "weight": 1.0}], "risk_metric": "b"},
                    {"weights": {}}):
            with self.assertRaises(p.InputError, msg=bad):
                p.configure(bad)

    def test_localized_triage_markers_are_added_to_defaults(self):
        p.configure({"triage": {"p1_priorities": ["Критичный"], "incident_types": ["Инцидент"],
                                "legal_markers": ["комплаенс"]}})
        r = p.run({"as_of": "2026-11-05", "team": {"rho": 0.5}, "tasks": [
            task(id="RU-1", triage={"priority": "Критичный", "issue_type": "Инцидент"}),
            task(id="RU-2", triage={"labels": ["Комплаенс"], "due_date": "2026-11-20"}),
            task(id="EN-1", triage={"priority": "Show-stopper", "issue_type": "Incident"})]})
        self.assertEqual(sorted(s["id"] for s in r["critical"]), ["EN-1", "RU-1", "RU-2"])

    def test_compliance_rule_follows_the_risk_metric_and_can_be_disabled(self):
        p.configure({"metrics": [{"id": "value", "weight": 0.9}, {"id": "risk", "weight": 0.1}], "risk_metric": None})
        s = run([task(impacts={"risk": 5}, triage={"labels": ["compliance"]})])["ranked"][0]
        self.assertAlmostEqual(s["value"], 0.1 * 5 / 5)

    def test_cli_config_flag(self):
        import io, contextlib, tempfile
        cfg = pathlib.Path(tempfile.mkdtemp()) / "c.json"
        cfg.write_text(json.dumps({"metrics": [{"id": "x", "weight": 1.0}]}))
        inp = cfg.with_name("in.json")
        inp.write_text(json.dumps({"team": {"rho": 0.5}, "tasks": [task(impacts={"x": 5})]}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(p.main(["priority.py", str(inp), "--config", str(cfg), "--json"]), 0)
        self.assertAlmostEqual(json.loads(out.getvalue())["ranked"][0]["value"], 1.0)


class Triage(unittest.TestCase):
    AS_OF = "2026-11-05"

    def run_one(self, triage, **kw):
        return p.run({"as_of": self.AS_OF, "team": {"rho": 0.5}, "tasks": [task(triage=triage, **kw)]})

    def test_cvss_9_is_auto_critical(self):
        r = self.run_one({"cvss_score": 9.8})
        self.assertIn("CVSS 9.8 >= 9 (auto)", r["critical"][0]["notes"][0])
        self.assertEqual(self.run_one({"cvss_score": 8.9})["critical"], [])

    def test_p1_incident_is_auto_critical_other_p1_is_candidate(self):
        self.assertEqual(len(self.run_one({"priority": "Highest", "issue_type": "Incident"})["critical"]), 1)
        r = self.run_one({"priority": "Show-stopper", "issue_type": "Bug"})
        self.assertEqual(r["critical"], [])
        self.assertEqual(r["triage_candidates"][0]["id"], "T-1")

    def test_legal_deadline_under_30_days(self):
        crit = self.run_one({"labels": ["compliance"], "due_date": "2026-11-30"})
        self.assertIn("legal deadline in 25 days", crit["critical"][0]["notes"][0])
        far = self.run_one({"labels": ["GDPR"], "due_date": "2027-01-30"})
        self.assertEqual(far["critical"], [])
        no_marker = self.run_one({"labels": ["ui"], "due_date": "2026-11-10"})
        self.assertEqual(no_marker["critical"], [])
        self.assertIn("mandatory legal deadline?", no_marker["triage_candidates"][0]["reasons"][0])

    def test_due_date_requires_as_of(self):
        with self.assertRaises(p.InputError):
            p.run({"team": {"rho": 0.5}, "tasks": [task(triage={"due_date": "2026-11-30"})]})

    def test_user_can_dismiss_auto_critical_with_reason(self):
        r = self.run_one({"cvss_score": 9.8}, not_critical_reason="CVE affects a module we do not ship")
        self.assertEqual(r["critical"], [])
        self.assertIn("dismissed by user", r["ranked"][0]["notes"][0])

    def test_user_confirmed_financial_risk(self):
        r = self.run_one({}, critical=True, critical_reason="financial risk 2M RUB")
        self.assertIn("financial risk 2M RUB (confirmed by user)", r["critical"][0]["notes"][0])


if __name__ == "__main__":
    unittest.main()
