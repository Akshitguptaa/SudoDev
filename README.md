# SudoDev

![Next.js](https://img.shields.io/badge/Next.js_16-black?logo=next.js) ![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi) ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white) ![AI Agent](https://img.shields.io/badge/AI_Agent-8A2BE2) ![License](https://img.shields.io/badge/License-Apache_2.0-blue)

> **SudoDev** is an autonomous AI Software Engineer capable of solving complex coding tasks, refactoring code, and debugging issues. It combines a recursive **Feedback Loop** for self-correction with a **Smart Context Search** engine to operate effectively on large codebases.

---

## System Architecture

The system uses a decoupled architecture with a React-based frontend and a Python agentic backend.

```mermaid
graph TD
    User((User)) -->|HTTPS| UI["Client Layer<br/>(Next.js 16 / React 19)"]
    
    subgraph "Server Side (FastAPI)"
        UI -->|POST /api/run| API[API Gateway]
        UI -->|GET /api/status| API
        API -->|Async| BG[Background Worker]
        BG -->|Start| Agent[("Improved Agent")]
    end
    
    subgraph "Agent Logic"
        Agent -->|1. Analyze| Context["Context Search (AST)"]
        Context -->|AST Parse| FileSys
        
        Agent -->|2. Reproduce| Repro["Reproduction Script"]
        Repro -->|Run| Sandbox
        
        Agent -->|3. Loop| Feedback{"Feedback Loop"}
        Feedback -->|Fix| CodeGen["LLM Code Gen"]
        CodeGen -->|Apply| Sandbox
        
        Feedback -->|Verify| Test[Test Runner]
        Test -->|Result| Feedback
    end
    
    subgraph "Runtime Sandbox (Docker)"
        Sandbox[Containerized Env]
        FileSys[File System]
    end
    
    subgraph "External Intelligence"
        Context -->|Query| Groq["Groq API (Llama 3.3)"]
        CodeGen -->|Prompt| Groq
        Repro -->|Prompt| Groq
    end
```

### Key Design Decisions
-   **Recursive Feedback Loop**: The agent doesn't just guess; it writes code, runs it, captures errors, and self-corrects iteratively (up to 3 attempts).
-   **Smart Context Search**: Instead of relying solely on vector databases, SudoDev uses AST (Abstract Syntax Tree) parsing combined with LLM-based relevance scoring to identify critical code sections without overhead.
-   **Sandboxed Execution**: Every agent run happens inside an isolated Docker container, ensuring safety and reproducibility.

## Key Features

-   **Dual Mode Operation**:
    -   **SWE-bench Mode**: Solves standard benchmark issues for evaluation.
    -   **GitHub Mode**: Connects to any public repository to fix reported issues.
-   **Deep Debugging**: Auto-generates reproduction scripts to confirm bugs before fixing them.
-   **Context-Aware**: Intelligently extracts only relevant classes and functions from large files to fit within LLM context windows.
-   **Live Observation**: Real-time streaming of logs, terminal outputs, and agent thoughts to the UI.

## Tech Stack

-   **Frontend**: Next.js 16 (App Router), React 19, Tailwind CSS
-   **Backend API**: Python, FastAPI
-   **AI Model**: Groq (Llama 3.3)
-   **Code Analysis**: Python AST
-   **Runtime**: Docker
-   **Styling**: Tailwind CSS 

## TO-DO

- [x] Bench Mode testing
- [x] Github pipeline
- [x] Docker Sandbox
- [x] AST context
- [x] Recursive feedback
- [ ] IDE-integration
- [ ] Auto PRs

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
Apache-2.0 License. See [LICENSE](LICENSE) for more information.1

