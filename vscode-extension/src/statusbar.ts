import * as vscode from 'vscode';
import { TRIGGER } from './trigger';

export class AgentCellStatusBarProvider implements vscode.NotebookCellStatusBarItemProvider {
  provideCellStatusBarItems(cell: vscode.NotebookCell, _token: vscode.CancellationToken): vscode.NotebookCellStatusBarItem[] | undefined {
    try {
      // Show on both markup and code cells if content starts with @paleopal (or the older @agent)
      const text = cell.document.getText().trim();
      if (!TRIGGER.test(text)) return;
      const item = new vscode.NotebookCellStatusBarItem('$(robot) Ask PaleoPAL', vscode.NotebookCellStatusBarAlignment.Right);
      item.command = {
        command: 'paleopal.runAgentForCell',
        title: 'Ask PaleoPAL',
        arguments: []
      };
      item.tooltip = 'Send this cell to PaleoPAL';
      return [item];
    } catch {
      return;
    }
  }
}


