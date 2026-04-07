"""
Evaluator Agent - Handles evaluation and job search
SkillUp Agent - Google GenAI APAC 2026 Hackathon

Uses MCP for tool calls, ADK for LLM, A2A for agent communication.
"""
import os
import sys
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings
from utils.logger import get_logger
from database.firestore_client import FirestoreClient
# A2A imports - uncomment when a2a folder exists
# from a2a.protocol import A2AMessage, A2AProtocol, a2a_protocol

logger = get_logger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _child_process_env() -> dict:
    """Explicitly forward Cloud Run env vars to the MCP subprocess."""
    env = os.environ.copy()
    existing_path = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = PROJECT_ROOT if not existing_path else f"{PROJECT_ROOT}{os.pathsep}{existing_path}"
    return env


class EvaluatorAgent:
    """
    Evaluator Agent responsibilities:
    1. Generate evaluation questions (5 questions)
    2. Score user answers
    3. Generate badge based on score
    4. Fetch relevant jobs (RapidAPI JSearch - 10 jobs)
    5. Save results to Firestore
    """
    
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = "gemini-2.5-flash"
        self.db = FirestoreClient()
        
        # MCP server path (absolute)
        MCP_SERVER_PATH = os.path.join(PROJECT_ROOT, "tools", "mcp_tools", "evaluator_server.py")
        self.server_params = StdioServerParameters(
            command="python",
            args=[MCP_SERVER_PATH],
            env=_child_process_env()
        )
        
        # Register with A2A protocol
        a2a_protocol.register_agent("evaluator", self)
        logger.info("EvaluatorAgent initialized")
    
    async def handle_a2a_message(self, message: A2AMessage) -> dict:
        """Handle incoming A2A messages"""
        if message.message_type == A2AProtocol.REQUEST_EVALUATION:
            return await self.generate_evaluation(
                message.session_id,
                message.payload.get('skill'),
                message.payload.get('level')
            )
        elif message.message_type == A2AProtocol.FETCH_JOBS:
            return await self.fetch_jobs(message.payload.get('skill'))
        return {"error": "Unknown message type"}
    
    async def generate_evaluation(self, session_id: str, skill: str, level: str) -> dict:
        """Generate 5 evaluation questions"""
        try:
            prompt = f"""Generate exactly 5 evaluation questions for {skill} at {level} level.

Mix of:
- 3 multiple choice questions (4 options each)
- 2 short answer questions

Return JSON:
{{
    "questions": [
        {{
            "id": 1,
            "type": "multiple_choice",
            "question": "...",
            "options": ["A", "B", "C", "D"],
            "correct": "A",
            "difficulty": "easy|medium|hard"
        }},
        {{
            "id": 4,
            "type": "short_answer",
            "question": "...",
            "expected_keywords": ["keyword1", "keyword2"],
            "difficulty": "medium"
        }}
    ]
}}"""
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            return json.loads(text)
        except Exception as e:
            logger.error(f"Evaluation generation error: {e}")
            return {"error": str(e)}
    
    async def score_answers(self, session_id: str, skill: str, questions: list, answers: list) -> dict:
        """Score user answers and generate badge"""
        try:
            prompt = f"""Score these answers for {skill} evaluation.

Questions and Answers:
{json.dumps(list(zip(questions, answers)), indent=2)}

Score each answer (0-20 points each, 100 total).
Identify weak topics.

Return JSON:
{{
    "scores": [20, 15, 20, 10, 18],
    "total_score": 83,
    "badge": "Advanced",
    "weak_topics": ["topic1"],
    "feedback": "Overall feedback..."
}}

Badge criteria:
- 90-100: Expert
- 75-89: Advanced  
- 60-74: Intermediate
- 40-59: Beginner
- <40: Needs Practice"""
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2)
            )
            
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            result = json.loads(text)
            
            # Save to Firestore
            self.db.save_result(session_id, {
                "skill": skill,
                "score": result.get("total_score"),
                "badge": result.get("badge"),
                "weak_topics": result.get("weak_topics", [])
            })
            
            return result
        except Exception as e:
            logger.error(f"Scoring error: {e}")
            return {"error": str(e)}
    
    async def fetch_jobs(self, skill: str) -> dict:
        """Fetch 10 relevant jobs via RapidAPI JSearch"""
        import requests
        
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            headers = {
                "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            params = {
                "query": f"{skill} Developer",
                "num_pages": "1",
                "date_posted": "month"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            data = response.json()
            
            jobs = []
            for job in data.get("data", [])[:10]:
                jobs.append({
                    "title": job.get("job_title"),
                    "company": job.get("employer_name"),
                    "location": job.get("job_city", "Remote"),
                    "salary": job.get("job_min_salary", "Not specified"),
                    "url": job.get("job_apply_link"),
                    "description": job.get("job_description", "")[:200]
                })
            
            return {"jobs": jobs, "count": len(jobs)}
        except Exception as e:
            logger.error(f"Job fetch error: {e}")
            return {"jobs": [], "error": str(e)}


# For direct testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        agent = EvaluatorAgent()
        
        # Test evaluation generation
        result = await agent.generate_evaluation("test_session", "Python", "Beginner")
        print("Evaluation:", json.dumps(result, indent=2))
        
        # Test job fetch
        jobs = await agent.fetch_jobs("Python")
        print("Jobs:", json.dumps(jobs, indent=2))
    
    asyncio.run(test())
