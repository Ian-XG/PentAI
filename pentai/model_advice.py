"""Model guidance for offensive-security work. Safety-tuned consumer models
(gpt-oss, guard models) refuse legitimate authorized pentest/education tasks;
this steers the operator toward low-refusal, tool-capable models that handle the
domain without spurious "I can't help with that". Recommendations favor local
models (Ollama) so the work stays on the operator's machine."""

# Curated for authorized ethical-hacking use: low spurious-refusal AND good
# tool-calling (PentAI needs the model to actually call run_command). Local
# unless noted. (name-as-you'd-pull-it, one-line reason)
RECOMMENDED: list[tuple[str, str]] = [
    ("hermes3", "Nous Hermes 3 - neutrally aligned, excellent tool-calling; the natural fit for PentAI"),
    ("dolphin-mixtral", "uncensored Mixtral fine-tune - strong, low-refusal, handles tools"),
    ("dolphin3", "uncensored Llama 3.2 - smaller and fast, good for laptops"),
    ("whiterabbitneo", "purpose-built for offensive/defensive security (search Ollama for a tagged build)"),
    ("claude (via /setup)", "best reasoning; handles the authorized-hacking frame without refusing - needs an API key"),
]

# substrings that mark a model as prone to refusing legitimate security work
_OVER_REFUSERS = ("gpt-oss", "llama-guard", "llamaguard", "llama_guard",
                  "shieldgemma", "guardrail", "-guard")

def is_over_refuser(model: str) -> bool:
    m = (model or "").lower()
    return any(sig in m for sig in _OVER_REFUSERS)

def over_refusal_tip(model: str) -> str | None:
    if not is_over_refuser(model):
        return None
    flagship = RECOMMENDED[0][0]
    return (f"'{model}' tends to refuse legitimate offensive-security work. For "
            f"authorized pentest/CTF/lab use, switch with /model <name> to a "
            f"low-refusal model - e.g. {flagship}, dolphin-mixtral, or Claude. "
            f"See /models for the full list.")

def recommended_text() -> str:
    lines = ["recommended models for authorized ethical-hacking work "
             "(low refusal + tool-calling):"]
    for name, note in RECOMMENDED:
        lines.append(f"  {name:<22} {note}")
    lines.append("switch with /model <name>  (local models: pull first with `ollama pull <name>`)")
    return "\n".join(lines)
