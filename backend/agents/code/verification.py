"""
verification.py — PaleoPAL generation verification module.

Ported from the ~/paleopal-ab/ harness's checks.py, which was built directly
against spectral_full.yml: each check name maps onto a rule id in the YAML's
`rules` and `steps` sections (e.g. `preprocessing_order` <-> rule
`preprocessing_order_is_fixed`, `no_user_variable_rebinding` <-> rule
`prefer_chaining_over_rebinding`). Only the parts that are pure functions of
a code string (and, for disclosures, a response string) plus a small `task`
context dict are kept here — nothing in this module depends on the harness's
batch/file orchestration (run_ab.py, providers.py, compare_runs.py are not
ported; they have no live equivalent).

------------------------------------------------------------------------------
CONTRACT: the `task` dict
------------------------------------------------------------------------------
In the harness, `task` was loaded from a static tasks.yml fixture, one entry
per hand-authored test case. Live, nothing loads this for free — PaleoPAL's
plan step must assemble it before generation, from these sources:

    field                | live source
    ----------------------+--------------------------------------------------
    objective             | resolved objective (spectral_analysis.yml
                          | `objectives`), decided by the plan step —
                          | NOT guessed from the user's wording downstream
    data_evenly_spaced    | `inspection.even_spacing` check result against
                          | the LIVE KERNEL object. Not the corpus, not an
                          | assumption based on "paleoclimate data is
                          | usually unevenly spaced."
    expected_object       | the variable/object name the user's request
                          | actually refers to
    expects_plot          | whether the user's request calls for a figure
    must_mention          | disclosure obligations applicable to the
                          | resolved objective — i.e. rules in
                          | spectral_analysis.yml with `kind: disclosure`
                          | whose `applies_to_objectives` includes the
                          | resolved objective. Currently only
                          | exploratory_result_is_not_interpretable.
    user_overrides        | rule ids of choices the user explicitly made
    (passed to gate())    | or confirmed (e.g. plot_in_loglog after asking
                          | for linear axes). Not repaired.

------------------------------------------------------------------------------
CONTRACT: the `code` argument
------------------------------------------------------------------------------
run_checks() takes a plain code string. Extracting it from the LLM response
is the code agent's job (generate_code_node in handlers.py), not this
module's. A prose-only reply with no code is not a failure: declining to
write code and explaining why can be the CORRECT response. The caller must
skip run_checks() in that case rather than pass an empty string, which would
be scored as missing required steps.

Until the plan step exists (Phase 3), any caller of run_checks() or
check_disclosures() must build this dict itself. Do not let this module
guess at these values — a wrong `objective` silently changes which checks
even apply, which is exactly the class of silent failure this whole
redesign exists to prevent.

------------------------------------------------------------------------------
OPEN — undecided, do not resolve by guessing
------------------------------------------------------------------------------
1. How is pyleoclim_api.json (consumed via api_validation.validate(), see
   run_checks() below) kept in sync with the installed Pyleoclim version at
   runtime — regenerated at container build time, refreshed on a schedule,
   something else? Infrastructure question, not a schema or scoring
   question. api_validation.py sits next to this module and prefers the
   installed pyleoclim over the bundled JSON — but pyleoclim is only
   installed in the isolated execution container, not the backend, so in
   the backend it always falls back to the bundled snapshot.
------------------------------------------------------------------------------
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

# Methods that assume even sampling and therefore require a regrid step first.
EVEN_SPACING_METHODS = {"mtm", "welch", "periodogram", "cwt"}

# Methods that tolerate uneven sampling and therefore need no regridding.
UNEVEN_TOLERANT_METHODS = {"wwz", "lomb_scargle"}

# Steps the workflow marks `required` regardless of objective.
ALWAYS_REQUIRED_STEPS = {"standardize", "spectral"}

# Valid literals for Series.spectral(method=...). An invalid value raises just
# as surely as an invalid parameter name, but is invisible to a signature check.
VALID_SPECTRAL_METHODS = {"mtm", "welch", "periodogram", "lomb_scargle",
                          "wwz", "cwt"}

# Attributes whose extraction indicates a domain object being dismantled.
DOMAIN_ATTRS = {"value", "time", "frequency", "amplitude", "period"}

REGRID_CALLS = {"interp", "bin"}

# Canonical preprocessing order (rule: preprocessing_order_is_fixed).
# Steps may be skipped; those that run must keep this relative order.
PREPROC_ORDER = ["detrend", "outliers", "regrid", "standardize"]
PREPROC_ALIASES = {"detrend": "detrend", "outliers": "outliers",
                   "interp": "regrid", "bin": "regrid",
                   "standardize": "standardize"}
PLOTTING_MODULES = {"plt", "pyplot", "pylab"}


@dataclass
class Finding:
    rule: str
    severity: str
    status: str
    detail: str = ""


@dataclass
class CodeFacts:
    """Everything the checks need, extracted from the AST in one pass."""
    parsed: bool = True
    parse_error: str = ""
    spectral_call_line: int | None = None
    spectral_method: str | None = None
    spectral_settings_keys: set[str] = field(default_factory=set)
    regrid_lines: list[int] = field(default_factory=list)
    detrend_step_lines: list[int] = field(default_factory=list)
    calls_signif_test: bool = False
    calls_beta_est: bool = False
    uses_utils_spectral_directly: bool = False
    dismantle_sites: list[str] = field(default_factory=list)
    plot_kwargs: dict = field(default_factory=dict)
    receiver_names: set[str] = field(default_factory=set)
    preproc_sequence: list[str] = field(default_factory=list)
    rebound_vars: list[str] = field(default_factory=list)
    discarded_results: list[str] = field(default_factory=list)
    undisplayed_result: list[str] = field(default_factory=list)
    runtime_conditionals: list[str] = field(default_factory=list)


def _kwarg_str(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str):
                return kw.value.value
    return None


def _kwarg_node(call: ast.Call, name: str):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _chain_depth(call: ast.Call) -> int:
    """How many calls are nested beneath this one in its receiver chain.

    In `ts.detrend().interp()` the detrend call has depth 0 and interp depth 1,
    so sorting by depth recovers the order the steps are actually applied —
    which line numbers alone cannot do for a chained pipeline.
    """
    depth, node = 0, call.func
    while isinstance(node, ast.Attribute):
        node = node.value
        if isinstance(node, ast.Call):
            depth += 1
            node = node.func
        else:
            break
    return depth


def _root_name(call: ast.Call) -> str | None:
    node = call.func
    while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def extract_facts(code: str) -> CodeFacts:
    facts = CodeFacts()
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        facts.parsed = False
        facts.parse_error = str(exc)
        return facts

    # applied order of preprocessing steps, chain-aware
    ordered = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            canon = PREPROC_ALIASES.get(node.func.attr)
            if canon:
                ordered.append(((node.lineno, _chain_depth(node)), canon))
    seen = []
    for _key, canon in sorted(ordered):
        if not seen or seen[-1] != canon:
            seen.append(canon)
    facts.preproc_sequence = seen

    # Rebinding a variable the USER owns: `ts = ts.interp()`.
    # Rebinding a variable the code created itself (`psd = psd.signif_test()`)
    # is fine — the user never had a handle on it. So a name only counts as
    # user-owned until the code first assigns it.
    locally_assigned: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Call):
            root = _root_name(node.value)
            if root and root == target.id and root not in locally_assigned:
                facts.rebound_vars.append(
                    f"line {node.lineno}: {root} = {root}... (overwrites the "
                    f"user's object)"
                )
        locally_assigned.add(target.id)

    # Results computed and then thrown away. `psd2 = psd.signif_test(...)`
    # followed by `psd.plot(...)` silently discards the significance test: the
    # figure is drawn from the untested PSD and shows no significance bands.
    assigned: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Attribute):
                assigned[node.targets[0].id] = node.lineno
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
    last_assigned_line = max(assigned.values()) if assigned else -1
    for name, lineno in assigned.items():
        if name in used:
            continue
        if lineno == last_assigned_line:
            # The final result. Not a dropped intermediate, but in a notebook an
            # assignment displays nothing - the user sees no output at all.
            facts.undisplayed_result.append(
                f"line {lineno}: `{name}` is the final result but is never "
                f"displayed or plotted"
            )
        else:
            facts.discarded_results.append(
                f"line {lineno}: `{name}` is computed but never used - the "
                f"work is silently thrown away"
            )

    # Runtime branching on a data property (inspection.emit_conditionals: false)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    facts.runtime_conditionals.append(
                        f"line {node.lineno}: branches on .{sub.func.attr}()"
                    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # ---- method calls: obj.method(...) --------------------------------
        if isinstance(func, ast.Attribute):
            name = func.attr

            # which variable is this method chain rooted at?
            if name in {"spectral", "interp", "bin", "detrend", "standardize",
                        "outliers", "wavelet"}:
                root = func.value
                while isinstance(root, (ast.Attribute, ast.Call, ast.Subscript)):
                    root = root.func if isinstance(root, ast.Call) else root.value
                if isinstance(root, ast.Name):
                    facts.receiver_names.add(root.id)

            if name == "spectral":
                facts.spectral_call_line = node.lineno
                facts.spectral_method = _kwarg_str(node, "method")
                settings = _kwarg_node(node, "settings")
                if isinstance(settings, ast.Dict):
                    facts.spectral_settings_keys = {
                        k.value for k in settings.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }

            elif name in REGRID_CALLS:
                facts.regrid_lines.append(node.lineno)

            elif name == "detrend":
                facts.detrend_step_lines.append(node.lineno)

            elif name == "signif_test":
                facts.calls_signif_test = True

            elif name == "beta_est":
                facts.calls_beta_est = True

            # utils.spectral.<fn>(...) called directly rather than via core
            if isinstance(func.value, ast.Attribute) and func.value.attr == "spectral":
                if isinstance(func.value.value, ast.Attribute) and \
                        func.value.value.attr == "utils":
                    facts.uses_utils_spectral_directly = True

            # ---- plotting: did a dismantled object flow into pyplot? ------
            root = func.value
            while isinstance(root, ast.Attribute):
                root = root.value
            is_pyplot = isinstance(root, ast.Name) and root.id in PLOTTING_MODULES
            if is_pyplot:
                for arg in list(node.args) + [k.value for k in node.keywords]:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Attribute) and sub.attr in DOMAIN_ATTRS:
                            facts.dismantle_sites.append(
                                f"line {node.lineno}: .{sub.attr} passed to "
                                f"{root.id}.{func.attr}()"
                            )

            # ---- plot kwargs on a Pyleoclim .plot() call ------------------
            if name == "plot":
                for kw in node.keywords:
                    if kw.arg in {"in_loglog", "in_period"} and \
                            isinstance(kw.value, ast.Constant):
                        facts.plot_kwargs[kw.arg] = kw.value.value

    return facts


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

# Disclosure checks read the assistant's PROSE, not its code. They are keyword
# heuristics and therefore weaker than the AST checks. Being retired: PaleoPAL
# now adds required statements itself from the workflow YAML's `must_say`, so
# the model is no longer responsible for them. Kept until that is wired.
SIGNIF_TERMS = ("signif", "significance", "null model", "red noise",
                "noise model", "ar1", "not significant", "interpret")


def check_disclosures(raw_response: str, task: dict) -> list[Finding]:
    out: list[Finding] = []
    prose_all = re.sub(r"```.*?```", " ", raw_response, flags=re.DOTALL).lower()

    # Task-declared prose obligations: at least one term from each group.
    for group in task.get("must_mention", []):
        terms = [t.lower() for t in group]
        out.append(Finding(
            "required_disclosure", "prohibited",
            "ok" if any(t in prose_all for t in terms) else "violated",
            "" if any(t in prose_all for t in terms)
            else f"response never mentions any of: {', '.join(terms)}",
        ))

    if task.get("objective") == "exploratory":
        prose = re.sub(r"```.*?```", " ", raw_response.lower(), flags=re.DOTALL)
        mentioned = any(t in prose for t in SIGNIF_TERMS)
        out.append(Finding(
            "exploratory_caveat_stated", "prohibited",
            "ok" if mentioned else "violated",
            "" if mentioned else
            "no mention that significance testing is needed before interpreting",
        ))
    return out


def run_checks(code: str, task: dict) -> list[Finding]:
    """See the module docstring's `task` CONTRACT before calling this live —
    every field below must come from the plan step, not be guessed here."""
    facts = extract_facts(code)
    objective = task.get("objective")
    out: list[Finding] = []

    if not facts.parsed:
        return [Finding("code_parses", "prohibited", "violated", facts.parse_error)]
    out.append(Finding("code_parses", "prohibited", "ok"))

    # --- does the code call functions that actually exist? ------------------
    # The single most important check: structurally perfect code that calls a
    # non-existent method fails on line 1. Depends on api_validation.py and
    # pyleoclim_api.json being kept live-accurate — see OPEN item 1 in the module docstring.
    try:
        from .api_validation import validate
        unknown, bad_kwargs, _src = validate(code)
        out.append(Finding(
            "api_methods_exist", "prohibited",
            "violated" if unknown else "ok", "; ".join(unknown)))
        out.append(Finding(
            "api_kwargs_valid", "prohibited",
            "violated" if bad_kwargs else "ok", "; ".join(bad_kwargs)))
    except Exception as exc:                      # noqa: BLE001
        out.append(Finding("api_methods_exist", "prohibited", "unknown", str(exc)))

    # --- matplotlib_is_continuation_not_fallback ---------------------------
    out.append(Finding(
        "object_not_dismantled", "discouraged",
        "violated" if facts.dismantle_sites else "ok",
        "; ".join(facts.dismantle_sites),
    ))

    # --- uneven_spacing_requires_regridding --------------------------------
    method = facts.spectral_method
    if method in EVEN_SPACING_METHODS and facts.spectral_call_line:
        # <= not <, because a chained call such as
        #   ts.interp().spectral(method='mtm')
        # puts both on the same source line.
        regridded_before = any(
            ln <= facts.spectral_call_line for ln in facts.regrid_lines
        )
        out.append(Finding(
            "regrid_before_even_spacing_method", "prohibited",
            "ok" if regridded_before else "violated",
            f"method={method}, regrid lines={facts.regrid_lines}",
        ))
    else:
        out.append(Finding(
            "regrid_before_even_spacing_method", "prohibited", "ok",
            f"not applicable (method={method})",
        ))

    # --- lomb_scargle_high_frequency_bias ----------------------------------
    if objective == "scaling_exponent":
        bad = method == "lomb_scargle"
        out.append(Finding(
            "no_lomb_scargle_for_slope", "prohibited",
            "violated" if bad else "ok",
            f"method={method}",
        ))

    # --- peaks_require_null_model ------------------------------------------
    if objective == "peak_detection":
        out.append(Finding(
            "significance_tested", "prohibited",
            "ok" if facts.calls_signif_test else "violated",
        ))

    # --- objective actually attempted --------------------------------------
    if objective == "scaling_exponent":
        out.append(Finding(
            "beta_estimated", "prohibited",
            "ok" if facts.calls_beta_est else "violated",
        ))

    # --- caution_double_detrending -----------------------------------------
    double = bool(facts.detrend_step_lines) and "detrend" in facts.spectral_settings_keys
    out.append(Finding(
        "no_double_detrending", "prohibited",
        "violated" if double else "ok",
        "detrend applied as a step AND passed via settings" if double else "",
    ))

    # --- preprocessing_order_is_fixed ---------------------------------------
    seq = facts.preproc_sequence
    idx = [PREPROC_ORDER.index(x) for x in seq if x in PREPROC_ORDER]
    ordered_ok = idx == sorted(idx)
    out.append(Finding(
        "preprocessing_order", "prohibited",
        "ok" if ordered_ok else "violated",
        f"applied: {' -> '.join(seq)}; expected relative order "
        f"{' -> '.join(PREPROC_ORDER)}" if not ordered_ok else "",
    ))

    # --- prefer_chaining_over_rebinding -------------------------------------
    out.append(Finding(
        "no_user_variable_rebinding", "discouraged",
        "violated" if facts.rebound_vars else "ok",
        "; ".join(facts.rebound_vars),
    ))

    # --- is method= even a real literal? ------------------------------------
    if method is not None:
        if method in VALID_SPECTRAL_METHODS:
            out.append(Finding("method_literal_valid", "prohibited", "ok"))
        else:
            near = [m for m in VALID_SPECTRAL_METHODS
                    if m.replace("_", "") == method.replace("_", "").lower()]
            hint = f" (did you mean '{near[0]}'?)" if near else \
                   f" (valid: {', '.join(sorted(VALID_SPECTRAL_METHODS))})"
            out.append(Finding(
                "method_literal_valid", "prohibited", "violated",
                f"method='{method}' is not a valid value{hint}",
            ))

    # --- method choice given a stated data property -------------------------
    # When the record is known to be unevenly sampled, a tolerant estimator
    # (WWZ, Lomb-Scargle) avoids regridding entirely. Regridding anyway is a
    # needless loss of information, not an error.
    if task.get("data_evenly_spaced") is False and method:
        if method in UNEVEN_TOLERANT_METHODS:
            # Right method, but regridding anyway throws away the advantage.
            if facts.regrid_lines:
                out.append(Finding(
                    "no_unnecessary_regrid", "discouraged", "violated",
                    f"{method} tolerates uneven sampling, yet the code regrids "
                    f"anyway - a needless loss of information",
                ))
            else:
                out.append(Finding("no_unnecessary_regrid", "discouraged", "ok"))
            out.append(Finding("method_suits_uneven_data", "discouraged", "ok",
                               f"{method} tolerates uneven sampling"))
        elif method in EVEN_SPACING_METHODS:
            out.append(Finding(
                "method_suits_uneven_data", "discouraged", "violated",
                f"chose {method}, which forced regridding, when "
                f"{' or '.join(sorted(UNEVEN_TOLERANT_METHODS))} would not have",
            ))

    # --- did it finish the workflow? ----------------------------------------
    present = set(facts.preproc_sequence)
    if facts.spectral_call_line:
        present.add("spectral")
    missing = sorted(ALWAYS_REQUIRED_STEPS - present)
    out.append(Finding(
        "required_steps_present", "prohibited",
        "violated" if missing else "ok",
        f"missing required step(s): {', '.join(missing)}" if missing else "",
    ))

    # --- results must actually be used --------------------------------------
    out.append(Finding(
        "no_discarded_results", "prohibited",
        "violated" if facts.discarded_results else "ok",
        "; ".join(facts.discarded_results),
    ))

    out.append(Finding(
        "result_displayed", "discouraged",
        "violated" if facts.undisplayed_result else "ok",
        "; ".join(facts.undisplayed_result),
    ))

    # --- inspection.emit_conditionals: false --------------------------------
    # NOTE: in the harness the model had no kernel access, so it couldn't
    # resolve the branch itself, and this was scored `discouraged` rather than
    # `prohibited` on that basis. LIVE, PaleoPAL DOES have kernel access via
    # the plan step — so a runtime conditional in live-generated code is a
    # worse sign than it was in the harness: the information needed to avoid
    # it was available and unused. Worth revisiting whether this should be
    # `prohibited` live rather than carrying over `discouraged` unexamined.
    out.append(Finding(
        "no_runtime_data_branching", "discouraged",
        "violated" if facts.runtime_conditionals else "ok",
        "; ".join(facts.runtime_conditionals),
    ))

    # --- prefer the core API ------------------------------------------------
    out.append(Finding(
        "uses_core_api", "discouraged",
        "violated" if facts.uses_utils_spectral_directly else "ok",
    ))

    # --- cwt discouraged as a first choice ----------------------------------
    out.append(Finding(
        "cwt_not_first_choice", "discouraged",
        "violated" if method == "cwt" else "ok",
        f"method={method}",
    ))

    # --- exploratory_result_is_not_interpretable (do_not clause) ------------
    if objective == "exploratory":
        out.append(Finding(
            "no_unrequested_significance", "discouraged",
            "violated" if facts.calls_signif_test else "ok",
            "signif_test run on an exploratory request" if facts.calls_signif_test else "",
        ))

    # --- operated on the object the user actually named ---------------------
    expected = task.get("expected_object")
    if expected:
        used = facts.receiver_names
        if not used:
            out.append(Finding("correct_object", "prohibited", "unknown",
                               "no recognisable receiver found"))
        else:
            out.append(Finding(
                "correct_object", "prohibited",
                "ok" if expected in used else "violated",
                f"expected {expected}, code operated on {sorted(used)}",
            ))

    # --- plotting defaults (advisory) ---------------------------------------
    # PSD.plot() is already log-log by default, so a plain psd.plot() is
    # fine; only an explicit in_loglog=False departs from it. When the USER
    # asked for that, it's deliberate — pass it in task["user_overrides"]
    # and gate() will not repair it.
    if task.get("expects_plot"):
        loglog = facts.plot_kwargs.get("in_loglog")
        out.append(Finding(
            "plot_in_loglog", "advisory",
            "violated" if loglog is False else "ok",
            f"in_loglog={loglog!r}",
        ))

    return out


# ---------------------------------------------------------------------------
# Gating — NEW, not in the harness.
#
# The harness's score() aggregated findings into weighted A/B statistics
# across many saved completions; it never needed to decide what to DO about a
# single generation, because nothing downstream consumed its output live.
# gate() replaces that job: given one generation's findings, decide whether
# PaleoPAL's own code goes back for REPAIR.
#
# Every violation in PaleoPAL's own code is repaired quietly, whatever its
# severity. Severity only governs how PaleoPAL treats the USER's gaps and
# choices (corrected snippet vs ask-and-wait), which is handled upstream, not
# here. The one exception is a choice the user explicitly confirmed (e.g.
# "regrid anyway", "linear axes"): its rule id goes in `user_overrides` and
# the violation is reported as overridden instead of repaired.
# ---------------------------------------------------------------------------

def gate(findings: list[Finding], user_overrides=()) -> dict:
    """
    Returns:
        repair      — True if any violation must go back to the model.
        violations  — findings to feed into REPAIR (any severity).
        overridden  — violations the user explicitly chose; leave them.
    Every repair should also be recorded in the internal repair history.
    """
    violated = [f for f in findings if f.status == "violated"]
    overridden = [f for f in violated if f.rule in user_overrides]
    to_repair = [f for f in violated if f.rule not in user_overrides]
    return {
        "repair": bool(to_repair),
        "violations": to_repair,
        "overridden": overridden,
    }

