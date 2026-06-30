"""
core/debate_engine.py
Orchestrates the full multi-agent adversarial debate.

Flow:
  1. Opening statements — every agent speaks once.
  2. N rounds of cross-examination — agents read recent history and rebut.
  3. Judge verdict — concise, document-specific structured summary.

Each step yields SSE strings that Flask streams directly to the browser.
"""

import json
from typing import Generator

from core.groq_client import chat, FAST_MODEL, SMART_MODEL

_HISTORY_WINDOW = 8


def run(
    doc_text: str,
    agents: list[dict],
    num_rounds: int = 3,
) -> Generator[str, None, None]:
    """
    Generator that yields SSE-formatted strings.
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
            "Give your opening statement in exactly ONE sentence."
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
            other_agents = [a["name"] for a in agents if a["id"] != agent["id"]]
            others_str   = ", ".join(other_agents)
            system_msg   = _build_system(agent, round_num=round_num,
                                         total_rounds=num_rounds, other_names=others_str)
            user_msg = (
                f"Engineering document:\n{truncated_doc}\n\n"
                f"Debate so far:\n{history_block}\n\n"
                f"Other participants: {others_str}\n\n"
                f"Round {round_num}: Respond in exactly ONE sentence. "
                "Address a specific claim made by one of the other participants by name."
            )
            reply = _call(system_msg, user_msg)
            msg   = _build_message(agent, reply, phase=f"Round {round_num}",
                                   round_num=round_num)
            history.append(f"{agent['name']}: {reply}")
            yield _sse({"type": "message", "message": msg})

    # ── 3. Judge verdict ───────────────────────────────────────────────────
    yield _sse({"type": "phase", "content": "Judge — Final Verdict"})

    verdict = _judge_verdict(truncated_doc, agents, "\n\n".join(history))
    judge_msg = _build_message(
        {"id": "judge", "name": "Judge", "color": "#2c3e50", "icon": "⚖️"},
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

def _build_system(agent: dict, round_num: int, total_rounds: int,
                  other_names: str = "") -> str:
    role     = agent.get("role", "specialist")
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
            "Raise the sharpest concern from your domain relevant to this specific project."
        )

    if round_num == 0:
        context = "This is your opening statement — state your core position in a single punchy sentence."
    else:
        context = (
            f"This is round {round_num} of {total_rounds}. "
            f"Pick one specific claim made by another participant ({other_names}) "
            "and challenge or support it directly. Mention their name naturally."
        )

    return (
        f"You are {agent['name']}, a panellist in a live engineering review debate.\n"
        f"Expertise: {skillset}\n"
        f"Role directive: {directive}\n\n"
        f"{context}\n\n"
        "Rules:\n"
        "- EXACTLY ONE SHORT sentence — hard limit, never more\n"
        "- Speak conversationally and directly\n"
        "- Reference actual content from the engineering document\n"
        "- No bullet points, no lists, no headers\n"
        "- Be sharp, decisive, and natural"
    )


def _judge_verdict(doc: str, agents: list[dict], full_debate: str) -> str:
    """
    Produce a short, document-specific, information-dense verdict.
    The score must be derived from the actual debate — no placeholder examples.
    """
    names  = ", ".join(a["name"] for a in agents)
    system = (
        "You are the Judge of an engineering review panel.\n"
        f"Panellists: {names}.\n\n"
        "Write a concise verdict using EXACTLY these headings (bold markdown, own line).\n"
        "Every line must cite a SPECIFIC finding from the debate or document — no generic filler.\n\n"
        "**VERDICT** — one sentence: viable / conditional / not viable, and the single most decisive reason why.\n\n"
        "**STRENGTHS**\n"
        "• Up to 2 bullets. Each must name a concrete engineering strength from the document.\n\n"
        "**RISKS**\n"
        "• Up to 2 bullets. Each must name a concrete risk raised during the debate.\n\n"
        "**ACTIONS**\n"
        "• Up to 3 bullets. Each = one specific, actionable next step for the engineering team.\n\n"
        "**SCORE** — A number out of 100 that YOU calculate based on the balance of evidence "
        "in THIS specific debate. Justify it in one clause.\n\n"
        "Total length: under 100 words. Zero padding. No transitional phrases. Do not truncate text, make the answer shorter if necessary, but make sure you finish the entire thing."
    )
    user = (
        f"Engineering document:\n{doc}\n\n"
        f"Full debate transcript:\n{full_debate}\n\n"
        "Deliver the verdict now. Base the score entirely on the evidence above."
    )
    return _call(system, user, model=SMART_MODEL, temperature=0.55, max_tokens=450)


def _call(
    system: str,
    user: str,
    model: str         = FAST_MODEL,
    temperature: float = 0.82,
    max_tokens: int    = 100,
) -> str:
    return chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    ).strip()


def _build_message(agent: dict, content: str, phase: str, round_num: int) -> dict:
    return {
        "agent_id":    agent["id"],
        "agent_name":  agent["name"],
        "agent_color": agent.get("color", "#888"),
        "agent_icon":  agent.get("icon",  "🤖"),
        "phase":       phase,
        "round":       round_num,
        "content":     content,
    }


def _sse(data: dict) -> str:
    """Encode a dict as a single SSE event string."""
    return f"data: {json.dumps(data)}\n\n"