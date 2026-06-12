"""AI Board of Directors — multi-model panel that answers a strategic question
from distinct executive perspectives, then synthesizes a chair recommendation.

Each director runs in parallel. If a director's API key is missing the card
renders as 'not configured' rather than failing the whole meeting.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass
class Director:
    key: str
    name: str
    title: str
    role: str
    model_label: str
    system_prompt: str
    accent: str  # css color class


DIRECTORS = [
    Director(
        key="strategist",
        name="The Strategist",
        title="Long-range positioning",
        role="Claude Opus",
        model_label="claude-opus-4-7",
        accent="strategist",
        system_prompt=(
            "You are The Strategist on an executive board of directors. Your job is to take "
            "a strategic question and answer with the long-term, structural angle — second-order "
            "effects, where the puck is heading, durable advantage, and positioning. Be concrete, "
            "be decisive, and skip filler. Open with the structural read, then 2-4 specific moves "
            "the company should make. Maximum 250 words. Use plain prose, not bullets. "
            "Never hedge with 'it depends' — pick a position and defend it."
        ),
    ),
    Director(
        key="operator",
        name="The Operator",
        title="Execution and delivery",
        role="GPT-5",
        model_label="gpt-5",
        accent="operator",
        system_prompt=(
            "You are The Operator on an executive board. Your job is to answer with the "
            "execution angle — what actually has to happen, what breaks first, what the "
            "90-day and 12-month delivery plan looks like, what capabilities you need to "
            "build. Be specific and operational, not strategic. Open with the first thing "
            "that has to be true, then walk through the execution path. Maximum 250 words. "
            "Use plain prose, not bullets. Pick a position and defend it."
        ),
    ),
    Director(
        key="cfo",
        name="The CFO",
        title="Capital and unit economics",
        role="Gemini Pro",
        model_label="gemini-2.0-pro-exp",
        accent="cfo",
        system_prompt=(
            "You are The CFO on an executive board. Your job is to answer with the financial "
            "angle — unit economics, capital required, payback, ROI, key sensitivities, and "
            "what would have to be true for the numbers to work. Be quantitative where you can. "
            "Open with the headline financial framing, then identify the 2-3 numbers that matter. "
            "Maximum 250 words. Use plain prose, not bullets. Take a position."
        ),
    ),
    Director(
        key="skeptic",
        name="The Skeptic",
        title="What we're missing",
        role="Grok",
        model_label="grok-3",
        accent="skeptic",
        system_prompt=(
            "You are The Skeptic on an executive board. Your job is to steelman the counter-position "
            "— why this might be wrong, what the room is missing, the assumptions that don't hold, "
            "and the failure modes nobody is naming. Don't be a contrarian for sport — find the "
            "specific weak points. Open with the strongest objection, then 2-3 supporting reasons. "
            "Maximum 250 words. Use plain prose, not bullets. Be sharp, not cynical."
        ),
    ),
    Director(
        key="researcher",
        name="The Researcher",
        title="Evidence and precedent",
        role="Perplexity Sonar",
        model_label="sonar-pro",
        accent="researcher",
        system_prompt=(
            "You are The Researcher on an executive board. Your job is to ground the discussion "
            "in current data and recent precedent — what does the market actually look like, what "
            "have analogous companies tried, what's the base rate for this kind of move. Cite "
            "concrete sources and numbers where possible. Open with the most relevant comparable, "
            "then key data points. Maximum 250 words. Use plain prose, not bullets."
        ),
    ),
]


CHAIR_PROMPT = (
    "You are The Chair of an executive board of directors. Five directors have just spoken "
    "on a strategic question. Your job is to synthesize:\n"
    "1. Where the board AGREES (one paragraph).\n"
    "2. Where the board DISAGREES — and what the disagreement actually means (one paragraph).\n"
    "3. THE CHAIR'S RECOMMENDATION — a clear decision, not a hedge (one paragraph).\n\n"
    "Be decisive. Do not list the directors' views — synthesize them. Maximum 280 words total. "
    "Use plain prose, not bullets. Speak with authority."
)


# ---------------- Client adapters ----------------


def _claude_call(model: str, system: str, user: str, max_tokens: int = 700) -> str:
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def _openai_call(model: str, system: str, user: str, base_url: str = None, key_env: str = "OPENAI_API_KEY", max_tokens: int = 700) -> str:
    from openai import OpenAI
    key = os.environ.get(key_env)
    if not key:
        raise RuntimeError(f"{key_env} not configured")
    client = OpenAI(api_key=key, base_url=base_url) if base_url else OpenAI(api_key=key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return completion.choices[0].message.content.strip()


def _gemini_call(model: str, system: str, user: str, max_tokens: int = 700) -> str:
    import google.generativeai as genai
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    genai.configure(api_key=key)
    gm = genai.GenerativeModel(
        model_name=model,
        system_instruction=system,
        generation_config={"max_output_tokens": max_tokens, "temperature": 0.7},
    )
    resp = gm.generate_content(user)
    return (resp.text or "").strip()


def _call_director(d: Director, question: str) -> dict:
    """Call one director. Return {status, content, ms, error}."""
    t0 = time.time()
    try:
        if d.key == "strategist":
            content = _claude_call(d.model_label, d.system_prompt, question)
        elif d.key == "operator":
            content = _openai_call(d.model_label, d.system_prompt, question)
        elif d.key == "cfo":
            content = _gemini_call(d.model_label, d.system_prompt, question)
        elif d.key == "skeptic":
            content = _openai_call(
                d.model_label, d.system_prompt, question,
                base_url="https://api.x.ai/v1", key_env="XAI_API_KEY",
            )
        elif d.key == "researcher":
            content = _openai_call(
                d.model_label, d.system_prompt, question,
                base_url="https://api.perplexity.ai", key_env="PERPLEXITY_API_KEY",
            )
        else:
            raise RuntimeError(f"unknown director {d.key}")
        return {"status": "ok", "content": content, "ms": int((time.time() - t0) * 1000), "error": None}
    except RuntimeError as e:
        return {"status": "not_configured", "content": None, "ms": 0, "error": str(e)}
    except Exception as e:
        return {"status": "error", "content": None, "ms": int((time.time() - t0) * 1000), "error": str(e)[:200]}


def convene(question: str) -> dict:
    """Run all directors in parallel, then synthesis from the Chair."""
    question = (question or "").strip()
    if not question:
        return {"question": "", "directors": [], "synthesis": None, "ms": 0}
    if len(question) > 2000:
        question = question[:2000]

    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=len(DIRECTORS)) as ex:
        futures = {ex.submit(_call_director, d, question): d for d in DIRECTORS}
        for f in as_completed(futures):
            d = futures[f]
            results[d.key] = f.result()

    directors = []
    successful_views = []
    for d in DIRECTORS:
        r = results.get(d.key, {"status": "error", "content": None, "error": "no response"})
        directors.append({
            "key": d.key,
            "name": d.name,
            "title": d.title,
            "role": d.role,
            "model_label": d.model_label,
            "accent": d.accent,
            "status": r["status"],
            "content": r.get("content"),
            "error": r.get("error"),
            "ms": r.get("ms", 0),
        })
        if r["status"] == "ok" and r.get("content"):
            successful_views.append(f"### {d.name} ({d.role}):\n{r['content']}")

    synthesis = None
    if successful_views:
        try:
            combined = "\n\n".join(successful_views)
            user_text = (
                f"The board has been convened on this question:\n\n"
                f"QUESTION:\n{question}\n\n"
                f"DIRECTORS' VIEWS:\n\n{combined}\n\n"
                f"Now synthesize as The Chair."
            )
            synthesis = {
                "status": "ok",
                "content": _claude_call("claude-opus-4-7", CHAIR_PROMPT, user_text, max_tokens=900),
            }
        except RuntimeError as e:
            synthesis = {"status": "not_configured", "error": str(e)}
        except Exception as e:
            synthesis = {"status": "error", "error": str(e)[:200]}

    return {
        "question": question,
        "directors": directors,
        "synthesis": synthesis,
        "ms": int((time.time() - t0) * 1000),
        "ok_count": sum(1 for d in directors if d["status"] == "ok"),
        "total": len(DIRECTORS),
    }


def director_status() -> list[dict]:
    """Quick view of which directors have keys configured. For status badge on the form."""
    out = []
    for d in DIRECTORS:
        if d.key == "strategist":
            configured = bool(os.environ.get("ANTHROPIC_API_KEY"))
        elif d.key == "operator":
            configured = bool(os.environ.get("OPENAI_API_KEY"))
        elif d.key == "cfo":
            configured = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        elif d.key == "skeptic":
            configured = bool(os.environ.get("XAI_API_KEY"))
        elif d.key == "researcher":
            configured = bool(os.environ.get("PERPLEXITY_API_KEY"))
        else:
            configured = False
        out.append({
            "key": d.key, "name": d.name, "role": d.role,
            "title": d.title, "accent": d.accent,
            "configured": configured,
        })
    return out
