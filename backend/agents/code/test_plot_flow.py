#!/usr/bin/env python3
"""Unit tests for plot_flow.py, with stand-ins for the model and the search.

Run from the backend directory:  python agents/code/test_plot_flow.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import sys
import types
import unittest

_HERE = pathlib.Path(__file__).parent
_pkg = types.ModuleType("_plot_pkg")
_pkg.__path__ = [str(_HERE)]
sys.modules["_plot_pkg"] = _pkg


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_plot_pkg.{name}", _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    setattr(_pkg, name, module)
    spec.loader.exec_module(module)
    return module


for _name in ("api_validation", "verification", "workflow_detector", "request_interpreter",
              "step_snippets", "workflow_writer", "chat_session", "planning_flow", "guide_router"):
    _load(_name)
plot_flow = _load("plot_flow")
GUIDE = _pkg.guide_router.load_guides()["visualization"]

LOAD = "import pyleoclim as pyleo\nlr04 = pyleo.utils.load_dataset('LR04')"


def history(*cells):
    return [{"role": "assistant", "generated_content": c} for c in cells]


def model(choice, code_for=None):
    """Answers the plot interpreter with `choice`, and writes `code_for(step_id, start)` as the code."""
    calls = []

    def call(system, user):
        calls.append((system, user))
        if system.startswith("You read one plotting request"):
            return json.dumps(choice)
        step = [l.split("## Step: ")[1] for l in user.splitlines() if l.startswith("## Step: ")][0]
        start = system.split("Start from `")[1].split("`")[0]
        code = code_for(step, start) if code_for else f"fig, ax = {start}.plot()"
        return json.dumps({"steps": [{"id": step, "explanation": "I plotted it.", "code": code}]})
    call.calls = calls
    return call


async def no_search(query, top_k=5):
    return []


def run(request, cells, choice, code_for=None, kernel=None):
    call = model(choice, code_for)
    result = asyncio.run(plot_flow.run(request, history(*cells), GUIDE, call, [no_search], kernel=kernel))
    return result, call


class ObjectTests(unittest.TestCase):
    def test_types_follow_the_chain(self):
        objects = plot_flow.objects_from_cells([
            LOAD,
            "d = lr04.detrend().standardize()\npsd = d.spectral(method='mtm')\n"
            "sig = psd.signif_test(method='CN', qs=[0.9, 0.99])\nscal = d.wavelet()\n"
            "ms = pyleo.MultipleSeries([lr04, d])\npsds = ms.spectral()\npca = ms.pca()\nfig, ax = lr04.plot()"])
        self.assertEqual({n: o.type for n, o in objects.items()},
                         {"lr04": "Series", "d": "Series", "psd": "PSD", "sig": "PSD", "scal": "Scalogram",
                          "ms": "MultipleSeries", "psds": "MultiplePSD", "pca": "MultivariateDecomp"})
        self.assertIsNone(objects["psd"].significance)
        self.assertEqual(objects["sig"].significance, {"method": "CN", "qs": [0.9, 0.99]})

    def test_default_significance(self):
        objects = plot_flow.objects_from_cells([LOAD, "sig = lr04.spectral().signif_test()"])
        self.assertEqual(objects["sig"].significance, {"method": "ar1sim", "qs": [0.95]})

    def test_reassigned_to_something_unknown_is_dropped(self):
        objects = plot_flow.objects_from_cells([LOAD, "lr04 = 3"])
        self.assertNotIn("lr04", objects)

    def test_kernel_type_wins(self):
        found = plot_flow.plottable([LOAD], GUIDE, {"variables": {"lr04": "GeoSeries"}})
        self.assertEqual(found["lr04"].type, "GeoSeries")

    def test_only_the_kernel_is_not_enough(self):
        found = plot_flow.plottable([LOAD], GUIDE, {"variables": {"lr04": "Series", "other": "Series"}})
        self.assertEqual(set(found), {"lr04"})


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        self.series = plot_flow.PlotObject("lr04", "Series")
        self.ms = plot_flow.PlotObject("ms", "MultipleSeries")

    def test_defaults(self):
        self.assertEqual(plot_flow.choose_entry(self.series, None, GUIDE)[0]["id"], "plot_series")
        self.assertEqual(plot_flow.choose_entry(self.ms, None, GUIDE)[0]["id"], "stackplot")
        pca = plot_flow.PlotObject("pca", "MultivariateDecomp")
        self.assertEqual(plot_flow.choose_entry(pca, None, GUIDE)[0]["id"], "pca_dashboard")

    def test_asked_for_plot(self):
        self.assertEqual(plot_flow.choose_entry(self.ms, "overlay_series", GUIDE)[0]["id"], "overlay_series")

    def test_a_plot_for_another_type_is_explained(self):
        entry, message = plot_flow.choose_entry(self.series, "pca_screeplot", GUIDE)
        self.assertIsNone(entry)
        self.assertIn("`lr04` is a Series", message)

    def test_prompt_lists_only_plots_for_present_types(self):
        prompt = plot_flow.build_prompt({"lr04": self.series}, GUIDE)
        self.assertIn("- lr04 (Series)", prompt)
        self.assertIn("summary_plot", prompt)
        self.assertNotIn("pca_screeplot", prompt)


class StatementTests(unittest.TestCase):
    def entry(self, step_id):
        return next(s for s in GUIDE["steps"] if s["id"] == step_id)

    def test_scalogram_gets_the_cone_of_influence(self):
        sentences = plot_flow.statements_for(self.entry("plot_scalogram"),
                                             [plot_flow.PlotObject("scal", "Scalogram")], GUIDE)
        self.assertEqual(len(sentences), 1)
        self.assertIn("cone of influence", sentences[0])

    def test_significance_by_method_and_levels(self):
        sig = plot_flow.PlotObject("sig", "PSD", {"method": "ar1sim", "qs": [0.9, 0.95, 0.99]})
        sentences = plot_flow.statements_for(self.entry("plot_psd"), [sig], GUIDE)
        self.assertEqual(sentences, ["The significance lines show the 90%, 95% and 99% threshold of a test "
                                     "against an AR(1) null hypothesis."])

    def test_no_test_no_sentence(self):
        self.assertEqual(plot_flow.statements_for(self.entry("plot_psd"),
                                                  [plot_flow.PlotObject("psd", "PSD")], GUIDE), [])

    def test_phaseran_never_on_a_spectrum(self):
        sig = plot_flow.PlotObject("sig", "PSD", {"method": "phaseran", "qs": [0.95]})
        self.assertEqual(plot_flow.statements_for(self.entry("plot_psd"), [sig], GUIDE), [])
        coh = plot_flow.PlotObject("coh", "Coherence", {"method": "phaseran", "qs": [0.95]})
        sentences = plot_flow.statements_for(self.entry("coherence_dashboard"), [coh], GUIDE)
        self.assertTrue(any("phase-randomized" in s for s in sentences))

    def test_summary_plot_reads_its_arguments(self):
        objects = {"lr04": plot_flow.PlotObject("lr04", "Series"),
                   "sig": plot_flow.PlotObject("sig", "PSD", {"method": "ar1sim", "qs": [0.95]}),
                   "scal": plot_flow.PlotObject("scal", "Scalogram")}
        plotted = plot_flow.plotted_objects("fig, ax = lr04.summary_plot(psd=sig, scalogram=scal)",
                                            self.entry("summary_plot"), objects)
        self.assertEqual({o.name for o in plotted}, {"lr04", "sig", "scal"})


class FlowTests(unittest.TestCase):
    def test_plot_a_series(self):
        result, call = run("plot lr04", [LOAD], {"object": "lr04", "plot": None})
        code = [c for c in result["cells"] if c["kind"] == "code"]
        self.assertEqual(code[0]["text"], "# Written by PaleoPAL\nfig, ax = lr04.plot()")
        markdown = result["cells"][-2]["text"]
        self.assertTrue(markdown.startswith("### Plot the series"))
        self.assertIn("**PaleoPAL's guide to visualization:**", markdown)
        self.assertIn("labels the axes", markdown)
        self.assertIn("Parameters", markdown)
        self.assertEqual(result["checker_findings"], [])
        self.assertIn("Working with PaleoPAL", result["cells"][0]["text"])  # first PaleoPAL cells

    def test_plot_the_spectrum_with_its_test(self):
        cells = [LOAD, "psd = lr04.spectral()\npsd_sig = psd.signif_test(number=1000)"]
        result, _ = run("plot the significance test", cells, {"object": "psd_sig", "plot": None})
        markdown = next(c["text"] for c in result["cells"] if c.get("step") == "plot_psd" and c["kind"] == "markdown")
        parts = markdown.split("\n\n")
        self.assertEqual(parts[0], "### Plot the spectrum")
        self.assertEqual(parts[2], "The significance lines show the 95% threshold of a test against an "
                                   "AR(1) null hypothesis.")

    def test_several_objects_and_none_named_asks(self):
        cells = [LOAD, "psd = lr04.spectral()"]
        result, _ = run("make a plot", cells, {"object": None, "plot": None})
        self.assertTrue(result["needs_user_input"])
        self.assertIn("`lr04` (Series), `psd` (PSD)", result["cells"][0]["text"])

    def test_one_object_and_none_named_uses_it(self):
        result, _ = run("make a plot", [LOAD], {"object": None, "plot": None})
        self.assertFalse(result["needs_user_input"])

    def test_unknown_object_asks(self):
        result, _ = run("plot sst", [LOAD], {"object": "sst", "plot": None})
        self.assertIn("I couldn't find `sst`", result["cells"][0]["text"])

    def test_not_run_asks(self):
        result, _ = run("plot lr04", [LOAD], {"object": "lr04", "plot": None}, kernel={"variables": {}})
        self.assertIn("hasn't been run", result["cells"][0]["text"])

    def test_summary_plot_without_its_results_asks(self):
        result, _ = run("summary plot of lr04", [LOAD], {"object": "lr04", "plot": "summary_plot"})
        self.assertTrue(result["needs_user_input"])
        self.assertIn("needs a PSD and a Scalogram", result["cells"][0]["text"])

    def test_nothing_to_plot_is_not_covered(self):
        result, _ = run("plot it", ["x = 1"], {"object": None, "plot": None})
        self.assertIsNone(result)

    def test_dismantling_is_repaired(self):
        attempts = []

        def code_for(step, start):
            attempts.append(step)
            return ("import matplotlib.pyplot as plt\nplt.plot(lr04.time, lr04.value)" if len(attempts) == 1
                    else "fig, ax = lr04.plot()")
        result, _ = run("plot lr04", [LOAD], {"object": "lr04", "plot": None}, code_for)
        self.assertEqual(result["repairs"], 1)
        self.assertEqual(result["checker_findings"], [])


if __name__ == "__main__":
    unittest.main()
