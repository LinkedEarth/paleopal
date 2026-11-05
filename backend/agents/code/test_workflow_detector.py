#!/usr/bin/env python3
"""Unit tests for workflow_detector.py, against the real spectral workflow file.

Run from the backend directory:

  cd backend
  python agents/code/test_workflow_detector.py

The module is loaded straight from its file so that importing it does not pull
in the code agent package (and its LangGraph dependencies).
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_PATH = pathlib.Path(__file__).parent / "workflow_detector.py"
_spec = importlib.util.spec_from_file_location("workflow_detector", _PATH)
d = importlib.util.module_from_spec(_spec)
sys.modules["workflow_detector"] = d
_spec.loader.exec_module(d)

WORKFLOW = d.load_workflow()
IMPORT = "import pyleoclim as pyleo"
LOAD = "lr04 = pyleo.utils.load_dataset('LR04')"


def statuses(state):
    return {s.id: s.status for s in state.steps}


class LoadedDataOnlyTests(unittest.TestCase):
    """The notebook from the first VS Code test: an import and a loaded series."""

    def setUp(self):
        self.state = d.detect([IMPORT, LOAD], WORKFLOW)
        self.steps = statuses(self.state)

    def test_recognises_import_and_series(self):
        self.assertIn("pyleoclim", self.state.imports)
        self.assertEqual(self.state.series, ["lr04"])
        self.assertEqual(self.state.target, "lr04")

    def test_chooses_whole_workflow(self):
        self.assertEqual(self.state.level, "whole_workflow")

    def test_required_and_recommended_steps_are_to_do(self):
        for step in ("detrend", "standardize", "spectral_estimate", "visualize"):
            self.assertEqual(self.steps[step], "to_do", step)

    def test_optional_steps_stay_optional(self):
        self.assertEqual(self.steps["remove_outliers"], "optional")
        self.assertEqual(self.steps["segment_on_gaps"], "optional")

    def test_regrid_is_not_decided_without_the_method(self):
        self.assertEqual(self.steps["regrid"], "depends_on_method")

    def test_unstated_objective_proposes_the_significance_test(self):
        self.assertEqual(self.steps["significance"], "propose")
        self.assertEqual(self.steps["beta_estimate"], "not_needed")

    def test_nothing_is_uncertain(self):
        self.assertEqual(self.state.uncertain, [])


class StepRecognitionTests(unittest.TestCase):
    def test_objective_makes_significance_required(self):
        state = d.detect([IMPORT, LOAD], WORKFLOW, objective="peak_detection")
        self.assertEqual(statuses(state)["significance"], "to_do")

    def test_scaling_objective_does_not_propose_significance(self):
        steps = statuses(d.detect([IMPORT, LOAD], WORKFLOW, objective="scaling_exponent"))
        self.assertEqual(steps["significance"], "not_needed")
        self.assertEqual(steps["beta_estimate"], "to_do")

    def test_steps_in_separate_cells_follow_the_variable(self):
        cells = [IMPORT, LOAD, "s = lr04.standardize()", "psd = s.spectral(method='wwz')"]
        state = d.detect(cells, WORKFLOW)
        steps = statuses(state)
        self.assertEqual(state.level, "next_step")
        self.assertEqual(steps["standardize"], "done")
        self.assertEqual(steps["spectral_estimate"], "done")
        self.assertEqual(steps["detrend"], "to_do")

    def test_chain_in_one_cell(self):
        cells = [IMPORT, LOAD, "psd = lr04.detrend().interp().standardize().spectral(method='mtm')"]
        steps = statuses(d.detect(cells, WORKFLOW))
        for step in ("detrend", "regrid", "standardize", "spectral_estimate"):
            self.assertEqual(steps[step], "done", step)

    def test_plotting_the_series_is_not_the_visualize_step(self):
        state = d.detect([IMPORT, LOAD, "lr04.plot()"], WORKFLOW)
        self.assertEqual(statuses(state)["visualize"], "to_do")
        self.assertEqual(state.level, "whole_workflow")

    def test_plotting_the_spectrum_is_the_visualize_step(self):
        cells = [IMPORT, LOAD, "psd = lr04.spectral()", "fig, ax = psd.plot()"]
        self.assertEqual(statuses(d.detect(cells, WORKFLOW))["visualize"], "done")

    def test_current_is_the_newest_variable_from_the_target(self):
        cells = [IMPORT, LOAD, "s = lr04.standardize()", "psd = s.spectral()", "fig, ax = psd.plot()"]
        self.assertEqual(d.detect(cells, WORKFLOW).current, "psd")
        self.assertEqual(d.detect([IMPORT, LOAD], WORKFLOW).current, "lr04")

    def test_notebook_magics_are_ignored(self):
        state = d.detect(["%matplotlib inline\n" + IMPORT, LOAD], WORKFLOW)
        self.assertEqual(state.uncertain, [])
        self.assertEqual(state.series, ["lr04"])


class SeveralSeriesTests(unittest.TestCase):
    cells = [IMPORT, "a = pyleo.utils.load_dataset('LR04')",
             "b = pyleo.utils.load_dataset('SOI')", "a_std = a.standardize()"]

    def test_no_target_with_two_series_is_unclear(self):
        self.assertEqual(d.detect(self.cells, WORKFLOW).level, "unclear")

    def test_a_step_on_one_series_does_not_count_for_the_other(self):
        self.assertEqual(statuses(d.detect(self.cells, WORKFLOW, target="a"))["standardize"], "done")
        self.assertEqual(statuses(d.detect(self.cells, WORKFLOW, target="b"))["standardize"], "to_do")


class CantTellTests(unittest.TestCase):
    def test_empty_notebook_needs_data(self):
        self.assertEqual(d.detect([], WORKFLOW).level, "needs_data")

    def test_import_alone_needs_data(self):
        self.assertEqual(d.detect([IMPORT], WORKFLOW).level, "needs_data")

    def test_broken_cell_is_flagged_not_guessed(self):
        state = d.detect([IMPORT, LOAD, "s = lr04.standardize("], WORKFLOW)
        self.assertEqual(len(state.uncertain), 1)
        self.assertIn("cell 3", state.uncertain[0])

    def test_unfamiliar_helper_is_flagged(self):
        state = d.detect([IMPORT, LOAD, "clean = my_helper(lr04)"], WORKFLOW)
        self.assertEqual(len(state.uncertain), 1)
        self.assertIn("my_helper", state.uncertain[0])

    def test_unknown_target_is_flagged(self):
        state = d.detect([IMPORT, LOAD], WORKFLOW, target="sst")
        self.assertEqual(state.target, None)
        self.assertEqual(len(state.uncertain), 1)


if __name__ == "__main__":
    unittest.main()
