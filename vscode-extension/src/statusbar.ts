import * as vscode from 'vscode';

export class AgentCellStatusBarProvider implements vscode.NotebookCellStatusBarItemProvider {
  provideCellStatusBarItems(cell: vscode.NotebookCell, _token: vscode.CancellationToken): vscode.NotebookCellStatusBarItem[] | undefined {
    try {
      // Show on both markup and code cells if content starts with @agent
      const text = cell.document.getText().trim();
      if (!/^\s*@agent\b/i.test(text)) return;
      const item = new vscode.NotebookCellStatusBarItem('$(robot) Run Agent', vscode.NotebookCellStatusBarAlignment.Right);
      item.command = {
        command: 'paleopal.runAgentForCell',
        title: 'Run Agent',
        arguments: []
      };
      item.tooltip = 'Run PaleoPal agent for this cell';
      return [item];
    } catch {
      return;
    }
  }
}


