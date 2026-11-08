"""Golden Dataset self-checks.  Run: python3 -I -m unittest discover -s evals/golden"""
import csv
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "skills/backlog-prioritization-engine/scripts"))
sys.path.insert(0, str(HERE))

import agreement  # noqa: E402
import build  # noqa: E402
import priority  # noqa: E402

DATASET = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))


class Kappa(unittest.TestCase):
    def test_textbook_unweighted(self):
        # 2x2 table [[25,10],[15,50]]: po=0.75, pe=0.53 -> 0.4681
        a = ["y"] * 35 + ["n"] * 65
        b = ["y"] * 25 + ["n"] * 10 + ["y"] * 15 + ["n"] * 50
        self.assertAlmostEqual(agreement.cohen_kappa(a, b, ["y", "n"]), 0.22 / 0.47, places=4)

    def test_quadratic_perfect_and_reversed(self):
        cats = [0, 1, 2, 3]
        self.assertAlmostEqual(agreement.cohen_kappa(cats, cats, cats, "quadratic"), 1.0)
        self.assertAlmostEqual(agreement.cohen_kappa(cats, cats[::-1], cats, "quadratic"), -1.0)

    def test_quadratic_penalizes_distance_less_than_nominal(self):
        a, b = [0, 1, 2, 3, 3], [0, 1, 2, 2, 3]
        self.assertGreater(agreement.cohen_kappa(a, b, [0, 1, 2, 3], "quadratic"),
                           agreement.cohen_kappa(a, b, [0, 1, 2, 3]))


class Sheets(unittest.TestCase):
    def write(self, rows):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8-sig", newline="")
        w = csv.writer(f, delimiter=";")
        w.writerow(build.CSV_COLUMNS)
        w.writerows(rows)
        f.close()
        return pathlib.Path(f.name)

    def full_row(self, tid, crit="no", **over):
        vals = {"critical": crit, "critical_reason": "x" if crit == "yes" else "",
                **{f"impact_{m}": "1" for m in agreement.IMPACTS}, "urgency": "2", "relevance": "1", "comment": ""}
        if crit == "yes":
            vals.update({k: "" for k in vals if k.startswith("impact_") or k in ("urgency", "relevance")})
        vals.update(over)
        return [tid, "s"] + [vals[c] for c in build.CSV_COLUMNS[2:]]

    def test_valid_sheet(self):
        ids = agreement.load_ids()
        path = self.write([self.full_row(t, "yes" if t == "GOLD-3" else "no") for t in ids])
        rows, errors = agreement.read_sheet(path, ids)
        self.assertEqual(errors, [])
        self.assertEqual(rows["GOLD-3"], {"critical": "yes"})

    def test_reports_errors(self):
        ids = agreement.load_ids()
        bad = [self.full_row("GOLD-1", urgency="7"), self.full_row("GOLD-2", "maybe"),
               self.full_row("GOLD-4", "yes", critical_reason=""), self.full_row("GOLD-5", relevance="")]
        _, errors = agreement.read_sheet(self.write(bad), ids)
        text = "\n".join(errors)
        for needle in ("urgency=7 outside 1..5", "critical must be yes/no", "critical_reason is required",
                       "relevance is empty", "missing tasks"):
            self.assertIn(needle, text)

    def test_report_flags_disagreements(self):
        ids = agreement.load_ids()
        a = {t: {"critical": "no", "urgency": 2, "relevance": 1, **{f"impact_{m}": 1 for m in agreement.IMPACTS}} for t in ids}
        b = json.loads(json.dumps(a))
        b["GOLD-1"]["relevance"] = 3
        b["GOLD-3"] = {"critical": "yes"}
        out = agreement.report({"a": a, "b": b})
        self.assertIn("GOLD-1: relevance a=1, b=3", out)
        self.assertIn("GOLD-3: critical differs", out)


class DatasetIntent(unittest.TestCase):
    """The scenario each task was written for must actually be triggered by the calculator."""

    def test_triage_outcomes_match_intent(self):
        tasks = []
        for t in DATASET["tasks"]:
            tasks.append({"id": t["id"], "evidence_found_in_text": t["expected"]["evidence_found_in_text"],
                          "story_points": t["story_points"], "impacts": {"scaling": 1}, "urgency": 1,
                          "triage": {"issue_type": t["type"], "priority": t["priority"], "labels": t["tags"],
                                     "components": t["subsystem"], "due_date": t["due_date"],
                                     "cvss_score": t["expected"]["cvss_score"]}})
        r = priority.run({"as_of": DATASET["as_of"], "team": {"rho": 0.5}, "tasks": tasks})
        critical = {s["id"] for s in r["critical"]}
        candidates = {c["id"] for c in r["triage_candidates"]}
        for t in DATASET["tasks"]:
            want = t["expected"]["triage"]
            got = "auto_critical" if t["id"] in critical else "candidate" if t["id"] in candidates else "none"
            self.assertEqual(got, want, f"{t['id']}: {t['scenario']}")

    def test_uncertainty_scenarios(self):
        est = DATASET["user_context"]["estimates"]
        spread = lambda e: (e["pess"] - e["opt"]) / e["real"]
        self.assertLessEqual(spread(est["GOLD-7"]), 1.0)
        self.assertGreater(spread(est["GOLD-8"]), 1.0)

    def test_adr_fixture_matches_intent(self):
        present = {p.name for p in (HERE / "adr").glob("*.md")}
        self.assertEqual(present, set(DATASET["user_context"]["adr_present"]))

    def test_artifacts_are_up_to_date(self):
        self.assertEqual(build.main(["build.py", "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
