"""
routes/api.py
Flask Blueprint for all /api/* endpoints.

Endpoints:
  POST /api/set-key   — Accepts a Groq API key and stores it for the session.
  POST /api/analyze   — Accepts a file upload, extracts text, generates agents.
  POST /api/debate    — Accepts document text + agents, streams the live debate.
"""

from flask import Blueprint, request, jsonify, Response

from core import groq_client
from core.document_parser import extract_text
from core.agent_factory import generate_agents
from core.debate_engine import run as run_debate

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# POST /api/set-key
# ---------------------------------------------------------------------------

@api_bp.route("/set-key", methods=["POST"])
def set_key():
    """
    Store a Groq API key for the duration of the server process.
    The key is never written to disk — it lives only in memory.

    Request body (JSON):
        { "api_key": "gsk_..." }

    Responses:
        200  { "status": "ok", "message": "..." }
        400  { "status": "error", "message": "..." }
    """
    data = request.get_json(silent=True) or {}
    api_key = data.get("api_key", "").strip()

    if not api_key:
        return jsonify({"status": "error", "message": "No API key provided."}), 400

    try:
        groq_client.set_api_key(api_key)
        # Ping the API to validate the key immediately
        groq_client.chat(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        return jsonify({"status": "ok", "message": "Groq API key validated and saved."})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------

@api_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    Accept a file upload, extract its text, and generate a debate agent roster.

    Request: multipart/form-data with field "file".

    Response (200):
        {
          "document_text":   str,
          "document_type":   str,
          "project_summary": str,
          "agents":          list[AgentDict]
        }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field in request."}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # Extract text
    try:
        doc_text = extract_text(file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"Unexpected extraction error: {exc}"}), 500

    # Generate agents
    try:
        result = generate_agents(doc_text)
    except RuntimeError as exc:
        # RuntimeError = missing API key
        return jsonify({"error": str(exc)}), 401
    except Exception as exc:
        return jsonify({"error": f"Agent generation failed: {exc}"}), 500

    return jsonify({
        "document_text": doc_text,
        "document_type": result["document_type"],
        "project_summary": result["project_summary"],
        "agents": result["agents"],
    })


# ---------------------------------------------------------------------------
# POST /api/debate
# ---------------------------------------------------------------------------

@api_bp.route("/debate", methods=["POST"])
def debate():
    """
    Run the multi-agent debate and stream results as Server-Sent Events (SSE).

    Request body (JSON):
        {
          "document_text": str,
          "agents":        list[AgentDict],
          "rounds":        int  (2–5, default 3)
        }

    SSE event types:
        phase   — { "type": "phase",   "content": str }
        message — { "type": "message", "message": AgentMessage }
        verdict — { "type": "verdict", "content": str }
        error   — { "type": "error",   "content": str }
        done    — { "type": "done" }
    """
    data = request.get_json(silent=True) or {}
    doc_text = data.get("document_text", "").strip()
    agents = data.get("agents", [])
    rounds = max(2, min(5, int(data.get("rounds", 3))))

    if not doc_text:
        return jsonify({"error": "document_text is required."}), 400
    if len(agents) < 2:
        return jsonify({"error": "At least two agents are required."}), 400

    def generate():
        try:
            yield from run_debate(doc_text, agents, num_rounds=rounds)
        except RuntimeError as exc:
            import json
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        except Exception as exc:
            import json
            yield f"data: {json.dumps({'type': 'error', 'content': f'Debate error: {exc}'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )