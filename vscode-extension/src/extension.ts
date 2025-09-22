import * as vscode from 'vscode';
import { randomUUID } from 'crypto';
import { createNotebook, buildConversationHistoryFromNotebook, appendMarkdownCell, appendCodeCell, runAllNotebookCells, buildHistoryUpToCell, getActiveCellIndex, insertLoadingCell, updateCellText, deleteCell, insertMarkdownCellAt } from './notebook';
import { showClarificationPanel, ClarificationQuestion } from './clarifyPanel';
import { AgentCellStatusBarProvider } from './statusbar';

type Role = 'system' | 'user' | 'assistant';

interface ChatMessage { role: Role; content: string; agent_type?: string; generated_content?: string; }

interface AgentRequestBody {
  agent_type: string;
  capability: string;
  conversation_id: string;
  user_input: string;
  context: Record<string, any>;
  notebook_context: Record<string, any>;
  metadata: Record<string, any>;
}

function getConfig() {
  const cfg = vscode.workspace.getConfiguration('paleopal');
  return {
    baseUrl: cfg.get<string>('backendUrl', 'http://localhost:8000'),
    provider: cfg.get<string>('defaultProvider', 'openai'),
    model: cfg.get<string>('defaultModel', 'gpt-4o'),
    enableClarification: cfg.get<boolean>('enableClarification', true),
    clarificationThreshold: cfg.get<string>('clarificationThreshold', 'conservative'),
    enableExecution: cfg.get<boolean>('enableExecution', false)
  };
}

function buildApiBase(baseUrl: string): string {
  const trimmed = baseUrl.replace(/\/+$/g, '');
  if (/\/api\/?$/.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

async function promptAgentType(): Promise<'code'|'sparql'|'workflow_generation'|'workflow'|'chat'|undefined> {
  const choice = await vscode.window.showQuickPick([
    { label: 'Code', value: 'code' },
    { label: 'SPARQL', value: 'sparql' },
    { label: 'Workflow', value: 'workflow_generation' },
    { label: 'Chat', value: 'chat' },
  ], { placeHolder: 'Select agent type' });
  return choice?.value as any;
}

function extractNotebookHistory(): ChatMessage[] {
  return buildConversationHistoryFromNotebook();
}

async function callAgentsRequest(body: AgentRequestBody) {
  const { baseUrl } = getConfig();
  const apiBase = buildApiBase(baseUrl);
  const url = `${apiBase}/agents/request`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Agent request failed: ${res.status} ${text}. Check PaleoPal backend URL setting (paleopal.backendUrl).`);
  }
  return res.json();
}

async function callChat(messages: ChatMessage[]) {
  const { baseUrl, provider, model } = getConfig();
  const apiBase = buildApiBase(baseUrl);
  const url = `${apiBase}/agents/chat`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, llm_provider: provider, model })
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Chat failed: ${res.status} ${text}. Check PaleoPal backend URL setting (paleopal.backendUrl).`);
  }
  return res.json();
}

async function newConversation() {
  await createNotebook('PaleoPal Conversation');
  vscode.window.showInformationMessage('PaleoPal: New notebook conversation created.');
}

async function askAgent() {
  const agentType = await promptAgentType();
  if (!agentType) return;

  const prompt = await vscode.window.showInputBox({ prompt: 'Enter your request' });
  if (!prompt) return;

  const convId = `client_${randomUUID()}`;
  const history = extractNotebookHistory();
  const { provider, model, enableClarification, clarificationThreshold, enableExecution } = getConfig();

  if (agentType === 'chat') {
    const messages: ChatMessage[] = [...history, { role: 'user', content: prompt }];
    const reply = await callChat(messages);
    await appendMarkdownCell(`**Assistant**\n\n${reply.content}`);
    return;
  }

  const capability = agentType === 'sparql' ? 'generate_query' : (agentType === 'workflow_generation') ? 'generate_workflow' : 'generate_code';
  const body: AgentRequestBody = {
    agent_type: agentType,
    capability,
    conversation_id: convId,
    user_input: prompt,
    context: { conversation_history: history },
    notebook_context: {},
    metadata: {
      stateless: true,
      enable_execution: enableExecution,
      llm_provider: provider,
      model,
      enable_clarification: enableClarification,
      clarification_threshold: clarificationThreshold
    }
  };

  const response = await callAgentsRequest(body);
  const code: string | undefined = response?.result?.generated_code;
  const msg: string = response?.message || 'Agent responded.';
  // Handle clarifications
  if (response?.status === 'needs_clarification' || response?.result?.clarification_questions) {
    const qs: ClarificationQuestion[] = (response?.result?.clarification_questions || response?.clarification_questions || []).map((q: any, i: number) => ({
      id: q.id || `q${i+1}`,
      question: q.question || String(q),
      choices: Array.isArray(q.choices) ? q.choices : undefined,
      context: q.context
    }));
    if (qs.length > 0) {
      const answers = await showClarificationPanel(qs);
      if (answers && answers.length > 0) {
        // Re-submit with clarification_responses in metadata
        const body2: AgentRequestBody = {
          ...body,
          metadata: {
            ...body.metadata,
            clarification_responses: answers.map(a => ({ id: a.id, answer: a.answer }))
          }
        };
        const resp2 = await callAgentsRequest(body2);
        const code2: string | undefined = resp2?.result?.generated_code;
        const msg2: string = resp2?.message || 'Agent responded.';
        if (msg2 && agentType !== 'workflow_generation') {
          await appendMarkdownCell(`**Agent**: ${msg2}`);
        }
        if (code2) {
          if (agentType === 'workflow_generation') {
            await appendMarkdownCell('```json\n' + code2 + '\n```');
          } else {
            await appendCodeCell(code2, 'python');
          }
        }
        return;
      }
    }
  }
  if (agentType === 'workflow_generation' && code) {
    await insertWorkflowFromJson(code);
  } else {
    if (msg) await appendMarkdownCell(`**Agent**: ${msg}`);
    if (code) await appendCodeCell(code, 'python');
  }
}

async function insertResult() {
  // Placeholder: this command can be used to insert arbitrary content (e.g., paste from clipboard)
  const content = await vscode.window.showInputBox({ prompt: 'Enter content to insert (markdown)' });
  if (!content) return;
  await appendMarkdownCell(content);
}

async function runNotebook() {
  await runAllNotebookCells();
}

// Markdown/code insertion now handled via notebook helpers

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.notebooks.registerNotebookCellStatusBarItemProvider('jupyter-notebook', new AgentCellStatusBarProvider())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand('paleopal.newConversation', newConversation),
    vscode.commands.registerCommand('paleopal.askAgent', askAgent),
    vscode.commands.registerCommand('paleopal.insertResult', insertResult),
    vscode.commands.registerCommand('paleopal.runNotebook', runNotebook),
    vscode.commands.registerCommand('paleopal.runAgentForCell', runAgentForCell),
    vscode.commands.registerCommand('paleopal.setDefaultModel', setDefaultModelQuickPick),
  );
}

export function deactivate() {}

// Command: Run Agent for current cell content if it starts with @agent
async function runAgentForCell() {
  const editor = vscode.window.activeNotebookEditor;
  if (!editor) {
    vscode.window.showErrorMessage('No active notebook.');
    return;
  }
  const idx = getActiveCellIndex();
  if (idx < 0) {
    vscode.window.showErrorMessage('No active cell selected.');
    return;
  }
  const cell = editor.notebook.cellAt(idx);
  const text = cell.document.getText().trim();
  if (!text.startsWith('@agent')) {
    vscode.window.showErrorMessage('Current cell does not start with @agent.');
    return;
  }
  // parse: @agent <type> <request text>
  const line = text.split(/\n/)[0];
  const parts = line.split(/\s+/);
  const agentTypeRaw = ((parts[1] || 'code') as any);
  const agentType = (agentTypeRaw === 'workflow' ? 'workflow_generation' : agentTypeRaw) as any;
  const userText = text.replace(/^@agent[^\n]*\n?/, '').trim();
  const convId = `client_${randomUUID()}`;
  const history = buildHistoryUpToCell(idx);
  const { provider, model, enableClarification, clarificationThreshold, enableExecution } = getConfig();

  const capability = agentType === 'sparql' ? 'generate_query' : (agentType === 'workflow_generation') ? 'generate_workflow' : 'generate_code';
  const body: AgentRequestBody = {
    agent_type: agentType,
    capability,
    conversation_id: convId,
    user_input: userText,
    context: { conversation_history: history },
    notebook_context: {},
    metadata: {
      stateless: true,
      enable_execution: enableExecution,
      llm_provider: provider,
      model,
      enable_clarification: enableClarification,
      clarification_threshold: clarificationThreshold
    }
  };

  const loadingIdx = await insertLoadingCell(idx);
  try {
    const response = await callAgentsRequest(body);
    // Clarifications
    if (response?.status === 'needs_clarification' || response?.result?.clarification_questions) {
      const qs: ClarificationQuestion[] = (response?.result?.clarification_questions || response?.clarification_questions || []).map((q: any, i: number) => ({
        id: q.id || `q${i+1}`,
        question: q.question || String(q),
        choices: Array.isArray(q.choices) ? q.choices : undefined,
        context: q.context
      }));
      if (qs.length > 0) {
        const answers = await showClarificationPanel(qs);
        if (answers && answers.length > 0) {
          const body2: AgentRequestBody = {
            ...body,
            metadata: { ...body.metadata, clarification_responses: answers.map(a => ({ id: a.id, answer: a.answer })) }
          };
          const resp2 = await callAgentsRequest(body2);
          if (loadingIdx !== undefined) await deleteCell(loadingIdx);
          const code2: string | undefined = resp2?.result?.generated_code;
          if (agentType === 'workflow_generation' && code2) {
            await insertWorkflowFromJson(code2, idx);
          } else if (code2) {
            await insertCodeBelowIndex(idx, code2);
          }
          return;
        }
      }
    }
    if (loadingIdx !== undefined) await deleteCell(loadingIdx);
    const code: string | undefined = response?.result?.generated_code;
    if (agentType === 'workflow_generation' && code) {
      await insertWorkflowFromJson(code, idx);
    } else if (code) {
      await insertCodeBelowIndex(idx, code);
    }
  } catch (e: any) {
    if (loadingIdx !== undefined) await updateCellText(loadingIdx, `❌ ${e?.message || e}`);
  }
}

async function insertWorkflowFromJson(jsonStr: string, afterIndex?: number) {
  try {
    const wf = JSON.parse(jsonStr);
    const steps: any[] = Array.isArray(wf?.steps) ? wf.steps : [];
    if (steps.length === 0) {
      await appendMarkdownCell('```json\n' + jsonStr + '\n```');
      return;
    }
    let cursor = typeof afterIndex === 'number' ? afterIndex : (vscode.window.activeNotebookEditor?.notebook.cellCount ?? 0) - 1;
    for (const step of steps) {
      const agent = (step.agent || 'code').toLowerCase();
      const description = (step.description || '').trim();
      const input = step.input ? String(step.input) : '';
      const expected = step.expected_output ? String(step.expected_output) : '';
      const header = `@agent ${agent === 'sparql' ? 'sparql' : 'code'}`;
      const parts: string[] = [];
      if (description) parts.push(description.replace(/\s+/g, ' '));
      if (input) parts.push(`Input: ${input.replace(/\s+/g, ' ')}`);
      if (expected) parts.push(`Expected Output: ${expected.replace(/\s+/g, ' ')}`);
      const body = parts.join(' ');
      const newIdx = await insertMarkdownCellAt(cursor, `${header}\n${body}`);
      if (typeof newIdx === 'number') cursor = newIdx;
    }
  } catch (err) {
    await appendMarkdownCell('```json\n' + jsonStr + '\n```');
  }
}

async function insertCodeBelowIndex(afterIndex: number, code: string) {
  // Insert code cell right below the triggering cell
  const editor = vscode.window.activeNotebookEditor;
  if (!editor) {
    await appendCodeCell(code, 'python');
    return;
  }
  const ws = new vscode.WorkspaceEdit();
  const insertIndex = Math.min(afterIndex + 1, editor.notebook.cellCount);
  const cell = new vscode.NotebookCellData(vscode.NotebookCellKind.Code, code, 'python');
  ws.set(editor.notebook.uri, [vscode.NotebookEdit.replaceCells(new vscode.NotebookRange(insertIndex, insertIndex), [cell])]);
  await vscode.workspace.applyEdit(ws);
}

async function setDefaultModelQuickPick() {
  const providers: Record<string, string[]> = {
    openai: ["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo","o4-mini"],
    anthropic: ["claude-3-7-sonnet-20250219","claude-3-opus-20240229","claude-3-sonnet-20240229","claude-3-haiku-20240307","claude-2.1"],
    google: ["gemini-2.5-pro","gemini-2.5-flash","gemini-1.5-pro","gemini-1.5-flash","gemini-1.0-pro"],
    ollama: ["deepseek-r1","qwen2.5-coder:32b-instruct","llama3:70b","llama3:8b","mixtral:8x7b"],
    grok: ["grok-3-mini-beta","grok-2-mini","grok-2","grok-1","grok-beta"],
  };
  const cfg = vscode.workspace.getConfiguration('paleopal');
  const provider = cfg.get<string>('defaultProvider', 'openai');
  const models = providers[provider] || ['auto'];
  const pick = await vscode.window.showQuickPick(models.map(m => ({ label: m })), { placeHolder: `Select model for ${provider}` });
  if (pick) {
    await cfg.update('defaultModel', pick.label, vscode.ConfigurationTarget.Global);
    vscode.window.showInformationMessage(`PaleoPal: Default model set to ${pick.label}`);
  }
}


