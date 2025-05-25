# PaleoPal SPARQL Chatbot Frontend

A chat-bot style interface for interacting with the PaleoPal SPARQL generation API.

## Features

- Chat interface for natural language queries
- Support for handling clarification questions
- LLM provider selection (OpenAI, Anthropic, Ollama)
- Split-pane layout with chat on one side and results on the other
- Display of generated SPARQL queries with syntax highlighting
- Display of query execution results in a tabular format
- Copy to clipboard functionality for SPARQL queries

## Prerequisites

- Node.js (v14 or newer)
- npm or yarn
- PaleoPal Backend API running on port 8000

## Setup and Installation

1. Install the dependencies:

```bash
npm install
# or with yarn
yarn install
```

2. Start the development server:

```bash
npm start
# or with yarn
yarn start
```

3. Open [http://localhost:3000](http://localhost:3000) in your browser to use the application.

## Usage

1. Select your preferred LLM provider from the dropdown menu at the top of the chat.
2. Type your natural language query about paleoclimate data in the chat input.
3. The system will generate a SPARQL query based on your request.
4. If clarification is needed, the system will ask a question - respond to provide more context.
5. Once the SPARQL query is generated, it will be displayed on the right side along with its execution results.
6. You can copy the SPARQL query to clipboard for use in other applications.

## API Integration

The frontend connects to the PaleoPal backend API endpoints:

- `/sparql/generate` - Generates SPARQL queries from natural language
- `/sparql/execute` - Executes SPARQL queries (used indirectly via generate)

The application uses axios for API requests and handles the proper format for clarification responses.

## Development

The frontend is built with:

- React - UI library
- Axios - API requests
- react-syntax-highlighter - SPARQL query syntax highlighting

The application follows a component-based architecture with:

- `App.js` - Main application component with layout
- `ChatWindow.js` - Chat interface for queries and responses
- `ResultPane.js` - Display of SPARQL queries and results 