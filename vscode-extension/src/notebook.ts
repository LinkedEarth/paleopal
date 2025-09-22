import * as vscode from 'vscode';

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

export function getActiveNotebookEditor(): vscode.NotebookEditor | undefined {
  const editor = vscode.window.activeNotebookEditor;
  return editor;
}

export function buildConversationHistoryFromNotebook(): { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; }[] {
  const editor = getActiveNotebookEditor();
  const messages: { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; }[] = [];
  if (!editor) return messages;

  for (const cell of editor.notebook.getCells()) {
    if (cell.kind === vscode.NotebookCellKind.Markup) {
      const text = cell.document.getText();
      if (text.trim().length > 0) {
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

export function buildHistoryUpToCell(targetIndex: number): { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; }[] {
  const editor = getActiveNotebookEditor();
  const messages: { role: 'user' | 'assistant'; content: string; agent_type?: string; generated_content?: string; }[] = [];
  if (!editor) return messages;
  const cells = editor.notebook.getCells();
  for (let i = 0; i < Math.min(targetIndex, cells.length); i++) {
    const cell = cells[i];
    if (cell.kind === vscode.NotebookCellKind.Markup) {
      const text = cell.document.getText();
      if (text.trim().length > 0) messages.push({ role: 'user', content: text });
    } else if (cell.kind === vscode.NotebookCellKind.Code) {
      const code = cell.document.getText();
      if (code.trim().length > 0) messages.push({ role: 'assistant', content: '', agent_type: 'code', generated_content: code });
    }
  }
  return messages;
}

export function getActiveCellIndex(): number {
  const editor = getActiveNotebookEditor();
  if (!editor) return -1;
  const sel = editor.selections?.[0];
  return sel ? sel.start : -1;
}

export async function insertLoadingCell(afterIndex: number): Promise<number | undefined> {
  return insertMarkdownCellAt(afterIndex, '⏳ Running agent... (history from above cells)');
}

export async function updateCellText(cellIndex: number, text: string) {
  const editor = getActiveNotebookEditor();
  if (!editor) return;
  const cell = editor.notebook.cellAt(cellIndex);
  const edit = new vscode.WorkspaceEdit();
  const fullRange = new vscode.Range(0, 0, cell.document.lineCount, 0);
  edit.replace(cell.document.uri, fullRange, text);
  await vscode.workspace.applyEdit(edit);
}

export async function deleteCell(cellIndex: number) {
  const editor = getActiveNotebookEditor();
  if (!editor) return;
  const start = Math.max(0, Math.min(cellIndex, editor.notebook.cellCount - 1));
  // Use NotebookEdit.replaceCells to remove the cell at index
  const range = new vscode.NotebookRange(start, start + 1);
  const we = new vscode.WorkspaceEdit();
  we.set(editor.notebook.uri, [vscode.NotebookEdit.replaceCells(range, [])]);
  await vscode.workspace.applyEdit(we);
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

export async function insertMarkdownCellAt(afterIndex: number, text: string): Promise<number | undefined> {
  const editor = getActiveNotebookEditor();
  if (!editor) return;
  const insertIndex = Math.min(afterIndex + 1, editor.notebook.cellCount);
  const ws = new vscode.WorkspaceEdit();
  const cell = new vscode.NotebookCellData(vscode.NotebookCellKind.Markup, text, 'markdown');
  ws.set(editor.notebook.uri, [vscode.NotebookEdit.replaceCells(new vscode.NotebookRange(insertIndex, insertIndex), [cell])]);
  await vscode.workspace.applyEdit(ws);
  return insertIndex;
}

export async function insertCodeCellAt(afterIndex: number, code: string, language: string = 'python'): Promise<number | undefined> {
  const editor = getActiveNotebookEditor();
  if (!editor) return;
  const insertIndex = Math.min(afterIndex + 1, editor.notebook.cellCount);
  const ws = new vscode.WorkspaceEdit();
  const cell = new vscode.NotebookCellData(vscode.NotebookCellKind.Code, code, language);
  ws.set(editor.notebook.uri, [vscode.NotebookEdit.replaceCells(new vscode.NotebookRange(insertIndex, insertIndex), [cell])]);
  await vscode.workspace.applyEdit(ws);
  return insertIndex;
}

