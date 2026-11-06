import * as vscode from 'vscode';

// Facts about the data in the researcher's running kernel, read with one fixed, reviewed,
// read-only snippet (approved by Deborah, 2026-11-05). Nothing else ever runs in the kernel
// this way, and never code written by a model. If anything fails, the request goes ahead
// without the facts, as before.

// Reviewed text: change it only with Deborah's approval. It runs in a private namespace, never
// imports anything into the kernel, reads only Pyleoclim Series, and reads no measured values.
// The time axis (the age model) is for the backend's own checks and must never go into a prompt.
export const INSPECTION_SNIPPET = `exec(compile('''
import json, sys, warnings
facts = {"pyleoclim_version": None, "series": []}
pyleo = sys.modules.get("pyleoclim")  # never imports it: only reads what is already loaded
if pyleo is not None:
    facts["pyleoclim_version"] = getattr(pyleo, "__version__", None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, obj in list(user_ns.items()):
            if name.startswith("_") or not isinstance(obj, pyleo.core.series.Series):
                continue
            entry = {"name": name, "type": type(obj).__name__}
            try:
                entry.update(time_unit=obj.time_unit, time_name=obj.time_name, n_points=int(len(obj.time)),
                             time_min=float(obj.time.min()), time_max=float(obj.time.max()),
                             evenly_spaced=bool(obj.is_evenly_spaced()))
                if len(obj.time) <= 100000:  # the age model, for PaleoPAL's own checks only
                    entry["time_values"] = [float(t) for t in obj.time]
            except Exception:
                pass
            facts["series"].append(entry)
print("PALEOPAL_FACTS" + json.dumps(facts))
''', '<paleopal-inspection>', 'exec'), {'user_ns': get_ipython().user_ns})`;

const MARKER = 'PALEOPAL_FACTS';
const TIMEOUT_MS = 8000; // a busy kernel must not hold up the request
// Versioned, so a researcher sees the explanation again whenever its wording changes.
const EXPLAINED_KEY = 'paleopal.kernelAccessExplained.v2';

export interface KernelFacts {
  pyleoclim_version: string | null;
  series: { name: string; type: string; time_unit?: string; time_name?: string; n_points?: number;
            time_min?: number; time_max?: number; evenly_spaced?: boolean }[];
}

let declinedThisSession = false;

// Where the read stops, for diagnosing; never any data.
const log = vscode.window.createOutputChannel('PaleoPAL');

// Shown once, just before VS Code's own access prompt, whose wording PaleoPAL can't change.
async function explainOnce(state: vscode.Memento): Promise<boolean> {
  if (state.get<boolean>(EXPLAINED_KEY)) return true;
  if (declinedThisSession) return false;
  const choice = await vscode.window.showInformationMessage(
    'PaleoPAL would like to look at your notebook\'s running kernel.',
    {
      modal: true,
      detail: 'I only run a small set of fixed, read-only checks. They read descriptions of your data, such as '
        + 'the time units, time axis, number of points and spacing of your series, and the versions of the '
        + 'packages I work with. The time axis stays on your local machine or server: my own checks use it, '
        + 'for example to count how many points a slice leaves, and it is never sent to the AI model. The '
        + 'checks read none of your measured values and leave nothing in your session. I never run any other '
        + 'code there, including code I write. '
        + 'VS Code will now ask you to allow this. You can change your mind later with '
        + '"Jupyter: Manage Access To Jupyter Kernels".'
    },
    'Continue', 'Not now');
  if (choice !== 'Continue') {
    declinedThisSession = true;
    return false;
  }
  await state.update(EXPLAINED_KEY, true);
  return true;
}

export async function readKernelFacts(notebook: vscode.NotebookDocument | undefined,
                                      state: vscode.Memento): Promise<KernelFacts | undefined> {
  if (!notebook) return undefined;
  try {
    const jupyter = vscode.extensions.getExtension<any>('ms-toolsai.jupyter');
    if (!jupyter) { log.appendLine('Kernel read: the Jupyter extension is not installed.'); return undefined; }
    if (!jupyter.isActive) await jupyter.activate();
    const kernels = jupyter.exports?.kernels;
    if (!kernels?.getKernel) { log.appendLine('Kernel read: the Jupyter extension has no kernels API.'); return undefined; }
    if (!(await explainOnce(state))) { log.appendLine('Kernel read: skipped, access not granted this session.'); return undefined; }
    const kernel = await kernels.getKernel(notebook.uri); // undefined until the researcher starts one
    if (!kernel) { log.appendLine('Kernel read: no kernel started in this window. Run a cell in the notebook first (reloading the window disconnects the kernel).'); return undefined; }

    const source = new vscode.CancellationTokenSource();
    const timer = setTimeout(() => source.cancel(), TIMEOUT_MS);
    let text = '';
    const mimes = new Set<string>();
    try {
      for await (const output of kernel.executeCode(INSPECTION_SNIPPET, source.token)) {
        for (const item of output.items ?? []) {
          mimes.add(item.mime);
          if (item.mime === 'application/vnd.code.notebook.stdout') text += new TextDecoder().decode(item.data);
          // An error output carries the exception's name, not data.
          if (item.mime === 'application/vnd.code.notebook.error') {
            try { log.appendLine(`Kernel read: the check raised ${JSON.parse(new TextDecoder().decode(item.data)).name}.`); } catch { /* ignore */ }
          }
        }
      }
    } finally {
      clearTimeout(timer);
      source.dispose();
    }
    const start = text.indexOf(MARKER);
    if (start < 0) {
      log.appendLine(`Kernel read: the check ran but returned no facts (${text.length} characters; output types: ${[...mimes].join(', ') || 'none'}).`);
      return undefined;
    }
    const facts = JSON.parse(text.slice(start + MARKER.length).split('\n')[0]) as KernelFacts;
    log.appendLine(`Kernel read: ${facts.series.length} series found (${facts.series.map(s => s.name).join(', ') || 'none'}).`);
    return facts;
  } catch (e: any) {
    // No access, no kernel, or a busy kernel: carry on without the facts.
    log.appendLine(`Kernel read failed: ${e?.name || ''} ${e?.message || e}`);
    return undefined;
  }
}
