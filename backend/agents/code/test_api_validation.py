"""Tests for api_validation against references/pyleoclim_api.json.

Run from backend/:  python agents/code/test_api_validation.py
"""

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("api_validation", Path(__file__).with_name("api_validation.py"))
api_validation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_validation)


def check(code):
    unknown, bad, _ = api_validation.validate(code)
    return unknown, bad


class ValidationTests(unittest.TestCase):
    def test_a_made_up_method_is_caught(self):
        unknown, _ = check("psd = ts.spectrum(method='mtm')")
        self.assertIn("did you mean spectral", unknown[0])

    def test_a_wrong_argument_is_caught(self):
        _, bad = check("psd.signif_test(null_model='ar1sim')")
        self.assertIn("null_model", bad[0])
        _, bad = check("ts.spectral(methd='mtm')")
        self.assertIn("did you mean method", bad[0])

    def test_settings_passed_on_to_utils_are_accepted(self):
        self.assertEqual(check("ts.bin(bin_size=4)"), ([], []))
        self.assertEqual(check("ts.interp(step=0.5)"), ([], []))

    def test_methods_the_old_file_lacked_are_known(self):
        self.assertEqual(check("fig, ax = pyleo.add_GTS(fig, ax)"), ([], []))
        self.assertEqual(check("psd.signif_test(number=1000, nproc=4)"), ([], []))

    def test_the_source_names_the_version(self):
        self.assertIn("Pyleoclim", api_validation.get_api()["source"])


if __name__ == "__main__":
    unittest.main()
