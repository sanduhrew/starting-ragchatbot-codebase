# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A full-stack RAG (Retrieval-Augmented Generation) chatbot that answers questions about course materials using Anthropic Claude, ChromaDB, and FastAPI.

## Commands

### Run the app
```bash
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```
App serves at http://localhost:8000, API docs at http://localhost:8000/docs.

### Install dependencies
```bash
uv sync
```

### Environment setup
Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.

## Development Rules

- **Always use `uv` to run Python** — use `uv run` to execute scripts and `uv sync` for dependencies. Never use `pip install` or bare `python`.

## Architecture

The system follows a pipeline: **Frontend → FastAPI → RAG Orchestrator → Claude API (with tool calling) → Vector Store → Response**.

### Backend (`backend/`)

- **app.py** — FastAPI entry point. Two endpoints: `POST /api/query` and `GET /api/courses`. Serves the frontend as static files. On startup, loads docs from `../docs` via `rag_system.add_course_folder()`.
- **rag_system.py** — Central orchestrator. Wires together all components. `query()` fetches session history, calls Claude with tools, collects sources, saves the exchange.
- **ai_generator.py** — Anthropic Claude wrapper. Makes up to 2 API calls per query: first with tools enabled (Claude decides whether to search), second with tool results to synthesize the answer. System prompt is a static class variable.
- **search_tools.py** — Tool-calling abstraction. `CourseSearchTool` implements the `Tool` ABC. `ToolManager` registers tools and dispatches execution by name. Sources are tracked on the tool instance (`last_sources`) and reset after each query.
- **vector_store.py** — ChromaDB integration with two collections: `course_catalog` (course metadata, used for semantic course name resolution) and `course_content` (chunked text). Search flow: resolve course name → build filter → query embeddings.
- **document_processor.py** — Reads `.txt/.pdf/.docx` files. Parses structured headers (`Course Title:`, `Course Instructor:`, `Course Link:`), splits by `Lesson N:` markers, then chunks text using sentence-aware splitting (800 char chunks, 100 char overlap).
- **session_manager.py** — In-memory session store. Conversation history is formatted as a plain string and appended to the system prompt (not as separate messages).
- **models.py** — Pydantic models: `Course`, `Lesson`, `CourseChunk`.
- **config.py** — Reads `.env` via python-dotenv. All settings are in a single `Config` dataclass.

### Frontend (`frontend/`)

Vanilla HTML/CSS/JS served as static files by FastAPI. No build step. Uses `marked.js` for markdown rendering. Session ID is managed client-side and sent with each query.

### Course Documents (`docs/`)

Plain text files with a specific format: 3-line header (title, link, instructor) followed by `Lesson N: Title` delimited sections. Loaded and indexed into ChromaDB on app startup; existing courses are skipped.

## Key Design Decisions

- **Tool-calling pattern**: Claude decides whether to search via Anthropic's native tool_use mechanism rather than always retrieving context. This means general questions skip the vector store entirely.
- **Two-collection vector store**: Course names are resolved semantically (partial match like "MCP" finds the full title) via the `course_catalog` collection before filtering `course_content`.
- **Conversation history as string**: Session history is concatenated into the system prompt, not passed as structured messages. Max 2 exchanges retained.
- **All imports are relative**: Backend files import each other directly (e.g., `from models import Course`), so the working directory must be `backend/` when running.
