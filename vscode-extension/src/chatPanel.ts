import * as vscode from 'vscode';
import { buildConversationHistoryFromNotebook, insertAgentCells, AgentCell } from './notebook';

// A conversation about the notebook, opened by `@agent chat`. All reasoning is in the backend;
// this panel shows the replies, sends the researcher's messages and inserts the summary cells.
// The conversation lives only in this panel: once it closes, only the summary remains.

interface Source { title: string; text: string; link?: string | null; }

interface Turn {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  note?: string | null;
  code?: string;
  problems?: string[];
}

export interface ChatOptions {
  question: string;
  notebook: vscode.NotebookDocument;
  // The `@agent chat` cell; the summary goes below it, wherever it is by then.
  anchor?: vscode.NotebookCell;
  apiBase: string;
  provider: string;
  model: string;
}

async function post(apiBase: string, body: any): Promise<any> {
  const res = await fetch(`${apiBase}/agents/chat_session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`PaleoPAL's chat failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function renderMarkdown(text: string): Promise<string> {
  try {
    const html = await vscode.commands.executeCommand<string>('markdown.api.render', text);
    if (typeof html === 'string') return html;
  } catch { /* fall back to plain text */ }
  return `<p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>`;
}

// What the backend sees of an earlier reply: its words and any code it proposed.
function forBackend(turns: Turn[]) {
  return turns.map(t => ({
    role: t.role,
    content: t.code ? `${t.content}\n\n\`\`\`python\n${t.code}\n\`\`\`` : t.content,
    sources: t.sources ?? [],
    note: t.note ?? null
  }));
}

export function openChatPanel(options: ChatOptions) {
  const panel = vscode.window.createWebviewPanel(
    'paleopalChat', 'PaleoPAL chat', vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );
  panel.webview.html = chatHtml(panel.webview);

  const turns: Turn[] = [];
  let summarized = false;
  let busy = false;

  const show = async (turn: Turn) => {
    const sources = await Promise.all((turn.sources ?? []).map(async s => ({
      title: await renderMarkdown(s.link ? `[${s.title}](${s.link})` : s.title),
      text: escapeHtml(s.text)
    })));
    panel.webview.postMessage({
      type: 'turn', role: turn.role,
      html: turn.role === 'user' ? `<p>${escapeHtml(turn.content)}</p>` : await renderMarkdown(turn.content),
      code: turn.code ? escapeHtml(turn.code) : '', note: turn.note ?? '',
      problems: (turn.problems ?? []).map(escapeHtml), sources
    });
  };

  const ask = async (text: string) => {
    if (busy) return;
    busy = true;
    const turn: Turn = { role: 'user', content: text };
    turns.push(turn);
    await show(turn);
    panel.webview.postMessage({ type: 'busy', on: true });
    try {
      const r = await post(options.apiBase, {
        action: 'reply', notebook: buildConversationHistoryFromNotebook(options.notebook),
        messages: forBackend(turns), llm_provider: options.provider, model: options.model
      });
      const reply: Turn = { role: 'assistant', content: r.reply || '', sources: r.sources, note: r.note,
                            code: r.code, problems: r.problems };
      turns.push(reply);
      await show(reply);
      if (r.offer_summary) panel.webview.postMessage({ type: 'offer' });
    } catch (e: any) {
      panel.webview.postMessage({ type: 'error', text: String(e?.message || e) });
    } finally {
      busy = false;
      panel.webview.postMessage({ type: 'busy', on: false });
    }
  };

  const addSummary = async (): Promise<boolean> => {
    if (summarized || !turns.some(t => t.role === 'assistant')) return false;
    try {
      const r = await post(options.apiBase, {
        action: 'summarize', notebook: buildConversationHistoryFromNotebook(options.notebook),
        messages: forBackend(turns), llm_provider: options.provider, model: options.model
      });
      const cells: AgentCell[] = Array.isArray(r.cells) ? r.cells : [];
      if (cells.length === 0) return false;
      const after = options.anchor && options.anchor.index >= 0 ? options.anchor.index : options.notebook.cellCount - 1;
      await insertAgentCells(after, cells, options.notebook);
      summarized = true;
      return true;
    } catch (e: any) {
      vscode.window.showErrorMessage(String(e?.message || e));
      return false;
    }
  };

  panel.webview.onDidReceiveMessage(async msg => {
    if (msg.type === 'send' && typeof msg.text === 'string' && msg.text.trim()) {
      await ask(msg.text.trim());
    } else if (msg.type === 'summarize') {
      panel.webview.postMessage({ type: 'busy', on: true, text: 'Writing the summary…' });
      const added = await addSummary();
      panel.webview.postMessage({ type: 'busy', on: false });
      if (added) panel.webview.postMessage({ type: 'summarized' });
    }
  });

  // A panel can't be kept open, so ask right after it closes, while the conversation is still here.
  panel.onDidDispose(async () => {
    if (summarized || !turns.some(t => t.role === 'assistant')) return;
    const choice = await vscode.window.showInformationMessage(
      'Add a summary of this PaleoPAL chat to your notebook? The conversation itself isn\'t kept.',
      { modal: true }, 'Add summary', 'Close without a summary');
    if (choice === 'Add summary') await addSummary();
  });

  void ask(options.question);
}

function chatHtml(webview: vscode.Webview): string {
  const nonce = String(Date.now());
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PaleoPAL chat</title>
  <style>
    body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); color: var(--vscode-foreground); padding: 0 12px; }
    #log { padding-bottom: 150px; }
    .turn { margin: 12px 0; padding: 8px 12px; border-radius: 6px; }
    .user { background: var(--vscode-input-background); }
    .assistant { border-left: 3px solid var(--vscode-focusBorder); }
    .who { font-size: 0.85em; opacity: 0.7; margin-bottom: 4px; }
    pre { background: var(--vscode-textCodeBlock-background); padding: 8px; overflow-x: auto; }
    .note { font-style: italic; opacity: 0.85; }
    .problems { color: var(--vscode-errorForeground); }
    blockquote { margin: 4px 0 8px 0; padding-left: 8px; border-left: 2px solid var(--vscode-textBlockQuote-border); opacity: 0.9; }
    #offer, #done, #error { margin: 12px 0; padding: 8px 12px; border-radius: 6px; background: var(--vscode-editorWidget-background); }
    #bar { position: fixed; bottom: 0; left: 0; right: 0; padding: 8px 12px; background: var(--vscode-editor-background); border-top: 1px solid var(--vscode-panel-border); }
    textarea { width: 100%; box-sizing: border-box; min-height: 48px; font-family: inherit; color: var(--vscode-input-foreground); background: var(--vscode-input-background); border: 1px solid var(--vscode-input-border, transparent); }
    button { margin: 6px 6px 0 0; color: var(--vscode-button-foreground); background: var(--vscode-button-background); border: none; padding: 4px 10px; cursor: pointer; }
    button.secondary { color: var(--vscode-button-secondaryForeground); background: var(--vscode-button-secondaryBackground); }
    button:disabled { opacity: 0.5; cursor: default; }
    #status { font-size: 0.85em; opacity: 0.7; }
    [hidden] { display: none !important; }
  </style>
</head>
<body>
  <div id="log"></div>
  <div id="offer" hidden>Shall I add a summary of what we decided to your notebook?
    <div><button id="offerYes">Yes, add it</button><button id="offerNo" class="secondary">Not yet</button></div></div>
  <div id="done" hidden>I added the summary below your <code>@agent chat</code> cell. One undo removes it. You can close this panel.</div>
  <div id="error" class="problems" hidden></div>
  <div id="bar">
    <div id="status" hidden>PaleoPAL is thinking…</div>
    <textarea id="input" placeholder="Reply to PaleoPAL (Enter to send, Shift+Enter for a new line)"></textarea>
    <button id="send">Send</button><button id="summarize" class="secondary">Add summary to notebook</button>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const log = document.getElementById('log'), input = document.getElementById('input');
    const offer = document.getElementById('offer'), done = document.getElementById('done');
    const error = document.getElementById('error'), status = document.getElementById('status');
    const send = () => { const text = input.value.trim(); if (!text) return; input.value = ''; offer.hidden = true;
                         error.hidden = true; vscode.postMessage({ type: 'send', text }); };
    const summarize = () => { offer.hidden = true; vscode.postMessage({ type: 'summarize' }); };
    document.getElementById('send').addEventListener('click', send);
    document.getElementById('summarize').addEventListener('click', summarize);
    document.getElementById('offerYes').addEventListener('click', summarize);
    document.getElementById('offerNo').addEventListener('click', () => { offer.hidden = true; input.focus(); });
    input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    window.addEventListener('message', ({ data }) => {
      if (data.type === 'turn') {
        const div = document.createElement('div');
        div.className = 'turn ' + data.role;
        let html = '<div class="who">' + (data.role === 'user' ? 'You' : 'PaleoPAL') + '</div>' + data.html;
        if (data.code) html += '<pre><code>' + data.code + '</code></pre><div class="note">Not run. It reaches your notebook only through the summary, if you agree.</div>';
        if (data.problems.length) html += '<div class="problems">I\\'m still learning and can\\'t get this right yet, but I\\'m learning! Please check the code, because these problems remain: ' + data.problems.join('; ') + '</div>';
        if (data.note) html += '<p class="note">' + data.note + '</p>';
        if (data.sources.length) html += '<details><summary>Sources</summary>' +
          data.sources.map(s => s.title + '<blockquote>' + s.text + '</blockquote>').join('') + '</details>';
        div.innerHTML = html;
        log.appendChild(div);
        window.scrollTo(0, document.body.scrollHeight);
      } else if (data.type === 'busy') {
        status.textContent = data.text || 'PaleoPAL is thinking…';
        status.hidden = !data.on;
        document.querySelectorAll('button').forEach(b => b.disabled = data.on);
      } else if (data.type === 'offer') {
        offer.hidden = false; window.scrollTo(0, document.body.scrollHeight);
      } else if (data.type === 'summarized') {
        done.hidden = false; document.getElementById('summarize').disabled = true;
        window.scrollTo(0, document.body.scrollHeight);
      } else if (data.type === 'error') {
        error.textContent = data.text; error.hidden = false;
      }
    });
    input.focus();
  </script>
</body>
</html>`;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
}
