"""
core/debate_engine.py
Orchestrates the full multi-agent adversarial debate.

Flow:
  1. Opening statements — every agent speaks once without prior context.
  2. N rounds of cross-examination — every agent reads the recent history and rebuts.
  3. Judge verdict — a single high-quality model synthesises the full debate.

Each step yields Server-Sent Event (SSE) strings that Flask streams directly to
the browser so the user sees messages as they arrive.
"""

import json
from typing import Generator

from core.groq_client import chat, FAST_MODEL, SMART_MODEL

# How many history turns to feed into each agent per round (keeps prompts tight)
_HISTORY_WINDOW = 8


def run(
    doc_text: str,
    agents: list[dict],
    num_rounds: int = 3,
) -> Generator[str, None, None]:
    """
    Generator that yields SSE-formatted strings.

    Callers should use this inside a Flask Response with mimetype='text/event-stream'.
    Each yielded value is a complete SSE event ending in '\\n\\n'.
    """
    truncated_doc = doc_text[:6000]
    history: list[str] = []

    # ── 1. Opening statements ──────────────────────────────────────────────
    yield _sse({"type": "phase", "content": "Opening Statements"})

    for agent in agents:
        system_msg = _build_system(agent, round_num=0, total_rounds=num_rounds)
        user_msg = (
            f"Engineering document:\n{truncated_doc}\n\n"
            "Give your opening statement about this project."
        )
        reply = _call(system_msg, user_msg)
        msg = _build_message(agent, reply, phase="Opening", round_num=0)
        history.append(f"{agent['name']}: {reply}")
        yield _sse({"type": "message", "message": msg})

    # ── 2. Cross-examination rounds ────────────────────────────────────────
    for round_num in range(1, num_rounds + 1):
        yield _sse({"type": "phase", "content": f"Round {round_num} — Cross-Examination"})

        history_block = "\n\n".join(history[-_HISTORY_WINDOW:])

        for agent in agents:
            system_msg = _build_system(agent, round_num=round_num, total_rounds=num_rounds)
            user_msg = (
                f"Engineering document:\n{truncated_doc}\n\n"
                f"Debate so far:\n{history_block}\n\n"
                f"Your turn in round {round_num}. "
                "Directly engage with what others have argued."
            )
            reply = _call(system_msg, user_msg)
            msg = _build_message(agent, reply, phase=f"Round {round_num}", round_num=round_num)
            history.append(f"{agent['name']}: {reply}")
            yield _sse({"type": "message", "message": msg})

    # ── 3. Judge verdict ───────────────────────────────────────────────────
    yield _sse({"type": "phase", "content": "Judge — Final Verdict"})

    verdict = _judge_verdict(truncated_doc, agents, "\n\n".join(history))
    judge_msg = _build_message(
        {
            "id": "judge",
            "name": "Judge",
            "color": "#2c3e50",
            "icon": "⚖️",
        },
        verdict,
        phase="Verdict",
        round_num=num_rounds + 1,
    )
    yield _sse({"type": "message", "message": judge_msg})
    yield _sse({"type": "verdict", "content": verdict})
    yield _sse({"type": "done"})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_system(agent: dict, round_num: int, total_rounds: int) -> str:
    role = agent.get("role", "specialist")
    skillset = ", ".join(agent.get("skillset", []))

    if role == "failure":
        directive = (
            "You MUST argue that this project will FAIL. "
            "Identify critical flaws, technical impossibilities, resource constraints, "
            "and overlooked risks. Be direct and specific. Do not concede viability."
        )
    elif role == "success":
        directive = (
            "You MUST argue that this project will SUCCEED. "
            "Highlight sound engineering, proven methods, feasibility, and why critics "
            "are overstating risks. Be direct. Do not concede fatal flaws."
        )
    else:
        directive = (
            f"You are a domain specialist in {skillset}. "
            "Raise critical concerns AND acknowledge genuine strengths. "
            "Focus on your domain's specific implications for the project's viability."
        )

    context = (
        f"This is your opening statement." if round_num == 0
        else f"This is round {round_num} of {total_rounds}. "
             "Rebut specific points made by other agents — name them and challenge their logic."
    )

    return (
        f"You are {agent['name']}, a panellist in an engineering review debate.\n"
        f"Expertise: {skillset}\n"
        f"Role directive: {directive}\n\n"
        f"{context}\n\n"
        "Rules:\n"
        "- 3–5 sentences maximum per turn\n"
        "- Reference actual content from the engineering document\n"
        "- Speak in argumentative prose — no bullet points\n"
        "- Be decisive and pointed"
    )


def _judge_verdict(doc: str, agents: list[dict], full_debate: str) -> str:
    names = ", ".join(a["name"] for a in agents)
    system = (
        "You are the Judge overseeing a multi-agent engineering review panel.\n"
        f"You have heard from: {names}.\n\n"
        "Produce a structured final verdict using EXACTLY these headings "
        "(bold markdown, on their own lines):\n\n"
        "**OVERALL VERDICT**\n"
        "1–2 sentences on project viability.\n\n"
        "**KEY STRENGTHS**\n"
        "The 2–3 most compelling arguments made FOR the project.\n\n"
        "**CRITICAL CONCERNS**\n"
        "The 2–3 most important risks or flaws raised against the project.\n\n"
        "**RECOMMENDED ACTIONS**\n"
        "3–4 concrete, actionable next steps for the engineering team.\n\n"
        "**CONFIDENCE SCORE**\n"
        "A score out of 100 with a one-line rationale, e.g. '72/100 — Conditionally viable, "
        "pending materials validation.'\n\n"
        "Be decisive, balanced, and reference specific debate arguments."
    )
    user = (
        f"Engineering document:\n{doc}\n\n"
        f"Full debate transcript:\n{full_debate}\n\n"
        "Deliver the final verdict."
    )
    return _call(system, user, model=SMART_MODEL, temperature=0.35, max_tokens=900)


def _call(
    system: str,
    user: str,
    model: str = FAST_MODEL,
    temperature: float = 0.82,
    max_tokens: int = 320,
) -> str:
    return chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    ).strip()


def _build_message(agent: dict, content: str, phase: str, round_num: int) -> dict:
    return {
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "agent_color": agent.get("color", "#888"),
        "agent_icon": agent.get("icon", "🤖"),
        "phase": phase,
        "round": round_num,
        "content": content,
    }


def _sse(data: dict) -> str:
    """Encode a dict as a single SSE event string."""
    return f"data: {json.dumps(data)}\n\n"