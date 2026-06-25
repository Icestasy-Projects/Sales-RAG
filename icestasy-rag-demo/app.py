import json
import time
from flask import Flask, render_template, request, Response, stream_with_context

from rag_engine import (
    resolve_sku, vector_search, get_stock, build_prompt,
    call_llm, get_all_stock, SYSTEM_PROMPT, DATA_SOURCE,
)
from mock_data import INVENTORY

app = Flask(__name__)


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.route("/")
def index():
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
