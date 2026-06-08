"""
NexusAI — Production Flask Backend (lightweight edition)
API surface is 100 % compatible with the original heavy version.
Runs on Render free tier (<300 MB RAM, <5 s startup).
"""

import os
import logging
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from chatbot import get_engine, FALLBACK_ANSWER

# ── Bootstrap ──────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# ── CORS — explicit allowed origins ───────────────────────
_DEFAULT_ORIGINS = ",".join([
    "https://kawin13.github.io",
    "http://localhost:5000",
    "http://localhost:3000",
    "http://127.0.0.1:5000",
])
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]
CORS(
    app,
    origins=_CORS_ORIGINS,
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"],
)
CORS(app, origins=os.getenv("CORS_ORIGINS", "*"))

# ── Config ─────────────────────────────────────────────────
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY", "")
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "40"))
PORT                 = int(os.getenv("PORT", "5000"))
DEBUG                = os.getenv("DEBUG", "false").lower() == "true"

# ── Eager engine init (avoid cold-start latency on first request) ──
logger.info("Initialising NexusAI FAQ Engine …")
try:
    engine = get_engine()
    logger.info(f"Engine ready — {engine.stats()['total_faqs']} FAQs indexed")
except Exception as exc:
    logger.critical(f"Failed to initialise FAQ engine: {exc}")
    raise


# ── Optional AI fallbacks ──────────────────────────────────

def _call_gemini(question: str) -> str | None:
    if not GEMINI_API_KEY:
        return None
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{
                "parts": [{
                    "text": (
                        "You are NexusAI, a concise technical assistant specialising in "
                        "software engineering, AI/ML, cloud computing, DevOps, and programming.\n\n"
                        f"Question: {question}"
                    )
                }]
            }]
        }
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.warning(f"Gemini fallback failed: {exc}")
        return None


def _call_openai(question: str) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are NexusAI, a concise technical assistant specialising in "
                        "software engineering, AI/ML, cloud computing, DevOps, and programming."
                    ),
                },
                {"role": "user", "content": question},
            ],
            "max_tokens": 400,
            "temperature": 0.7,
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers, json=payload, timeout=12,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning(f"OpenAI fallback failed: {exc}")
        return None


def _ai_fallback(question: str) -> dict | None:
    answer = _call_gemini(question) or _call_openai(question)
    if answer:
        return {
            "answer":     answer.strip(),
            "topic":      "AI Generated",
            "confidence": 75,
            "source":     "ai_generated",
            "question":   question,
        }
    return None


# ── Routes ─────────────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    """Ensure CORS headers are present on every response, including errors."""
    origin = request.headers.get("Origin", "")
    if origin in _CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"]  = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Vary"] = "Origin"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def handle_preflight(path):
    """Respond to CORS pre-flight requests."""
    return "", 204

@app.route("/", methods=["GET"])
def index():
    s = engine.stats()
    return jsonify({
        "name":            "NexusAI FAQ Chatbot API",
        "version":         "2.3.0",
        "version":         "2.2.0",
        "status":          "online",
        "faqs":            s["total_faqs"],
        "semantic_search": s["semantic_enabled"],
        "endpoints": {
            "POST /chat":   "Main chat endpoint",
            "POST /search": "Search FAQs",
            "GET  /topics": "List all topics",
            "GET  /faqs":   "Paginated FAQ list",
            "GET  /stats":  "Engine statistics",
            "GET  /health": "Health check",
        },
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":    "ok",
        "faqs":      len(engine.faqs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/chat", methods=["POST"])
def chat():
    t0 = time.perf_counter()

    body     = request.get_json(silent=True) or {}
    question = (body.get("message") or body.get("question") or "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400
    if len(question) > 1000:
        return jsonify({"error": "Question too long (max 1000 characters)"}), 400

    logger.info(f"[CHAT] {question[:80]!r}")

    def elapsed_ms():
        return round((time.perf_counter() - t0) * 1000)

    # 1 ── FAQ search
    results = engine.search(question, top_k=3)
    best    = results[0] if results else None

    if best and best["confidence"] >= CONFIDENCE_THRESHOLD:
        return jsonify({
            "answer":       best["answer"],
            "question":     best["question"],
            "topic":        best["topic"],
            "confidence":   best["confidence"],
            "source":       "faq_database",
            "alternatives": results[1:] if len(results) > 1 else [],
            "response_ms":  elapsed_ms(),
        })

    # 2 ── Optional AI fallback (Gemini / OpenAI)
    ai_result = _ai_fallback(question)
    if ai_result:
        return jsonify({**ai_result, "response_ms": elapsed_ms()})

    # 3 ── Graceful no-match (never returns empty)
    # If we have any results above a very low bar, surface the best one anyway
    if results and results[0]["confidence"] >= 15:
        best_guess = results[0]
        return jsonify({
            "answer":      best_guess["answer"],
            "question":    best_guess["question"],
            "topic":       best_guess["topic"],
            "confidence":  best_guess["confidence"],
            "source":      "low_confidence_match",
            "alternatives": results[1:],
            "response_ms": elapsed_ms(),
        })

    suggestions = [
        {
            "answer":     r["answer"],
            "question":   r["question"],
            "topic":      r["topic"],
            "confidence": r["confidence"],
        }
        for r in results[:2]
    ] if results else []

    return jsonify({
        "answer":      FALLBACK_ANSWER,
        "topic":       "Unknown",
        "confidence":  0,
        "source":      "no_match",
        "suggestions": suggestions,
        "response_ms": elapsed_ms(),
    })


@app.route("/search", methods=["POST"])
def search():
    body  = request.get_json(silent=True) or {}
    query = (body.get("query") or body.get("q") or "").strip()
    top_k = min(int(body.get("top_k", 5)), 20)

    if not query:
        return jsonify({"error": "No query provided"}), 400

    results = engine.search(query, top_k=top_k)
    return jsonify({"query": query, "results": results, "count": len(results)})


@app.route("/topics", methods=["GET"])
def topics():
    topic_list = engine.get_topics()
    counts     = engine.stats()["topics"]
    return jsonify({
        "topics": [{"name": t, "count": counts.get(t, 0)} for t in topic_list],
        "total":  len(topic_list),
    })


@app.route("/faqs", methods=["GET"])
def faqs():
    topic    = request.args.get("topic", "").strip()
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(50, int(request.args.get("per_page", 20)))

    items    = engine.get_faqs_by_topic(topic) if topic else engine.faqs
    total    = len(items)
    start    = (page - 1) * per_page
    page_items = items[start: start + per_page]

    return jsonify({
        "faqs":     page_items,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page,
    })


@app.route("/stats", methods=["GET"])
def stats():
    s = engine.stats()
    return jsonify({
        **s,
        "ai_fallback": {
            "gemini": bool(GEMINI_API_KEY),
            "openai": bool(OPENAI_API_KEY),
        },
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Error handlers ─────────────────────────────────────────

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad request", "detail": str(e)}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"error": "Internal server error"}), 500


# ── Entry point ────────────────────────────────────────────

if __name__ == "__main__":
    s = engine.stats()
    print(f"""
╔══════════════════════════════════════════╗
║         NexusAI FAQ Chatbot v2.2         ║
║   http://localhost:{PORT:<5}                  ║
╠══════════════════════════════════════════╣
║  FAQs:     {s['total_faqs']:<6}                       ║
║  Semantic: {str(s['semantic_enabled']):<6}                       ║
║  Gemini:   {str(bool(GEMINI_API_KEY)):<6}                       ║
║  OpenAI:   {str(bool(OPENAI_API_KEY)):<6}                       ║
╚══════════════════════════════════════════╝
""")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
