import os
import re
import json
import math
import time
from collections import Counter

from mock_data import FLAVOURS, PACK_FORMATS, SKUS, INVENTORY, KNOWLEDGE_BASE

# ---------------------------------------------------------------------------
# Supabase loader (live data when env vars present)
# ---------------------------------------------------------------------------

def load_skus_from_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        client = create_client(url, key)
        result = (
            client.schema("production")
            .from_("skus")
            .select("sku_code, status, flavour_id, pack_format_id, flavours(name), pack_formats(name, is_sample)")
            .execute()
        )
        skus = []
        for row in result.data:
            flavour_name = row["flavours"]["name"] if row.get("flavours") else ""
            pf_name = row["pack_formats"]["name"] if row.get("pack_formats") else ""
            is_sample = row["pack_formats"]["is_sample"] if row.get("pack_formats") else False
            abbr = row["sku_code"].split("-")[0]
            suffix = row["sku_code"].split("-")[1] if len(row["sku_code"].split("-")) > 1 else ""
            skus.append({
                "sku_code": row["sku_code"],
                "flavour_id": row["flavour_id"],
                "flavour_name": flavour_name,
                "flavour_abbr": abbr,
                "pack_format_id": row["pack_format_id"],
                "pack_format_name": pf_name,
                "pack_format_suffix": suffix,
                "is_sample": is_sample,
            })
        return skus
    except Exception as e:
        print(f"[Supabase] load failed: {e}")
        return None


# Use live data if available, fall back to mock
_live_skus = load_skus_from_supabase()
ACTIVE_SKUS = _live_skus if _live_skus is not None else SKUS
DATA_SOURCE = "Supabase (live)" if _live_skus is not None else "mock data"

# ---------------------------------------------------------------------------
# TF-IDF vector search
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_tfidf(corpus: list[str]):
    tokenised = [_tokenise(d) for d in corpus]
    N = len(corpus)
    df: Counter = Counter()
    for tokens in tokenised:
        for tok in set(tokens):
            df[tok] += 1
    idf = {tok: math.log((N + 1) / (cnt + 1)) + 1 for tok, cnt in df.items()}

    def vec(tokens):
        tf = Counter(tokens)
        total = len(tokens) or 1
        return {tok: (tf[tok] / total) * idf.get(tok, 1) for tok in tf}

    vecs = [vec(tokens) for tokens in tokenised]
    return vecs, idf


def _cosine(a: dict, b: dict) -> float:
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values())) or 1
    nb = math.sqrt(sum(v * v for v in b.values())) or 1
    return dot / (na * nb)


_corpus_texts = [chunk["text"] for chunk in KNOWLEDGE_BASE]
_doc_vecs, _idf = _build_tfidf(_corpus_texts)


def vector_search(query: str, top_k: int = 3):
    q_tokens = _tokenise(query)
    tf = Counter(q_tokens)
    total = len(q_tokens) or 1
    q_vec = {tok: (tf[tok] / total) * _idf.get(tok, 1) for tok in tf}
    scores = [(_cosine(q_vec, dv), i) for i, dv in enumerate(_doc_vecs)]
    scores.sort(reverse=True)
    results = []
    for score, idx in scores[:top_k]:
        results.append({
            "chunk_id": KNOWLEDGE_BASE[idx]["id"],
            "text": KNOWLEDGE_BASE[idx]["text"],
            "score": round(score, 4),
        })
    return results


# ---------------------------------------------------------------------------
# SKU resolver — maps natural language → SKU
# ---------------------------------------------------------------------------

FLAVOUR_ALIASES = {
    "mango": 1, "hapoos": 1, "alphonso": 1, "ratnagiri": 1, "rat": 1,
    "guava": 2, "peru": 2, "amrood": 2, "amr": 2,
    "jackfruit": 3, "palapazham": 3, "pal": 3, "kathal": 3,
    "coconut": 4, "tender coconut": 4, "karikku": 4, "kar": 4, "nariyal": 4,
    "modak": 5, "ukadiche": 5, "uka": 5,
    "coffee": 6, "kaaphi": 6, "kaapi": 6, "chikkamagaluru": 6, "chi": 6,
    "mysore paak": 7, "mysore pak": 7, "mysore": 7, "mys": 7,
    "speculoos": 8, "belgian": 8, "biscuit": 8, "bel": 8,
}

FORMAT_ALIASES = {
    "4l": 1, "4 l": 1, "bulk": 1, "tub": 1, "four litre": 1, "four liter": 1,
    "12sq": 2, "12 sq": 2, "square": 2, "12 square": 2,
    "sample": 3, "50ml": 3, "samples": 3,
}


def resolve_sku(message: str):
    msg_lower = message.lower()

    # Detect flavour — try multi-word first
    flavour_id = None
    for alias in sorted(FLAVOUR_ALIASES, key=len, reverse=True):
        if alias in msg_lower:
            flavour_id = FLAVOUR_ALIASES[alias]
            break

    # Detect format
    format_id = None
    for alias in sorted(FORMAT_ALIASES, key=len, reverse=True):
        if alias in msg_lower:
            format_id = FORMAT_ALIASES[alias]
            break

    # Detect quantity
    qty_match = re.search(r"\b(\d+)\s*(?:unit|units|tub|tubs|piece|pieces|pack|packs)?\b", msg_lower)
    qty = int(qty_match.group(1)) if qty_match else 1

    matched_skus = []
    for sku in ACTIVE_SKUS:
        if flavour_id and sku["flavour_id"] != flavour_id:
            continue
        if format_id and sku["pack_format_id"] != format_id:
            continue
        matched_skus.append(sku)

    return {
        "flavour_id": flavour_id,
        "format_id": format_id,
        "qty_requested": qty,
        "matched_skus": matched_skus,
        "data_source": DATA_SOURCE,
    }


# ---------------------------------------------------------------------------
# Stock lookup
# ---------------------------------------------------------------------------

def get_stock(sku_code: str) -> int:
    return INVENTORY.get(sku_code, 0)


def get_all_stock() -> list[dict]:
    rows = []
    for sku in ACTIVE_SKUS:
        code = sku["sku_code"]
        rows.append({
            "sku_code": code,
            "flavour_name": sku["flavour_name"],
            "pack_format_name": sku["pack_format_name"],
            "stock": INVENTORY.get(code, 0),
            "is_sample": sku["is_sample"],
        })
    return rows


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an order assistant for Icestasy, a premium artisanal ice cream brand from Mumbai with flavours inspired by Indian regional ingredients and global classics.

Pack format context you must know:
- 4L Bulk = one 4-litre tub. No minimum order — a rep can order even 1 unit. For HoReCa and bulk orders.
- 12 Square = exactly 12 individual ice cream pieces per unit. Minimum order is 1 unit (12 pieces). For retail and events.
- 50ml Samples = single-serve cups only for client visits and client meets. Never for resale. If a rep asks for samples, confirm it is for a client visit before processing.

Answer only using the context provided. Reply in the same language as the rep — Hinglish is preferred and natural. Return valid JSON with keys: can_fulfill (bool), flavour_name, sku_code, pack_format, qty_requested, stock_available, reply_message.

If stock is 0 or insufficient, suggest the nearest available alternative. Never impose a minimum order quantity on 4L Bulk."""


def build_prompt(message: str, sku_resolution: dict, chunks: list[dict]) -> str:
    context_parts = [f"## Retrieved Knowledge\n"]
    for c in chunks:
        context_parts.append(f"- {c['text']}")

    sku_info = []
    for s in sku_resolution["matched_skus"]:
        stock = get_stock(s["sku_code"])
        sku_info.append(
            f"  SKU {s['sku_code']}: {s['flavour_name']} / {s['pack_format_name']} — {stock} units in stock"
        )

    if sku_info:
        context_parts.append(f"\n## Matched SKUs from database\n" + "\n".join(sku_info))

    context_parts.append(f"\n## Quantity requested\n{sku_resolution['qty_requested']} unit(s)")

    context = "\n".join(context_parts)
    user_msg = f"{context}\n\n## Rep's message\n{message}"
    return user_msg


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

MOCK_RESPONSE = {
    "can_fulfill": True,
    "flavour_name": "Demo Flavour",
    "sku_code": "DEMO-4L-0",
    "pack_format": "4L Bulk",
    "qty_requested": 1,
    "stock_available": 10,
    "reply_message": "Demo mode: ANTHROPIC_API_KEY not set. Yeh ek mock response hai! ✨",
}


def call_llm(user_prompt: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"raw": json.dumps(MOCK_RESPONSE, ensure_ascii=False), "parsed": MOCK_RESPONSE}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text.strip()
        # extract JSON if wrapped in markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        json_str = json_match.group(1) if json_match else raw
        parsed = json.loads(json_str)
        return {"raw": raw, "parsed": parsed}
    except json.JSONDecodeError:
        return {"raw": raw, "parsed": {"reply_message": raw, "can_fulfill": False,
                                        "flavour_name": "", "sku_code": "", "pack_format": "",
                                        "qty_requested": 0, "stock_available": 0}}
    except Exception as e:
        err = {"reply_message": f"LLM error: {e}", "can_fulfill": False,
               "flavour_name": "", "sku_code": "", "pack_format": "",
               "qty_requested": 0, "stock_available": 0}
        return {"raw": str(e), "parsed": err}
