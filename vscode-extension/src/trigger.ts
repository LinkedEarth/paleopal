// How a cell asks PaleoPAL for something.
//
//   @paleopal <request>         a request; the backend decides which guide answers it
//   @paleopal chat <question>   opens a conversation in the chat panel
//   @agent <type> <request>     the older form, still accepted (code, sparql, workflow, chat)
//
// Under `@paleopal` only `chat` is a keyword, so "@paleopal plot lr04" is a request to plot.

export const TRIGGER = /^\s*@(paleopal|agent)\b/i;

export interface Trigger {
  agentType: string;  // code | sparql | workflow_generation | chat
  request: string;
}

export function parseTrigger(text: string): Trigger | undefined {
  const lines = text.trim().split(/\n/);
  const first = lines[0].match(/^\s*@(paleopal|agent)(?:\s+(.*))?$/i);
  if (!first) return undefined;
  const body = lines.slice(1).join('\n').trim();
  let rest = (first[2] || '').trim();
  let agentType = 'code';
  if (first[1].toLowerCase() === 'paleopal') {
    const chat = rest.match(/^chat\b\s*(.*)$/i);
    if (chat) {
      agentType = 'chat';
      rest = chat[1].trim();
    }
  } else {
    const typed = rest.match(/^(\w+)\b\s*(.*)$/);
    if (typed) {
      agentType = typed[1].toLowerCase();
      rest = typed[2].trim();
    }
    if (agentType === 'workflow') agentType = 'workflow_generation';
  }
  return { agentType, request: [rest, body].filter(Boolean).join('\n').trim() };
}
