# PaleoPal Front-End

React SPA that talks to the **multi-agent** PaleoPal backend and visualises:

* real-time LangGraph execution progress (per-message progress widgets)
* workflow planning / execution, SPARQL generation & Python code generation
* clarification question/answer flow

## Major UI features

| Feature | Notes |
|---------|-------|
| Multi-agent selector | Switch between Workflow-Planner, Code-Generator, SPARQL-Generator. |
| SSE streaming | Uses `fetch(..., { mode: "cors" })` + `ReadableStream` to render progress live. |
| Per-message progress | Each user message gets its own `AgentProgressDisplay` showing node-by-node status. |
| Query & Results panes | SPARQL, generated Python code, workflow plans, execution results – all nicely formatted. |
| Clarification UX | Detects needs, presents questions, collects answers, sends back to backend. |

## Quick start

```bash
cd frontend
npm install   # installs React, axios, react-syntax-highlighter …

# dev server (proxy to backend at :8000)
npm start     # http://localhost:3000
```

The `package.json` proxy points to the FastAPI server running on `localhost:8000`.

## Build

```bash
npm run build   # production build in ./build
```

## Directory structure

```
frontend/
  src/
    components/
      ChatApp.js          – conversation list + active window
      ChatWindow.js       – main chat UI and logic
      AgentProgressDisplay.js (inlined) – node progress widget
```

## Environment variables

If you want to target a different back-end URL, edit the `proxy` field in `package.json` or create a `.env` file with `REACT_APP_API_BASE`. (The code falls back to `/` which works with the dev-proxy.)

## New in May 2025

* Per-message streaming progress
* Cross-agent context passing (SPARQL → Code, etc.)
* Removal of `localStorage` in favour of server-side conversation persistence
* Frontend no longer stores any chat state locally – refresh pulls conversation list from backend. 