"""
routes/api.py
Flask Blueprint for all /api/* endpoints.

Endpoints:
  POST /api/set-key   — Accepts a Groq API key and stores it in memory.
  POST /api/analyze   — Accepts one or more files via "files" field (or legacy "file"),
                        extracts and merges their text, generates debate agents.
  POST /api/debate    — Accepts document text + agents, streams the live debate as SSE.
"""

import json as _json

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
    data    = request.get_json(silent=True) or {}
    api_key = data.get("api_key", "").strip()

    if not api_key:
        return jsonify({"status": "error", "message": "No API key provided."}), 400

    try:
        groq_client.set_api_key(api_key)
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
    Accept one or more uploaded files.
    Supports multi-file via field name "files", and legacy single-file via "file".
    Extracts text from every file, merges them, and generates debate agents.
    """
    # Collect all files — support both "files" (multi) and legacy "file" (single)
    uploaded = request.files.getlist("files")
    if not uploaded:
        uploaded = request.files.getlist("file")

    # Filter out empty slots
    uploaded = [f for f in uploaded if f and f.filename and f.filename.strip()]

    if not uploaded:
        return jsonify({"error": "No files provided. Please select at least one file."}), 400

    extracted_parts: list[str] = []
    file_names:      list[str] = []
    errors:          list[str] = []

    for f in uploaded:
        name = f.filename
        file_names.append(name)
        try:
            text = extract_text(f)
            # Wrap each file's content with a separator so the LLM sees which
            # content came from which file — critical for multi-file uploads
            header = (
                f"\n{'=' * 60}\n"
                f"FILE: {name}\n"
                f"{'=' * 60}\n"
            )
            extracted_parts.append(header + text)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
        except Exception as exc:
            errors.append(f"{name}: Unexpected error — {exc}")

    if not extracted_parts:
        detail = "; ".join(errors) if errors else "All files failed to parse."
        return jsonify({"error": detail}), 422

    # Merge all extracted texts
    merged_text = "\n\n".join(extracted_parts)

    # Prepend a file manifest for multi-file uploads so the LLM understands
    # it is working with a composite document
    if len(extracted_parts) > 1:
        manifest_lines = [f"=== MULTI-FILE UPLOAD — {len(extracted_parts)} files ==="]
        for i, name in enumerate(file_names[:len(extracted_parts)]):
            manifest_lines.append(f"  [{i + 1}] {name}")
        manifest_lines.append("")
        merged_text = "\n".join(manifest_lines) + "\n" + merged_text

    if errors:
        print(f"[/api/analyze] Partial failures: {errors}")

    try:
        result = generate_agents(merged_text)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 401
    except Exception as exc:
        return jsonify({"error": f"Agent generation failed: {exc}"}), 500

    return jsonify({
        "document_text":   merged_text,
        "document_type":   result["document_type"],
        "project_summary": result["project_summary"],
        "agents":          result["agents"],
        "file_count":      len(extracted_parts),
        "file_names":      file_names,
    })


# ---------------------------------------------------------------------------
# POST /api/debate
# ---------------------------------------------------------------------------

@api_bp.route("/debate", methods=["POST"])
def debate():
    data     = request.get_json(silent=True) or {}
    doc_text = data.get("document_text", "").strip()
    agents   = data.get("agents", [])
    rounds   = max(2, min(5, int(data.get("rounds", 3))))

    if not doc_text:
        return jsonify({"error": "document_text is required."}), 400
    if len(agents) < 2:
        return jsonify({"error": "At least two agents are required."}), 400

    def generate():
        try:
            yield from run_debate(doc_text, agents, num_rounds=rounds)
        except RuntimeError as exc:
            yield f"data: {_json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'type': 'error', 'content': f'Debate error: {exc}'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )