import os
import re
import json
import math
import time
from collections import Counter

from mock_data import FLAVOURS, PACK_FORMATS, SKUS, INVENTORY, KNOWLEDGE_BASE, MOCK_PRICES

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
            .select("id, sku_code, status, flavour_id, pack_format_id, flavours(name), pack_formats(name, is_sample)")
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
                "id": row["id"],
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
    # Only return SKUs if at least a flavour or format was identified.
    # Returning all SKUs on a general query causes the first SKU to be
    # used as a false default (Ratnagiri Hapoos).
    if flavour_id is not None or format_id is not None:
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
# Multi-item cart parser
# ---------------------------------------------------------------------------

def parse_cart_items(message: str) -> list:
    """
    Parse a message into a list of cart items. Handles multi-item messages like
    '2 Ratnagiri Mango 4L and 3 Belgian 4L'.
    Returns [{"sku": {...}, "qty": int, "unit_price": float, "stock": int}, ...]
    """
    segments = re.split(r'\band\b|\baur\b|\bor\b|,|\+|\bthen\b', message, flags=re.IGNORECASE)
    items = []
    seen_skus = set()
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        res = resolve_sku(seg)
        if not res["matched_skus"]:
            continue
        qty = res["qty_requested"]
        for sku in res["matched_skus"]:
            if sku["sku_code"] in seen_skus:
                continue
            seen_skus.add(sku["sku_code"])
            price = get_sku_price(sku)
            stock = INVENTORY.get(sku["sku_code"], 0)
            items.append({
                "sku_id": sku.get("id", 0),
                "sku_code": sku["sku_code"],
                "flavour_name": sku["flavour_name"],
                "format_name": sku["pack_format_name"],
                "pack_format_id": sku["pack_format_id"],
                "qty": qty,
                "unit_price": price,
                "stock": stock,
                "can_fulfill": True,  # always accept; low stock noted in reply
            })
    return items


def get_sku_price(sku: dict) -> float:
    """Return unit price for a SKU, checking live sku_prices first then mock."""
    try:
        from order_engine import get_sku_price as _live_price
        return _live_price(sku.get("id", 0), sku["pack_format_id"])
    except Exception:
        return MOCK_PRICES.get(sku["pack_format_id"], 0.0)


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

SYSTEM_PROMPT = """You are a concise order assistant for Icestasy, a premium artisanal ice cream brand from Mumbai.

Pack formats:
- 4L Bulk: one 4-litre tub, any quantity, HoReCa/bulk.
- 12 Square: 12 pieces per unit, retail/events.
- 50ml Sample: single-serve, client visits only, never for resale.

Rules:
- ALWAYS confirm the order. Never say out of stock, never mention replenishment, never suggest alternatives unless asked.
- NEVER ask follow-up questions. One direct confirmation only.
- Reply in English. If the rep writes in Hinglish, reply in Hinglish.
- No minimum order on 4L Bulk.
- reply_message must be a short confirmation like "Got it! 2 × Ratnagiri Mango 4L confirmed."

Return ONLY valid JSON (no markdown, no extra text):
{"can_fulfill": true, "flavour_name": str, "sku_code": str, "pack_format": str, "qty_requested": int, "stock_available": int, "reply_message": str}"""


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
    "reply_message": "Demo mode: no API key set. Yeh ek mock response hai! ✨",
}


def _parse_llm_raw(raw: str) -> dict:
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    json_str = json_match.group(1) if json_match else raw
    return json.loads(json_str)


def _empty_parse(raw: str) -> dict:
    return {"reply_message": raw, "can_fulfill": False,
            "flavour_name": "", "sku_code": "", "pack_format": "",
            "qty_requested": 0, "stock_available": 0}


def call_llm(user_prompt: str) -> dict:
    groq_key = os.environ.get("GROQ_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if groq_key:
        return _call_groq(user_prompt, groq_key)
    if anthropic_key:
        return _call_anthropic(user_prompt, anthropic_key)
    return {"raw": json.dumps(MOCK_RESPONSE, ensure_ascii=False), "parsed": MOCK_RESPONSE}


def _call_groq(user_prompt: str, api_key: str) -> dict:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        msg = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = msg.choices[0].message.content.strip()
        try:
            parsed = _parse_llm_raw(raw)
        except json.JSONDecodeError:
            parsed = _empty_parse(raw)
        return {"raw": raw, "parsed": parsed}
    except Exception as e:
        err = _empty_parse(f"Groq error: {e}")
        return {"raw": str(e), "parsed": err}


def _call_anthropic(user_prompt: str, api_key: str) -> dict:
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
        try:
            parsed = _parse_llm_raw(raw)
        except json.JSONDecodeError:
            parsed = _empty_parse(raw)
        return {"raw": raw, "parsed": parsed}
    except Exception as e:
        err = _empty_parse(f"LLM error: {e}")
        return {"raw": str(e), "parsed": err}
