import json
import os
import time
import requests
from flask import Flask, render_template, request, Response, stream_with_context

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from rag_engine import (
    resolve_sku, vector_search, get_stock, build_prompt,
    call_llm, get_all_stock, parse_cart_items, SYSTEM_PROMPT, DATA_SOURCE,
)
from mock_data import INVENTORY

app = Flask(__name__)


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Order API endpoints
# ---------------------------------------------------------------------------

@app.route("/api/clients/search")
def api_clients_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return {"clients": []}
    try:
        from order_engine import search_clients
        clients = search_clients(q)
        return {"clients": clients}
    except RuntimeError as e:
        return {"clients": [], "error": str(e), "hint": "Set SUPABASE_SERVICE_KEY in your .env or run.ps1"}, 200
    except Exception as e:
        return {"clients": [], "error": f"{type(e).__name__}: {e}"}, 200


@app.route("/api/clients/<int:client_id>/addresses")
def api_client_addresses(client_id):
    try:
        from order_engine import get_client_addresses, _addr_label
        addrs = get_client_addresses(client_id)
        return {"addresses": [{"id": a["id"], "label": _addr_label(a)} for a in addrs]}
    except Exception as e:
        return {"addresses": [], "error": str(e)}, 200


@app.route("/api/orders", methods=["POST"])
def api_create_order():
    body = request.get_json(force=True)
    try:
        from order_engine import create_order
        order = create_order(
            client_id=body["client_id"],
            payment_mode=body["payment_mode"],
            lines=body["lines"],
            billing_address_id=body.get("billing_address_id"),
            shipping_address_id=body.get("shipping_address_id"),
            notes=body.get("notes"),
        )
        return {"ok": True, "order": order}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


# ---------------------------------------------------------------------------
# Chat / SSE stream
# ---------------------------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    message = body.get("message", "").strip()
    if not message:
        return {"error": "empty message"}, 400

    def generate():
        # Step 1: message received
        yield sse_event({
            "step": 1,
            "label": "Message Received",
            "color": "gray",
            "content": message,
        })
        time.sleep(0.3)

        # Step 2: SKU resolution
        sku_res = resolve_sku(message)
        matched = sku_res["matched_skus"]
        sku_detail = []
        for s in matched:
            stock = get_stock(s["sku_code"])
            sku_detail.append({
                "sku_code": s["sku_code"],
                "flavour": s["flavour_name"],
                "format": s["pack_format_name"],
                "stock": stock,
            })
        yield sse_event({
            "step": 2,
            "label": "SKU Resolution",
            "color": "teal",
            "content": {
                "flavour_id": sku_res["flavour_id"],
                "format_id": sku_res["format_id"],
                "qty_requested": sku_res["qty_requested"],
                "data_source": DATA_SOURCE,
                "matched_skus": sku_detail,
            },
        })
        time.sleep(0.3)

        # Step 3: vector search
        chunks = vector_search(message, top_k=3)
        yield sse_event({
            "step": 3,
            "label": "Vector Search",
            "color": "purple",
            "content": {
                "query": message,
                "results": chunks,
            },
        })
        time.sleep(0.3)

        # Step 4: stock lookup
        stock_rows = []
        for s in matched:
            sql = (
                f"SELECT stock FROM inventory WHERE sku_code = '{s['sku_code']}';"
            )
            stock_val = get_stock(s["sku_code"])
            stock_rows.append({
                "sku_code": s["sku_code"],
                "sql": sql,
                "result": stock_val,
            })
        if not stock_rows:
            stock_rows = [{"sku_code": "N/A", "sql": "No SKU resolved.", "result": "—"}]
        yield sse_event({
            "step": 4,
            "label": "Stock Lookup",
            "color": "teal",
            "content": {"lookups": stock_rows},
        })
        time.sleep(0.3)

        # Step 5: prompt assembly
        user_prompt = build_prompt(message, sku_res, chunks)
        yield sse_event({
            "step": 5,
            "label": "Prompt Assembly",
            "color": "amber",
            "content": {
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
            },
        })
        time.sleep(0.3)

        # Step 6: LLM call
        llm_result = call_llm(user_prompt)
        yield sse_event({
            "step": 6,
            "label": "LLM Response",
            "color": "green",
            "content": {
                "raw": llm_result["raw"],
                "parsed": llm_result["parsed"],
            },
        })
        time.sleep(0.3)

        # Inventory summary
        all_stock = get_all_stock()
        yield sse_event({
            "step": "inventory",
            "label": "Inventory Summary",
            "content": all_stock,
        })

        # Cart detection — parse multi-item order intent
        cart_items = parse_cart_items(message)
        if cart_items:
            subtotal = sum(i["qty"] * i["unit_price"] for i in cart_items)
            yield sse_event({
                "step": "cart",
                "items": cart_items,
                "subtotal": subtotal,
            })

        # Final: parsed reply for chat bubble
        yield sse_event({
            "step": "done",
            "reply": llm_result["parsed"].get("reply_message", ""),
            "parsed": llm_result["parsed"],
        })

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# WhatsApp Cloud API webhook
# ---------------------------------------------------------------------------

WA_TOKEN    = os.environ.get("WA_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
WA_VERIFY   = os.environ.get("WA_VERIFY_TOKEN", "icestasy_verify")


def _wa_send(to: str, text: str):
    if not WA_TOKEN or not WA_PHONE_ID:
        return
    requests.post(
        f"https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages",
        headers={"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": to,
              "type": "text", "text": {"body": text}},
        timeout=10,
    )


@app.route("/whatsapp", methods=["GET"])
@app.route("/webhook", methods=["GET"])
def whatsapp_verify():
    """Meta webhook verification handshake."""
    if (request.args.get("hub.mode") == "subscribe" and
            request.args.get("hub.verify_token") == WA_VERIFY):
        return request.args.get("hub.challenge", ""), 200
    return "Forbidden", 403


@app.route("/whatsapp", methods=["POST"])
@app.route("/webhook", methods=["POST"])
def whatsapp_message():
    """Receive incoming WhatsApp messages and reply via RAG pipeline."""
    body = request.get_json(force=True)
    try:
        entry   = body["entry"][0]["changes"][0]["value"]
        msg     = entry["messages"][0]
        from_no = msg["from"]
        text    = msg.get("text", {}).get("body", "").strip()
    except (KeyError, IndexError):
        return "ok", 200  # not a text message event

    if not text:
        return "ok", 200

    # Run through RAG pipeline synchronously
    sku_res  = resolve_sku(text)
    chunks   = vector_search(text, top_k=3)
    prompt   = build_prompt(text, sku_res, chunks)
    result   = call_llm(prompt)
    reply    = result["parsed"].get("reply_message") or result["raw"][:1000]

    _wa_send(from_no, reply)
    return "ok", 200


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
