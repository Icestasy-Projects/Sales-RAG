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
# WhatsApp Cloud API webhook — conversational order flow
# ---------------------------------------------------------------------------

WA_TOKEN    = os.environ.get("WA_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
WA_VERIFY   = os.environ.get("WA_VERIFY_TOKEN", "icestasy_verify")

_processed_msg_ids: set = set()

# Per-user session state  {phone: {"state": str, "cart": [], "payment": str,
#                                   "client": {}, "addresses": [], "shipping_id": int}}
_wa_sessions: dict = {}

PAYMENT_OPTIONS = {"1": "advance", "2": "invoice", "3": "credit",
                   "advance": "advance", "invoice": "invoice", "credit": "credit"}


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


def _fmt_inr(n):
    return f"₹{n:,.0f}"


def _cart_summary(cart):
    lines = []
    for idx, i in enumerate(cart, 1):
        lines.append(
            f"{idx}. {i['qty']} × {i['flavour_name']} {i['format_name']} "
            f"— {_fmt_inr(i['qty'] * i['unit_price'])}"
        )
    subtotal = sum(i["qty"] * i["unit_price"] for i in cart)
    lines.append(f"\n*Subtotal: {_fmt_inr(subtotal)}*")
    return "\n".join(lines)


def _handle_wa_message(from_no: str, text: str) -> str:
    sess = _wa_sessions.get(from_no, {"state": "idle"})
    t = text.strip().lower()

    # ── CANCEL anytime ──────────────────────────────────────────────────────
    if t in ("cancel", "reset", "start over", "restart"):
        _wa_sessions.pop(from_no, None)
        return "Order cancelled. Send a new message whenever you're ready. 👍"

    state = sess.get("state", "idle")

    # ── IDLE: detect cart items ──────────────────────────────────────────────
    if state == "idle":
        cart = parse_cart_items(text)
        if not cart:
            # Fall back to RAG Q&A
            sku_res = resolve_sku(text)
            chunks  = vector_search(text, top_k=3)
            prompt  = build_prompt(text, sku_res, chunks)
            result  = call_llm(prompt)
            return result["parsed"].get("reply_message") or result["raw"][:800]

        _wa_sessions[from_no] = {"state": "cart_review", "cart": cart}
        summary = _cart_summary(cart)
        return (
            f"🛒 *Order Cart*\n\n{summary}\n\n"
            "Reply *yes* to confirm, or *cancel* to discard."
        )

    # ── CART REVIEW: waiting for yes/no ─────────────────────────────────────
    if state == "cart_review":
        if t in ("yes", "y", "confirm", "ok", "haan", "ha", "proceed"):
            sess["state"] = "payment"
            _wa_sessions[from_no] = sess
            return (
                "💳 *Payment mode?*\n\n"
                "1. Advance\n2. Invoice\n3. Credit\n\n"
                "Reply with the number or name."
            )
        if t in ("no", "n", "nahi", "nope"):
            _wa_sessions.pop(from_no, None)
            return "Order cancelled. Send a new message whenever you're ready. 👍"
        return "Please reply *yes* to confirm the order or *cancel* to discard it."

    # ── PAYMENT: waiting for payment mode ───────────────────────────────────
    if state == "payment":
        payment = PAYMENT_OPTIONS.get(t)
        if not payment:
            return "Please reply 1 (Advance), 2 (Invoice), or 3 (Credit)."
        sess["payment"] = payment
        sess["state"]   = "client_search"
        _wa_sessions[from_no] = sess
        return f"✅ Payment: *{payment.title()}*\n\nNow type the *client name* or phone number to search."

    # ── CLIENT SEARCH: waiting for search query ──────────────────────────────
    if state == "client_search":
        try:
            from order_engine import search_clients
            results = search_clients(text)
        except Exception as e:
            return f"Client search failed: {e}"
        if not results:
            return "No clients found. Try a different name or phone number."
        sess["client_options"] = results
        sess["state"] = "client_select"
        _wa_sessions[from_no] = sess
        lines = [f"{i+1}. {c['business_name']} ({c.get('primary_contact_phone','')})"
                 for i, c in enumerate(results[:5])]
        return "Found these clients:\n\n" + "\n".join(lines) + "\n\nReply with the *number* to select."

    # ── CLIENT SELECT: waiting for number ───────────────────────────────────
    if state == "client_select":
        options = sess.get("client_options", [])
        try:
            idx = int(t) - 1
            assert 0 <= idx < len(options)
        except (ValueError, AssertionError):
            return f"Please reply with a number between 1 and {len(options)}."
        client = options[idx]
        sess["client"] = client
        # Load addresses
        try:
            from order_engine import get_client_addresses, _addr_label
            addrs = get_client_addresses(client["id"])
        except Exception:
            addrs = []
        sess["addresses"] = addrs
        if addrs:
            sess["state"] = "address_select"
            _wa_sessions[from_no] = sess
            addr_lines = [f"{i+1}. {_addr_label(a)}" for i, a in enumerate(addrs)]
            return (
                f"✅ Client: *{client['business_name']}*\n\n"
                "📦 *Shipping address?*\n\n" + "\n".join(addr_lines) +
                "\n\nReply with the number."
            )
        else:
            # No addresses — skip to confirm
            sess["state"] = "confirm"
            sess["shipping_id"] = None
            _wa_sessions[from_no] = sess
            return _confirm_prompt(sess)

    # ── ADDRESS SELECT ───────────────────────────────────────────────────────
    if state == "address_select":
        addrs = sess.get("addresses", [])
        try:
            idx = int(t) - 1
            assert 0 <= idx < len(addrs)
        except (ValueError, AssertionError):
            return f"Please reply with a number between 1 and {len(addrs)}."
        sess["shipping_id"] = addrs[idx]["id"]
        sess["state"] = "confirm"
        _wa_sessions[from_no] = sess
        return _confirm_prompt(sess)

    # ── CONFIRM: final yes/no ────────────────────────────────────────────────
    if state == "confirm":
        if t in ("yes", "y", "confirm", "ok", "haan", "ha"):
            return _place_order(from_no, sess)
        if t in ("no", "n", "nahi", "nope"):
            _wa_sessions.pop(from_no, None)
            return "Order cancelled. Send a new message whenever you're ready. 👍"
        return "Reply *yes* to place the order or *cancel* to discard."

    # Fallback: reset
    _wa_sessions.pop(from_no, None)
    return "Something went wrong. Please send your order again."


def _confirm_prompt(sess):
    client  = sess["client"]
    payment = sess["payment"]
    cart    = sess["cart"]
    summary = _cart_summary(cart)
    return (
        f"📋 *Order Summary*\n\n"
        f"*Client:* {client['business_name']}\n"
        f"*Payment:* {payment.title()}\n\n"
        f"{summary}\n\n"
        "Reply *yes* to place this order or *cancel* to discard."
    )


def _place_order(from_no: str, sess: dict) -> str:
    try:
        from order_engine import create_order
        cart    = sess["cart"]
        client  = sess["client"]
        payment = sess["payment"]
        ship_id = sess.get("shipping_id")
        lines = [{
            "sku_id":        i["sku_id"],
            "sku_code":      i["sku_code"],
            "flavour_name":  i["flavour_name"],
            "format_name":   i["format_name"],
            "quantity":      i["qty"],
            "unit_price":    i["unit_price"],
            "line_discount": 0.0,
        } for i in cart]
        order = create_order(
            client_id=client["id"],
            payment_mode=payment,
            lines=lines,
            shipping_address_id=ship_id,
            billing_address_id=ship_id,
        )
        total    = order.get("total", sum(i["qty"] * i["unit_price"] for i in cart))
        order_no = order.get("order_no", "#")
        _wa_sessions.pop(from_no, None)
        item_lines = "\n".join(
            f"  • {i['qty']} × {i['flavour_name']} {i['format_name']} — {_fmt_inr(i['qty']*i['unit_price'])}"
            for i in cart
        )
        return (
            f"✅ *Order Confirmed!*\n\n"
            f"*Order No:* {order_no}\n"
            f"*Client:* {client['business_name']}\n"
            f"*Payment:* {payment.title()}\n\n"
            f"{item_lines}\n\n"
            f"*Total: {_fmt_inr(total)}*\n\n"
            "Order has been registered in the system. 🎉"
        )
    except Exception as e:
        _wa_sessions.pop(from_no, None)
        return f"❌ Order failed: {e}"


@app.route("/whatsapp", methods=["GET"])
@app.route("/webhook", methods=["GET"])
def whatsapp_verify():
    if (request.args.get("hub.mode") == "subscribe" and
            request.args.get("hub.verify_token") == WA_VERIFY):
        return request.args.get("hub.challenge", ""), 200
    return "Forbidden", 403


@app.route("/whatsapp", methods=["POST"])
@app.route("/webhook", methods=["POST"])
def whatsapp_message():
    body = request.get_json(force=True)
    try:
        entry   = body["entry"][0]["changes"][0]["value"]
        msg     = entry["messages"][0]
        msg_id  = msg.get("id", "")
        from_no = msg["from"]
        text    = msg.get("text", {}).get("body", "").strip()
    except (KeyError, IndexError):
        return "ok", 200

    if not text:
        return "ok", 200

    if msg_id and msg_id in _processed_msg_ids:
        return "ok", 200
    if msg_id:
        _processed_msg_ids.add(msg_id)
        if len(_processed_msg_ids) > 500:
            _processed_msg_ids.clear()

    reply = _handle_wa_message(from_no, text)
    _wa_send(from_no, reply)
    return "ok", 200


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
