"""
core/agent_factory.py
Generates the initial roster of debate agents from a document using the Groq LLM.
The factory always produces a Devil's Advocate (failure) and a Champion (success)
agent, plus 1–3 domain specialists derived from the actual engineering content.
"""

import json
import re

from core.groq_client import chat, SMART_MODEL


# Fallback colours for domain agents (cycles if more than 5)
_DOMAIN_COLORS = [
    "#8e44ad",  # Purple
    "#2980b9",  # Blue
    "#f39c12",  # Amber
    "#16a085",  # Teal
    "#d35400",  # Orange
]

_SYSTEM_PROMPT = """You are an expert engineering document analyzer.
Read the supplied engineering document and propose a debate panel of 3–5 AI agents
who will critically evaluate this project.

The panel MUST always include:
1. "Devil's Advocate" — role: "failure" — argues the project WILL FAIL
2. "Champion"         — role: "success" — argues the project WILL SUCCEED
3. 1–3 domain specialists — role: "specialist" — named after actual engineering
   disciplines present in the document (e.g. "Materials Integrity Agent",
   "Thermodynamics Agent", "Software Architecture Agent")

Return ONLY a valid JSON object with this exact schema — no prose before or after:

{
  "document_type":   "short description of the document kind",
  "project_summary": "2–3 sentence project summary",
  "agents": [
    {
      "id":          "agent_1",
      "name":        "Devil's Advocate",
      "role":        "failure",
      "icon":        "⚠️",
      "color":       "#e74c3c",
      "description": "One sentence describing what this agent argues.",
      "skillset":    ["Risk Analysis", "Failure Mode Analysis"]
    }
  ]
}

Rules:
- Devil's Advocate must have color "#e74c3c"
- Champion must have color "#27ae60"
- Domain agents: choose an appropriate emoji icon and a hex color
- Skillset: 2–5 short, domain-specific skill strings per agent
- IDs: agent_1, agent_2, agent_3, …
"""


def generate_agents(doc_text: str) -> dict:
    """
    Call the LLM to analyse the document and return the structured response.

    Returns a dict with keys: document_type, project_summary, agents (list).
    Raises ValueError if parsing fails.
    """
    truncated = doc_text[:8000]  # Stay well within context window

    response = chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Analyze this engineering document and propose debate agents:\n\n"
                    + truncated
                ),
            },
        ],
        model=SMART_MODEL,
        temperature=0.5,
        max_tokens=1600,
    )

    parsed = _extract_json(response)
    agents = parsed.get("agents", [])

    # Patch domain agent colors if they are missing or identical to the defaults
    domain_idx = 0
    for agent in agents:
        if agent.get("role") not in ("failure", "success"):
            if not agent.get("color") or agent["color"] in ("#e74c3c", "#27ae60"):
                agent["color"] = _DOMAIN_COLORS[domain_idx % len(_DOMAIN_COLORS)]
                domain_idx += 1

    return {
        "document_type": parsed.get("document_type", "Engineering Document"),
        "project_summary": parsed.get("project_summary", ""),
        "agents": agents,
    }


def _extract_json(text: str) -> dict:
    """Pull the first top-level JSON object from an LLM response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(
            "LLM did not return a JSON object. Raw response:\n" + text[:400]
        )
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON decode error: {exc}\nRaw:\n{text[:400]}") from exc