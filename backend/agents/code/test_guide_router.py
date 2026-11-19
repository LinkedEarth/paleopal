"""Tests for guide_router. Run from backend/: python agents/code/test_guide_router.py"""

import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("guide_router", Path(__file__).with_name("guide_router.py"))
guide_router = importlib.util.module_from_spec(_spec)
sys.modules["guide_router"] = guide_router
_spec.loader.exec_module(guide_router)

GUIDES = guide_router.load_guides()


def model(reply):
    calls = []

    def call(system, user):
        calls.append((system, user))
        return reply
    call.calls = calls
    return call


class LoadTests(unittest.TestCase):
    def test_both_guides_load(self):
        self.assertEqual(set(GUIDES), {"spectral_analysis", "visualization"})

    def test_every_plot_entry_names_its_types_and_use(self):
        for step in GUIDES["visualization"]["steps"]:
            self.assertTrue(step["for_types"], step["id"])
            self.assertIn(step["use"], ("default", "on_request"), step["id"])

    def test_one_default_plot_per_type(self):
        defaults = {}
        for step in GUIDES["visualization"]["steps"]:
            if step["use"] == "default":
                for t in step["for_types"]:
                    self.assertNotIn(t, defaults, f"{t} has two defaults")
                    defaults[t] = step["id"]
        self.assertEqual(defaults["MultipleSeries"], "stackplot")
        self.assertEqual(defaults["MultivariateDecomp"], "pca_dashboard")

    def test_phaseran_only_for_coherence(self):
        phaseran = GUIDES["visualization"]["statements"]["significance_lines"]["phaseran"]
        self.assertEqual(phaseran["only_for"], ["coherence_dashboard"])


class PromptTests(unittest.TestCase):
    def test_prompt_lists_both_guides_and_entries(self):
        prompt = guide_router.build_system_prompt(GUIDES)
        self.assertIn("- spectral_analysis:", prompt)
        self.assertIn("- visualization:", prompt)
        self.assertIn("stackplot (for MultipleSeries, MultipleGeoSeries)", prompt)
        self.assertIn("detrend", prompt)

    def test_request_is_the_user_message(self):
        call = model('{"guides": ["visualization"]}')
        guide_router.route_request("plot lr04", GUIDES, call)
        self.assertEqual(call.calls[0][1], "plot lr04")


class RouteTests(unittest.TestCase):
    def test_one_guide(self):
        route = guide_router.route_request("plot lr04", GUIDES, model('{"guides": ["visualization"]}'))
        self.assertEqual(route.guides, ["visualization"])
        self.assertFalse(route.failed)

    def test_both_in_order(self):
        route = guide_router.route_request(
            "plot lr04 then run spectral analysis", GUIDES,
            model('Sure: {"guides": ["visualization", "spectral_analysis"]}'))
        self.assertEqual(route.guides, ["visualization", "spectral_analysis"])

    def test_none(self):
        route = guide_router.route_request("read my csv", GUIDES, model('{"guides": []}'))
        self.assertEqual(route.guides, [])
        self.assertFalse(route.failed)

    def test_unknown_guide_dropped(self):
        route = guide_router.route_request("x", GUIDES, model('{"guides": ["wavelet", "visualization"]}'))
        self.assertEqual(route.guides, ["visualization"])
        self.assertIn("wavelet", route.problems[0])

    def test_duplicates_dropped(self):
        route = guide_router.route_request("x", GUIDES, model('{"guides": ["visualization", "visualization"]}'))
        self.assertEqual(route.guides, ["visualization"])

    def test_unreadable_reply_fails(self):
        for reply in ("no json here", '{"guides": "visualization"}', "[1, 2]"):
            route = guide_router.route_request("x", GUIDES, model(reply))
            self.assertTrue(route.failed, reply)
            self.assertEqual(route.guides, [])


class ObjectsTests(unittest.TestCase):
    def test_objects_reach_the_prompt(self):
        call = model('{"guides": ["visualization"]}')
        guide_router.route_request("plot the detrended series", GUIDES, call,
                                   {"lr04": "Series", "lr04_detrended": "Series", "psd": "PSD"})
        self.assertIn("- lr04_detrended (Series)", call.calls[0][0])
        self.assertIn("plot the detrended series\" is a plot of an existing", call.calls[0][0])

    def test_no_objects(self):
        self.assertIn("(none)", guide_router.build_system_prompt(GUIDES))


if __name__ == "__main__":
    unittest.main()
