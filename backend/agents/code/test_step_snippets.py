#!/usr/bin/env python3
"""Unit tests for step_snippets.py, with stand-ins for the vector search.

Run from the backend directory:

  cd backend
  python agents/code/test_step_snippets.py

The module is loaded straight from its file so that importing it does not pull
in the code agent package (and its LangGraph dependencies).
"""
from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
import unittest

_spec = importlib.util.spec_from_file_location(
    "step_snippets", pathlib.Path(__file__).parent / "step_snippets.py")
s = importlib.util.module_from_spec(_spec)
sys.modules["step_snippets"] = s
_spec.loader.exec_module(s)

STANDARDIZE = {"id": "standardize", "core_api": "pyleoclim.core.series.Series.standardize"}
REGRID = {"id": "regrid", "core_api": ["pyleoclim.core.series.Series.interp",
                                       "pyleoclim.core.series.Series.bin"]}


class QueryTests(unittest.TestCase):
    def test_query_uses_the_class_and_method(self):
        self.assertEqual(s.step_queries(STANDARDIZE), ["Series.standardize"])

    def test_each_api_of_a_step_gets_its_own_query(self):
        self.assertEqual(s.step_queries(REGRID), ["Series.interp", "Series.bin"])


class FilterTests(unittest.TestCase):
    def test_call_is_kept(self):
        self.assertTrue(s.calls_step("x = ts.standardize()", STANDARDIZE))

    def test_call_in_a_chain_is_kept(self):
        self.assertTrue(s.calls_step("ts.detrend().standardize().spectral()", STANDARDIZE))

    def test_any_method_of_the_step_counts(self):
        self.assertTrue(s.calls_step("x = ts.bin(bin_size=5)", REGRID))

    def test_a_mention_without_a_call_is_dropped(self):
        self.assertFalse(s.calls_step("# remember to standardize later", STANDARDIZE))
        self.assertFalse(s.calls_step("from sklearn import standardize", STANDARDIZE))


class SearchTests(unittest.TestCase):
    def test_runs_every_search_with_the_step_query_and_filters(self):
        seen = []

        async def first(query, top_k):
            seen.append(query)
            return [{"code": "ts.standardize()", "similarity_score": 0.4},
                    {"code": "plt.plot(x, y)", "similarity_score": 0.9}]

        async def second(query, top_k):
            seen.append(query)
            return [{"code": "a.standardize()", "similarity_score": 0.7}]

        kept = asyncio.run(s.find_step_snippets(STANDARDIZE, [first, second]))
        self.assertEqual(seen, ["Series.standardize", "Series.standardize"])
        self.assertEqual([k["code"] for k in kept], ["a.standardize()", "ts.standardize()"])


if __name__ == "__main__":
    unittest.main()
