"""
core/agent_factory.py

Two-stage agent generation:
  Stage 1 — An "Architect Agent" reads the document and invents 1–3 domain
             specialist roles that are genuinely relevant to THIS document.
             It is given explicit instruction to vary names, angles, and skills
             each call so the roster is never the same twice.
  Stage 2 — The fixed Devil's Advocate (failure) and Champion (success) agents
             are always appended after the dynamic specialists, ensuring the two
             anchor roles are consistent every time.
"""

import json
import re
import uuid

from core.groq_client import chat, SMART_MODEL


# Fixed anchor agents — always present, always identical structure
_DEVILS_ADVOCATE = {
    "id":          "agent_failure",
    "name":        "Devil's Advocate",
    "role":        "failure",
    "icon":        "⚠️",
    "color":       "#e74c3c",
    "description": "Argues this project will fail — exposes critical flaws, "
                   "overlooked risks, and technical impossibilities.",
    "skillset":    ["Risk Analysis", "Failure Mode Analysis", "Critical Review"],
}

_CHAMPION = {
    "id":          "agent_success",
    "name":        "Champion",
    "role":        "success",
    "icon":        "🏆",
    "color":       "#27ae60",
    "description": "Argues this project will succeed — defends sound engineering, "
                   "proven methods, and realistic feasibility.",
    "skillset":    ["Feasibility Analysis", "Engineering Validation", "Risk Mitigation"],
}

# Architect system prompt — drives diversity of specialist agents
_ARCHITECT_SYSTEM = """\
You are the Architect Agent: an expert engineering analyst who reads project \
documents and assembles bespoke debate panels.

Your job is to propose 1–3 DOMAIN SPECIALIST agents who will critically evaluate \
the specific engineering content of the document provided. Each specialist must \
be tailored to a distinct technical discipline that is ACTUALLY RELEVANT to this \
document — do not use generic names.

IMPORTANT: Every call should produce different specialists. Vary the discipline \
angle, the name, and the skill emphasis based on what you see in the document. \
Think creatively — consider safety, manufacturing, software, physics, economics, \
regulation, environment, human factors, supply chain, etc., and choose the most \
insightful lenses for THIS specific project.

Return ONLY a valid JSON object — no prose before or after:

{
  "document_type":   "short label for the kind of document",
  "project_summary": "2–3 sentence summary of the project",
  "specialists": [
    {
      "name":        "Unique Specialist Name (e.g. Thermal Fatigue Agent)",
      "icon":        "🔬",
      "color":       "#2980b9",
      "description": "One sentence: what angle does this agent argue from?",
      "skillset":    ["Skill A", "Skill B", "Skill C"]
    }
  ]
}

Rules:
- 1 to 3 specialists only
- Each specialist name must reflect a specific engineering discipline visible in the document
- Colors: choose distinct hex colors (NOT #e74c3c or #27ae60 — those are reserved)
- Skillset: 2–5 precise, domain-specific skills per agent
- Be creative and non-repetitive — imagine a fresh panel of experts each time
"""


def generate_agents(doc_text: str) -> dict:
    """
    Two-stage agent generation.

    Stage 1: LLM Architect proposes dynamic domain specialists from the document.
    Stage 2: Fixed Devil's Advocate and Champion are appended.

    Returns:
        dict with keys: document_type, project_summary, agents (list)
    """
    truncated = doc_text[:8000]

    response = chat(
        messages=[
            {"role": "system", "content": _ARCHITECT_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Analyze this engineering document and propose the specialist agents:\n\n"
                    + truncated
                ),
            },
        ],
        model=SMART_MODEL,
        temperature=0.85,   # Higher temperature = more varied specialists each run
        max_tokens=1400,
    )

    parsed = _extract_json(response)

    # Build specialist agents from LLM output
    specialists = []
    for i, spec in enumerate(parsed.get("specialists", [])):
        agent = {
            "id":          f"agent_specialist_{i+1}_{uuid.uuid4().hex[:6]}",
            "name":        spec.get("name",        f"Specialist {i+1}"),
            "role":        "specialist",
            "icon":        spec.get("icon",        "🔬"),
            "color":       _safe_color(spec.get("color", ""), i),
            "description": spec.get("description", ""),
            "skillset":    spec.get("skillset",    []),
        }
        specialists.append(agent)

    # Always append the two anchor agents last
    all_agents = specialists + [
        dict(_DEVILS_ADVOCATE),
        dict(_CHAMPION),
    ]

    return {
        "document_type":   parsed.get("document_type",   "Engineering Document"),
        "project_summary": parsed.get("project_summary", ""),
        "agents":          all_agents,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FALLBACK_COLORS = [
    "#8e44ad",  # Purple
    "#2980b9",  # Blue
    "#f39c12",  # Amber
    "#16a085",  # Teal
    "#d35400",  # Orange
    "#1a5276",  # Dark blue
    "#6c3483",  # Violet
]

_RESERVED = {"#e74c3c", "#27ae60"}


def _safe_color(color: str, idx: int) -> str:
    """Return color if valid and not reserved; else pick from fallback list."""
    if (
        color
        and color.startswith("#")
        and len(color) in (4, 7)
        and color.lower() not in _RESERVED
    ):
        return color
    return _FALLBACK_COLORS[idx % len(_FALLBACK_COLORS)]


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
        raise ValueError(
            f"JSON decode error: {exc}\nRaw:\n{text[:400]}"
        ) from exc