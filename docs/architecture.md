# Architecture — NED Prospectus Assistant

## System context

The assistant is a retrieval-augmented generation (RAG) system. User questions are answered only from chunks that were extracted from ingested prospectus PDFs. The language model is a constrained formatter of retrieved evidence, not a source of university policy.

```mermaid
flowchart TB
    subgraph Client["Browser"]
        UI["Next.js chat workspace"]
    end

    subgraph API["FastAPI application"]
        Routes["HTTP routes\n/health /documents /chat /retrieval/debug"]
        Ingest["IngestionService"]
        Extract["ExtractionService"]
        Chunk["ChunkingService"]
        Embed["EmbeddingService"]
        Retrieve["RetrievalService"]
        Answer["AnswerService"]
        Registry["DocumentRegistry"]
        Store["ChromaVectorStore"]
        Conv["ConversationStore\ncontinuity only"]
        Prompt["grounded_answer.txt"]
    end

    subgraph Providers["Provider adapters"]
        EmbP["EmbeddingProvider\nLocal MiniLM | Fake"]
        GenP["GenerationProvider\nGroq | Fake"]
    end

    subgraph Data["Local data"]
        PDF["data/documents/*.pdf"]
        Chroma["data/chroma persistent store"]
        RegFile["document_registry.json"]
    end

    subgraph External["External services"]
        Groq["Groq API (generation only)"]
    end

    UI -->|"JSON over HTTP"| Routes
    Routes --> Ingest
    Routes --> Retrieve
    Routes --> Answer
    Ingest --> Extract
    Extract --> Chunk
    Chunk --> Embed
    Embed --> EmbP
    Embed --> Store
    Ingest --> Registry
    Retrieve --> Embed
    Retrieve --> Store
    Answer --> Retrieve
    Answer --> GenP
    Answer --> Prompt
    Answer --> Conv
    Store --> Chroma
    Registry --> RegFile
    Ingest --> PDF
    GenP -.-> Groq
```

## Ingestion pipeline

```mermaid
flowchart LR
    A["PDF upload / CLI"] --> B["Validate type, size, path"]
    B --> C["SHA-256 hash"]
    C --> D{"Hash already indexed?"}
    D -->|yes, replace=false| E["Reject duplicate"]
    D -->|yes, replace=true| F["Delete prior chunks"]
    D -->|no| G["PyMuPDF page extract"]
    F --> G
    G --> H["Flag empty / image-only pages"]
    H --> I["Paragraph-aware chunking + overlap"]
    I --> J["Attach page and document metadata"]
    J --> K["Embed chunks"]
    K --> L["Persist in Chroma + registry"]
```

## Query pipeline

```mermaid
flowchart TD
    Q["User question"] --> V["Validate length and content"]
    V --> X["Expand acronyms and fee/department synonyms"]
    X --> E["Embed query"]
    E --> R["Chroma cosine query, candidate pool, optional document filter"]
    R --> L["Lexical rerank, then pack same-page and chapter-neighbor chunks"]
    R --> T{"Any chunk within distance threshold?"}
    T -->|no| I["Return insufficient_evidence\nno LLM call"]
    T -->|yes| P["Wrap passages as untrusted data"]
    P --> G["Groq JSON generation"]
    G --> C["Validate citation IDs against retrieved chunks"]
    C --> S["Structured ChatResponse"]
```

## Trust boundaries

```mermaid
flowchart TB
    User["User text"] -->|untrusted| Chat
    PDF["Prospectus text"] -->|untrusted| Passages
    Chat["Chat endpoint"] --> Retrieve
    Passages["Delimited retrieved passages"] --> Prompt
    Sys["System prompt + schema"] -->|trusted| Model
    Model["Generation provider"] --> Validate["Citation and schema validation"]
    Validate --> Browser["Sanitized JSON to UI"]
    Keys["GROQ_API_KEY / ADMIN_API_KEY"] -.->|server only| API["FastAPI process"]
```

## Component responsibilities

| Component | Responsibility | Must not do |
| --- | --- | --- |
| `ExtractionService` | Page text, page numbers, OCR flags | Interpret content |
| `ChunkingService` | Size/overlap, paragraph boundaries | Call an LLM |
| `EmbeddingService` | Batch embed via provider | Store or retrieve |
| `ChromaVectorStore` | Persist and query vectors | Generate answers |
| `RetrievalService` | Top-k, threshold, filters, debug payload | Call the generator |
| `AnswerService` | Prompt assembly, JSON parse, citation check, refusal | Use chat history as evidence |
| `DocumentRegistry` | Hash, metadata, duplicate policy | Embed text |
| Frontend | Display answers and sources | Invent answers or hold API keys |

## Runtime configuration (summary)

See `.env.example` for the full list. The important RAG knobs:

- `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS`
- `RETRIEVAL_TOP_K`
- `RETRIEVAL_MAX_DISTANCE` (cosine distance; lower is closer)
- `EMBEDDING_PROVIDER` / `GENERATION_PROVIDER`
- `EMBEDDING_MODEL` / `GROQ_MODEL`
