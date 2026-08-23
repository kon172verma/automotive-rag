from __future__ import annotations

from src.generation.context_models import AnswerContext

ANSWER_JSON_KEYS = (
    "answerability",
    "answer",
    "confidence",
    "citation_chunk_ids",
    "used_chunk_ids",
    "notes",
)


def build_system_prompt() -> str:
    return "\n".join(
        [
            "You answer vehicle-manual questions using only the provided evidence.",
            "Do not use outside automotive knowledge.",
            "Do not invent steps, warnings, or specifications.",
            "Stay specific to the provided make, model, and year.",
            "If the evidence is weak or missing, abstain.",
            "Return exactly one JSON object and no extra prose.",
            "Required keys:",
            ", ".join(ANSWER_JSON_KEYS),
            "Allowed answerability values: answerable, insufficient_evidence, not_in_manual.",
            "Allowed confidence values: low, medium, high.",
            "Only cite chunk IDs that appear in the available evidence list.",
            "If answerability is not answerable, keep the answer concise and explain the limitation.",
        ]
    )


def build_user_prompt(context: AnswerContext) -> str:
    available_chunk_ids = [chunk.chunk_id for chunk in context.evidence]
    return "\n\n".join(
        [
            "Vehicle:",
            context.request.vehicle_label,
            "Question:",
            context.request.question,
            "Retrieval mode:",
            context.retrieval_mode,
            "Selected result stage:",
            context.selected_stage,
            "Available chunk IDs:",
            ", ".join(available_chunk_ids) if available_chunk_ids else "(none)",
            "Evidence:",
            context.context_text or "(no evidence)",
            "Return JSON in this shape:",
            (
                '{'
                '"answerability":"answerable | insufficient_evidence | not_in_manual",'
                '"answer":"string",'
                '"confidence":"low | medium | high",'
                '"citation_chunk_ids":["chunk_id"],'
                '"used_chunk_ids":["chunk_id"],'
                '"notes":"string"'
                "}"
            ),
        ]
    )
