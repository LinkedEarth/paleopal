import * as vscode from 'vscode';

export const AUTHORSHIP_MARKDOWN = '*Written by PaleoPAL*';

export interface AgentCell {
  kind: 'markdown' | 'code';
  text: string;
  step?: string | null;
  decisions?: { step: string; answer: string }[];
}

function paleoPalLabel(cell: vscode.NotebookCell): any {
  const meta = cell.metadata as any;
  return meta?.metadata?.paleopal ?? meta?.custom?.metadata?.paleopal ?? meta?.paleopal;
}

// PaleoPAL's own explanations must not come back to the backend as the researcher's words.
// The visible authorship line is a backup in case the metadata is lost, e.g. by another editor.
function isPaleoPalMarkdown(cell: vscode.NotebookCell): boolean {
  return Boolean(paleoPalLabel(cell)) || cell.document.getText().includes(AUTHORSHIP_MARKDOWN);
}

export async function createNotebook(title?: string) {
  const nb = new vscode.NotebookData([
    new vscode.NotebookCellData(
      vscode.NotebookCellKind.Markup,
      `# ${title || 'PaleoPal Conversation'}\n\n`,
      'markdown'
    )
  ]);
  nb.metadata = {
    custom: {
      kernelspec: { display_name: 'Python 3', language: 'python', name: 'python3' },
      language_info: { name: 'python' }
    }
  } as any;
  const uri = vscode.Uri.parse('untitled:PaleoPal.ipynb');
  const doc = await vscode.workspace.openNotebookDocument('jupyter-notebook', nb);
  await vscode.window.showNotebookDocument(doc);
}

// PaleoPAL's own markdown goes back as its own earlier note, never as the researcher's words.
function paleoPalNote(cell: vscode.NotebookCell, text: string): any {
  return { role: 'assistant', content: text, agent_type: 'paleopal_note', decisions: paleoPalLabel(cell)?.decisions };
}

export function getActiveNotebookEditor(): vscode.NotebookEditor | undefined {
  const editor = vscode.window.activeNotebookEditor;
  return editor;
}

export function buildConversationHistoryFromNotebook(notebook?: vscode.NotebookDocument): { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; decisions?: any; }[] {
  const target = notebookOrActive(notebook);
  const messages: { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; decisions?: any; }[] = [];
  if (!target) return messages;

  for (const cell of target.getCells()) {
    if (cell.kind === vscode.NotebookCellKind.Markup) {
      const text = cell.document.getText();
      if (isPaleoPalMarkdown(cell)) {
        messages.push(paleoPalNote(cell, text));
      } else if (text.trim().length > 0) {
        messages.push({ role: 'user', content: text });
      }
    } else if (cell.kind === vscode.NotebookCellKind.Code) {
      const code = cell.document.getText();
      if (code.trim().length > 0) {
        messages.push({ role: 'assistant', content: '', agent_type: 'code', generated_content: code });
      }
    }
  }
  return messages;
}

export function buildHistoryUpToCell(targetIndex: number): { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; decisions?: any; }[] {
  const editor = getActiveNotebookEditor();
  const messages: { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; decisions?: any; }[] = [];
  if (!editor) return messages;
  const cells = editor.notebook.getCells();
  for (let i = 0; i < Math.min(targetIndex, cells.length); i++) {
    const cell = cells[i];
    if (cell.kind === vscode.NotebookCellKind.Markup) {
      const text = cell.document.getText();
      if (isPaleoPalMarkdown(cell)) messages.push(paleoPalNote(cell, text));
      else if (text.trim().length > 0) messages.push({ role: 'user', content: text });
    } else if (cell.kind === vscode.NotebookCellKind.Code) {
      const code = cell.document.getText();
      if (code.trim().length > 0) messages.push({ role: 'assistant', content: '', agent_type: 'code', generated_content: code });
    }
  }
  return messages;
}

// An edit goes to the notebook the request came from, which may no longer be the active tab.
function notebookOrActive(notebook?: vscode.NotebookDocument): vscode.NotebookDocument | undefined {
  return notebook ?? getActiveNotebookEditor()?.notebook;
}

async function applyOrWarn(edit: vscode.WorkspaceEdit): Promise<boolean> {
  const applied = await vscode.workspace.applyEdit(edit);
  if (!applied) vscode.window.showErrorMessage("PaleoPAL couldn't update the notebook. Is it still open?");
  return applied;
}

export function getActiveCellIndex(): number {
  const editor = getActiveNotebookEditor();
  if (!editor) return -1;
  const sel = editor.selections?.[0];
  return sel ? sel.start : -1;
}

export async function insertLoadingCell(afterIndex: number, notebook?: vscode.NotebookDocument): Promise<number | undefined> {
  return insertMarkdownCellAt(afterIndex, '⏳ Running agent... (history from above cells)', notebook);
}

export async function updateCellText(cellIndex: number, text: string, notebook?: vscode.NotebookDocument) {
  const target = notebookOrActive(notebook);
  if (!target) return;
  const cell = target.cellAt(cellIndex);
  const edit = new vscode.WorkspaceEdit();
  const fullRange = new vscode.Range(0, 0, cell.document.lineCount, 0);
  edit.replace(cell.document.uri, fullRange, text);
  await vscode.workspace.applyEdit(edit);
}

export async function deleteCell(cellIndex: number, notebook?: vscode.NotebookDocument) {
  const target = notebookOrActive(notebook);
  if (!target) return;
  const start = Math.max(0, Math.min(cellIndex, target.cellCount - 1));
  // Use NotebookEdit.replaceCells to remove the cell at index
  const range = new vscode.NotebookRange(start, start + 1);
  const we = new vscode.WorkspaceEdit();
  we.set(target.uri, [vscode.NotebookEdit.replaceCells(range, [])]);
  await applyOrWarn(we);
}

export async function appendMarkdownCell(text: string) {
  const editor = getActiveNotebookEditor();
  if (!editor) return;
  await insertMarkdownCellAt(editor.notebook.cellCount - 1, text);
}

export async function appendCodeCell(code: string, language: string = 'python') {
  const editor = getActiveNotebookEditor();
  if (!editor) return;
  await insertCodeCellAt(editor.notebook.cellCount - 1, code, language);
}

export async function runAllNotebookCells() {
  await vscode.commands.executeCommand('jupyter.runAllCells');
}

export async function insertMarkdownCellAt(afterIndex: number, text: string, notebook?: vscode.NotebookDocument): Promise<number | undefined> {
  const target = notebookOrActive(notebook);
  if (!target) return;
  const insertIndex = Math.min(afterIndex + 1, target.cellCount);
  const ws = new vscode.WorkspaceEdit();
  const cell = new vscode.NotebookCellData(vscode.NotebookCellKind.Markup, text, 'markdown');
  ws.set(target.uri, [vscode.NotebookEdit.replaceCells(new vscode.NotebookRange(insertIndex, insertIndex), [cell])]);
  await applyOrWarn(ws);
  return insertIndex;
}

// One edit, so a single undo removes everything PaleoPAL just added.
export async function insertAgentCells(afterIndex: number, cells: AgentCell[], notebook?: vscode.NotebookDocument): Promise<void> {
  const target = notebookOrActive(notebook);
  if (!target) return;
  const insertIndex = Math.min(afterIndex + 1, target.cellCount);
  const data = cells.map(cell => {
    const isCode = cell.kind === 'code';
    const cellData = new vscode.NotebookCellData(
      isCode ? vscode.NotebookCellKind.Code : vscode.NotebookCellKind.Markup,
      cell.text,
      isCode ? 'python' : 'markdown'
    );
    cellData.metadata = { metadata: { paleopal: { generated: true, step: cell.step ?? null, decisions: cell.decisions ?? [] } } };
    return cellData;
  });
  const ws = new vscode.WorkspaceEdit();
  ws.set(target.uri, [vscode.NotebookEdit.replaceCells(new vscode.NotebookRange(insertIndex, insertIndex), data)]);
  await applyOrWarn(ws);
}

export async function insertCodeCellAt(afterIndex: number, code: string, language: string = 'python', notebook?: vscode.NotebookDocument): Promise<number | undefined> {
  const target = notebookOrActive(notebook);
  if (!target) return;
  const insertIndex = Math.min(afterIndex + 1, target.cellCount);
  const ws = new vscode.WorkspaceEdit();
  const cell = new vscode.NotebookCellData(vscode.NotebookCellKind.Code, code, language);
  ws.set(target.uri, [vscode.NotebookEdit.replaceCells(new vscode.NotebookRange(insertIndex, insertIndex), [cell])]);
  await applyOrWarn(ws);
  return insertIndex;
}

