# Icestasy RAG Demo

A self-contained RAG (Retrieval-Augmented Generation) demo for Icestasy's sales order system.  
Built to showcase the RAG pipeline to non-technical stakeholders.

## Features

- WhatsApp-style chat with Hinglish support
- Live RAG pipeline visualizer (6 steps, streamed via SSE)
- TF-IDF vector search over flavour + format knowledge base
- SKU resolution from natural language
- Live inventory lookup (mock or Supabase)
- Claude Haiku for order fulfilment replies
- Inventory summary bar after each query

## Setup

### 1. Install dependencies

```bash
pip install flask anthropic supabase
```

### 2. Set environment variables

```bash
export ANTHROPIC_API_KEY=your_anthropic_api_key_here
export SUPABASE_URL=https://acngdpcpxburkzqxjpbf.supabase.co
export SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjbmdkcGNweGJ1cmt6cXhqcGJmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3OTg4MjcsImV4cCI6MjA5NzM3NDgyN30.t2XuMvFL5iyGeWkERJrTFPmJdNMb48gCUcn8Z0j5bsM
```

> If `ANTHROPIC_API_KEY` is not set, the app uses a mock LLM response.  
> If `SUPABASE_URL` / `SUPABASE_KEY` are not set, the app uses built-in mock SKU data.

### 3. Run

```bash
python app.py
```

Open **http://localhost:5000**

## File structure

```
icestasy-rag-demo/
├── app.py          # Flask server + SSE streaming endpoint
├── mock_data.py    # Flavours, pack formats, SKUs, inventory, knowledge base
├── rag_engine.py   # TF-IDF search, SKU resolver, prompt builder, LLM call
├── templates/
│   └── index.html  # Split-panel UI
├── static/
│   └── style.css   # Styling
└── README.md
```

## Example queries

| Query | What it tests |
|---|---|
| `Hapoos mango 4L ka 1 unit chahiye` | Basic 4L Bulk order |
| `Kaaphi ke 12 square 3 units — restaurant client` | 12 Square format |
| `Kal client visit hai, Modak aur Speculoos ke samples chahiye` | Sample request flow |
| `Coconut ka koi bhi format de do, 20 units` | Format-agnostic query |
| `Mysore Paak 4L mein hai kya, 10 chahiye` | Stock check + order |
| `Sabse zyada stock kisme hai abhi` | Inventory overview query |
