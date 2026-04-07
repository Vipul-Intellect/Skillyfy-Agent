import json
import threading

from google import genai
from google.genai import types

from config.settings import settings
from database.firestore_client import get_session, save_session
from utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_hint_usage_memory = {}
_hint_lock = threading.Lock()
_active_practice_memory = {}
_practice_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _persist_session_async(session_id: str, data: dict):
    def _persist():
        try:
            save_session(session_id, data)
        except Exception as e:
            logger.warning(f"Background save_session failed for {session_id}: {e}")

    threading.Thread(target=_persist, daemon=True).start()


def generate_practice_set(
    session_id: str,
    skill: str,
    topic: str,
    level: str,
    language: str = "python",
) -> dict:
    """
    Generate a practice pack with 3 questions and 1 mini-lab.
    """
    try:
        schema = {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "expected_focus": {"type": "string"},
                            "evaluation_guide": {"type": "string"},
                        },
                        "required": ["type", "question", "expected_focus", "evaluation_guide"],
                    },
                },
                "mini_lab": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "prompt": {"type": "string"},
                        "starter_code": {"type": "string"},
                        "success_criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                    },
                    "required": ["title", "prompt", "starter_code", "success_criteria"],
                },
                "practice_summary": {"type": "string"},
            },
            "required": ["questions", "mini_lab", "practice_summary"],
        }

        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""Create a practice pack for a {level} learner.

Skill: {skill}
Topic: {topic}
Language: {language}

Return:
- exactly 3 strong learning questions
- exactly 1 mini-lab

Rules:
- This is not a LeetCode-style assessment.
- Focus on practical understanding, debugging, and applied use.
- Questions should be concise and high-quality.
- The mini-lab should be 5-15 minutes of work.
- Starter code must be short and runnable.
- Keep the difficulty aligned to the learner level.""",
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=settings.API_TIMEOUT * 1000),
            ),
        )

        result = response.parsed or {}
        if not result.get("questions") or not result.get("mini_lab"):
            raise ValueError("Practice generator returned incomplete output")

        payload = {
            "session_id": session_id,
            "skill": skill,
            "topic": topic,
            "level": level,
            "language": language,
            "questions": result["questions"][:4],
            "mini_lab": result["mini_lab"],
            "practice_summary": result.get("practice_summary", "").strip(),
        }

        with _practice_lock:
            _active_practice_memory[session_id] = payload

        _persist_session_async(
            session_id,
            {
                "active_practice": {
                    "skill": skill,
                    "topic": topic,
                    "level": level,
                    "language": language,
                    "questions": payload["questions"],
                    "mini_lab": payload["mini_lab"],
                }
            },
        )

        logger.info(f"Generated practice pack for {session_id}: {skill}/{topic}")
        return _public_practice_payload(payload)
    except Exception as e:
        logger.error(f"Error generating practice set: {e}")
        return {
            "error": str(e),
            "questions": [],
            "mini_lab": {},
        }


def _public_practice_payload(payload: dict) -> dict:
    public_questions = []
    for question in payload.get("questions", []):
        public_questions.append(
            {
                "type": question.get("type"),
                "question": question.get("question"),
                "options": question.get("options", []),
                "expected_focus": question.get("expected_focus"),
            }
        )

    return {
        "session_id": payload.get("session_id"),
        "skill": payload.get("skill"),
        "topic": payload.get("topic"),
        "level": payload.get("level"),
        "language": payload.get("language"),
        "questions": public_questions,
        "mini_lab": payload.get("mini_lab", {}),
        "practice_summary": payload.get("practice_summary", ""),
    }


def evaluate_practice_answers(
    session_id: str,
    skill: str,
    topic: str,
    answers: list,
) -> dict:
    """
    Evaluate user answers against the active practice pack for the topic.
    """
    try:
        with _practice_lock:
            active_practice = dict(_active_practice_memory.get(session_id, {}))

        if not active_practice:
            session = get_session(session_id) or {}
            active_practice = session.get("active_practice") or {}

        stored_questions = active_practice.get("questions") or []

        if not stored_questions:
            return {"error": "No active practice found for this session"}

        relevant_questions = stored_questions[:len(answers)] if answers else stored_questions
        if not answers:
            return {"error": "No answers provided"}

        rubric_input = []
        for question, answer in zip(relevant_questions, answers):
            rubric_input.append(
                {
                    "question": question.get("question", ""),
                    "type": question.get("type", ""),
                    "expected_focus": question.get("expected_focus", ""),
                    "evaluation_guide": question.get("evaluation_guide", ""),
                    "answer": answer,
                }
            )

        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "acceptable": {"type": "boolean"},
                            "score": {"type": "integer"},
                            "feedback": {"type": "string"},
                        },
                        "required": ["question", "acceptable", "score", "feedback"],
                    },
                },
                "overall_feedback": {"type": "string"},
                "recommended_next_step": {"type": "string"},
            },
            "required": ["items", "overall_feedback", "recommended_next_step"],
        }

        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""Evaluate the learner's answers for a {skill} / {topic} practice pack.

Use the evaluation guide for each item.
Mark answers acceptable if they show the expected understanding, even if wording differs.
Use score 0-5 for each answer.
Be concise and constructive.

Inputs:
{json.dumps(rubric_input, indent=2)}""",
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=settings.API_TIMEOUT * 1000),
            ),
        )

        result = response.parsed or {}
        items = result.get("items", [])
        accepted = sum(1 for item in items if item.get("acceptable"))
        total = len(items)

        payload = {
            "session_id": session_id,
            "skill": skill,
            "topic": topic,
            "items": items,
            "accepted_count": accepted,
            "total_questions": total,
            "overall_feedback": result.get("overall_feedback", "").strip(),
            "recommended_next_step": result.get("recommended_next_step", "").strip(),
        }

        _persist_session_async(
            session_id,
            {
                "last_practice_evaluation": payload,
            },
        )
        return payload
    except Exception as e:
        logger.error(f"Error evaluating practice answers: {e}")
        return {"error": str(e), "items": []}


def get_socratic_hint(
    session_id: str,
    skill: str,
    topic: str,
    level: str,
    code: str = "",
    error: str = "",
    hint_level: int = 1,
) -> dict:
    """
    Generate Socratic hints - guide without giving away the answer.
    """
    try:
        hint_level = int(hint_level or 1)
        hint_level = max(1, min(hint_level, 3))

        hint_type = {
            1: "Give a conceptual hint about the underlying principle.",
            2: "Suggest the right approach and sequence of steps without giving the solution.",
            3: "Provide structure with at most 2 short lines of pseudocode or code scaffolding.",
        }

        schema = {
            "type": "object",
            "properties": {
                "hint": {"type": "string"},
                "question": {"type": "string"},
                "next_focus": {"type": "string"},
            },
            "required": ["hint", "question", "next_focus"],
        }

        prompt = f"""You are a Socratic AI tutor helping a {level} learner.

Skill: {skill}
Topic: {topic}
Hint level: {hint_level}
Instruction: {hint_type[hint_level]}

Rules:
- Never give the complete solution.
- Keep the hint concise.
- If you include code, keep it to at most 2 lines.
- The final question must push the learner to think about the next step.
- Tailor the hint to the user's current code/error if provided.
"""

        if code:
            prompt += f"\nUser code:\n```{code}```\n"
        if error:
            prompt += f"\nObserved error:\n{error}\n"

        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=settings.API_TIMEOUT * 1000),
            ),
        )

        result = response.parsed or {}
        hint = (result.get("hint") or "").strip()
        question = (result.get("question") or "").strip()
        next_focus = (result.get("next_focus") or "").strip()

        if not hint:
            raise ValueError("Hint generator returned empty hint")
        if not question.endswith("?"):
            question = (question.rstrip(".") + "?").strip() if question else "What step do you think should come next?"

        _track_hint_usage(session_id, skill, topic, hint_level)

        logger.info(f"Generated Socratic hint for {skill}/{topic} at level {hint_level}")
        return {
            "hint": hint,
            "question": question,
            "next_focus": next_focus,
            "hint_level": hint_level,
            "topic": topic,
            "skill": skill,
        }
    except Exception as e:
        logger.error(f"Error generating Socratic hint: {e}")
        return {
            "error": str(e),
            "hint": "Break the problem into one small step and test just that part first.",
            "question": "Which single step can you verify before changing the rest of the code?",
            "hint_level": hint_level,
            "topic": topic,
            "skill": skill,
        }


def _track_hint_usage(session_id: str, skill: str, topic: str, hint_level: int):
    """Track hint usage to identify weak topics."""
    try:
        key = f"{skill}:{topic}"
        with _hint_lock:
            session_usage = dict(_hint_usage_memory.get(session_id, {}))
            if key not in session_usage:
                session_usage[key] = {
                    "count": 0,
                    "max_level": 0,
                }

            session_usage[key]["count"] += 1
            session_usage[key]["max_level"] = max(session_usage[key]["max_level"], hint_level)
            _hint_usage_memory[session_id] = session_usage

        _persist_session_async(session_id, {"hint_usage": session_usage})
    except Exception as e:
        logger.error(f"Error tracking hint usage: {e}")


def get_weak_topics(session_id: str) -> dict:
    """
    Analyze hint usage to identify weak topics.
    """
    try:
        with _hint_lock:
            hint_usage = dict(_hint_usage_memory.get(session_id, {}))

        if not hint_usage:
            session = get_session(session_id)
            if not session:
                return {"error": "Session not found"}
            hint_usage = session.get("hint_usage", {})
        weak_topics = []

        for key, data in hint_usage.items():
            skill, topic = key.split(":", 1)
            if data["count"] >= 3 or data["max_level"] >= 3:
                weak_topics.append(
                    {
                        "skill": skill,
                        "topic": topic,
                        "hint_count": data["count"],
                        "max_hint_level": data["max_level"],
                        "needs_review": True,
                    }
                )

        weak_topics.sort(key=lambda x: (x["hint_count"], x["max_hint_level"]), reverse=True)
        return {
            "session_id": session_id,
            "weak_topics": weak_topics,
            "total_weak": len(weak_topics),
        }
    except Exception as e:
        logger.error(f"Error getting weak topics: {e}")
        return {"error": str(e)}


def explain_concept(skill: str, topic: str, level: str) -> dict:
    """
    Explain a concept at the appropriate level.
    """
    try:
        schema = {
            "type": "object",
            "properties": {
                "explanation": {"type": "string"},
                "example": {"type": "string"},
                "practice": {"type": "string"},
            },
            "required": ["explanation", "example", "practice"],
        }

        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""Explain the concept of "{topic}" in {skill} for a {level} learner.

Rules:
- Explanation under 150 words.
- Include one very small code example.
- End with one practical next step.""",
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=settings.API_TIMEOUT * 1000),
            ),
        )

        result = response.parsed or {}
        return {
            "topic": topic,
            "skill": skill,
            "level": level,
            "explanation": (result.get("explanation") or "").strip(),
            "example": (result.get("example") or "").strip(),
            "practice": (result.get("practice") or "").strip(),
        }
    except Exception as e:
        logger.error(f"Error explaining concept: {e}")
        return {"error": str(e)}


TOOL_DEFINITIONS = [
    {
        "name": "generate_practice_set",
        "description": "Generate 3-4 practice questions and 1 mini-lab for a selected skill topic and language.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"},
                "skill": {"type": "string", "description": "Current skill being learned"},
                "topic": {"type": "string", "description": "Specific topic or concept"},
                "level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"], "description": "User skill level"},
                "language": {"type": "string", "description": "Programming language for the mini-lab"},
            },
            "required": ["session_id", "skill", "topic", "level"],
        },
    },
    {
        "name": "evaluate_practice_answers",
        "description": "Evaluate the learner's answers for the active practice pack and decide whether they are acceptable.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"},
                "skill": {"type": "string", "description": "Current skill being learned"},
                "topic": {"type": "string", "description": "Specific topic or concept"},
                "answers": {"type": "array", "items": {"type": "string"}, "description": "Learner answers in order"},
            },
            "required": ["session_id", "skill", "topic", "answers"],
        },
    },
    {
        "name": "get_socratic_hint",
        "description": "Generate Socratic hints to guide learning without giving answers. Max 2 lines code, always ends with question.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"},
                "skill": {"type": "string", "description": "Current skill being learned"},
                "topic": {"type": "string", "description": "Specific topic or concept"},
                "level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"], "description": "User skill level"},
                "code": {"type": "string", "description": "User's current code"},
                "error": {"type": "string", "description": "Error message if any"},
                "hint_level": {"type": "integer", "enum": [1, 2, 3], "description": "1=concept, 2=approach, 3=structure"},
            },
            "required": ["session_id", "skill", "topic", "level"],
        },
    },
    {
        "name": "get_weak_topics",
        "description": "Analyze hint usage to identify weak topics that need more practice",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "explain_concept",
        "description": "Explain a programming concept at the appropriate level",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "The skill being learned"},
                "topic": {"type": "string", "description": "Concept to explain"},
                "level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"], "description": "User level"},
            },
            "required": ["skill", "topic", "level"],
        },
    },
]
