#!/usr/bin/env python3
"""Unit tests for verification.py (standard library only).

Run from the backend directory:

  cd backend
  python agents/code/test_verification.py

verification.py is loaded straight from its file so that importing it does
not pull in the code agent package (and its LangGraph dependencies).
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

_HERE = pathlib.Path(__file__).parent


def _load_verification():
    pkg = types.ModuleType("_verification_pkg")
    pkg.__path__ = [str(_HERE)]
    sys.modules["_verification_pkg"] = pkg
    for name in ("api_validation", "verification"):
        spec = importlib.util.spec_from_file_location(
            f"_verification_pkg.{name}", _HERE / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    return sys.modules["_verification_pkg.verification"]


v = _load_verification()

# A complete, correct peak-detection pipeline.
GOOD = (
    "psd = ts.standardize().spectral(method='lomb_scargle').signif_test()\n"
    "psd.plot({kwargs})\n"
)


def _finding(findings, rule):
    return next(f for f in findings if f.rule == rule)


class PlotInLoglogTests(unittest.TestCase):
    task = {"objective": "peak_detection", "expects_plot": True}

    def test_default_plot_passes(self):
        findings = v.run_checks(GOOD.format(kwargs=""), self.task)
        self.assertEqual(_finding(findings, "plot_in_loglog").status, "ok")

    def test_explicit_true_passes(self):
        findings = v.run_checks(GOOD.format(kwargs="in_loglog=True"), self.task)
        self.assertEqual(_finding(findings, "plot_in_loglog").status, "ok")

    def test_explicit_false_is_flagged(self):
        findings = v.run_checks(GOOD.format(kwargs="in_loglog=False"), self.task)
        self.assertEqual(_finding(findings, "plot_in_loglog").status, "violated")


class GateTests(unittest.TestCase):
    def test_clean_code_needs_no_repair(self):
        findings = v.run_checks(GOOD.format(kwargs=""),
                                {"objective": "peak_detection", "expects_plot": True})
        self.assertFalse(v.gate(findings)["repair"])

    def test_every_severity_is_repaired(self):
        findings = [
            v.Finding("a", "prohibited", "violated"),
            v.Finding("b", "discouraged", "violated"),
            v.Finding("c", "advisory", "violated"),
            v.Finding("d", "prohibited", "ok"),
        ]
        result = v.gate(findings)
        self.assertTrue(result["repair"])
        self.assertEqual([f.rule for f in result["violations"]], ["a", "b", "c"])

    def test_user_override_is_not_repaired(self):
        findings = v.run_checks(GOOD.format(kwargs="in_loglog=False"),
                                {"objective": "peak_detection", "expects_plot": True})
        result = v.gate(findings, user_overrides={"plot_in_loglog"})
        self.assertFalse(result["repair"])
        self.assertEqual([f.rule for f in result["overridden"]], ["plot_in_loglog"])


if __name__ == "__main__":
    unittest.main()
