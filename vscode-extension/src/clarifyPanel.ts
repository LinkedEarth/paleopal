import * as vscode from 'vscode';

export interface ClarificationQuestion {
  id: string;
  question: string;
  choices?: string[];
  context?: string;
}

export interface ClarificationAnswer {
  id: string;
  answer: string;
}

export async function showClarificationPanel(questions: ClarificationQuestion[]): Promise<ClarificationAnswer[] | undefined> {
  const panel = vscode.window.createWebviewPanel(
    'paleopalClarifications',
    'PaleoPal: Clarifications Needed',
    vscode.ViewColumn.Active,
    { enableScripts: true, retainContextWhenHidden: false }
  );

  panel.webview.html = getHtmlForQuestions(panel.webview, questions);

  return new Promise(resolve => {
    const disposables: vscode.Disposable[] = [];
    panel.onDidDispose(() => {
      disposables.forEach(d => d.dispose());
      resolve(undefined);
    }, null, disposables);

    panel.webview.onDidReceiveMessage((msg) => {
      if (msg.type === 'submit') {
        const answers: ClarificationAnswer[] = Array.isArray(msg.answers) ? msg.answers : [];
        resolve(answers);
        panel.dispose();
      } else if (msg.type === 'cancel') {
        resolve(undefined);
        panel.dispose();
      }
    }, undefined, disposables);
  });
}

function getHtmlForQuestions(webview: vscode.Webview, questions: ClarificationQuestion[]) {
  const nonce = String(Date.now());
  const qHtml = questions.map((q, idx) => {
    const choices = Array.isArray(q.choices) ? q.choices : [];
    const select = choices.length > 0;
    const control = select
      ? `<select id="ans_${idx}">${choices.map(c => `<option>${escapeHtml(c)}</option>`).join('')}</select>`
      : `<input id="ans_${idx}" type="text" style="width:100%" />`;
    const context = q.context ? `<div style="color:#777; margin-top:4px">${escapeHtml(q.context)}</div>` : '';
    return `<div style="margin-bottom:16px">
      <div style="font-weight:600">${escapeHtml(q.question)}</div>
      ${context}
      ${control}
    </div>`;
  }).join('');

  return `<!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'nonce-${nonce}';">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PaleoPal Clarifications</title>
  </head>
  <body>
    <h2>Additional details needed</h2>
    <div>${qHtml}</div>
    <div style="margin-top:16px">
      <button id="submitBtn">Submit</button>
      <button id="cancelBtn">Cancel</button>
    </div>
    <script nonce="${nonce}">
      const vscode = acquireVsCodeApi();
      const questions = ${JSON.stringify(questions)};
      document.getElementById('submitBtn').addEventListener('click', () => {
        const answers = questions.map((q, idx) => {
          const el = document.getElementById('ans_'+idx);
          const value = el && ('value' in el) ? el.value : '';
          return { id: q.id || ('q'+idx), answer: String(value || '') };
        });
        vscode.postMessage({ type: 'submit', answers });
      });
      document.getElementById('cancelBtn').addEventListener('click', () => {
        vscode.postMessage({ type: 'cancel' });
      });
    </script>
  </body>
  </html>`;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c] as string));
}


