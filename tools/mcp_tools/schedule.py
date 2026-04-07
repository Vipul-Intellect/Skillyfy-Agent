# Schedule Generation Tool for MCP
import google.generativeai as genai
from config.settings import settings
from database.firestore_client import save_session, get_session, update_session
from utils.logger import get_logger
import json

logger = get_logger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


def generate_schedule(
    session_id: str,
    skill: str,
    level: str,
    mode: str,
    daily_time: int
) -> dict:
    """
    Generate personalized learning schedule.
    
    Modes:
    - balanced: Equal mix of video, coding, revision
    - deep_learning: More theory and concepts
    - fast_track: Condensed, intensive learning
    - practice_focused: Heavy on coding exercises
    
    Time Distribution:
    - Video: ~40%
    - Coding: ~50%
    - Revision: ~10%
    
    Args:
        session_id: User session ID
        skill: Skill to learn
        level: User level (Beginner, Intermediate, Advanced)
        mode: Schedule mode
        daily_time: Daily time available in minutes
    
    Returns:
        Dictionary with schedule
    """
    try:
        # Calculate total days based on mode
        days_config = {
            "balanced": {"beginner": 7, "intermediate": 5, "advanced": 4},
            "deep_learning": {"beginner": 10, "intermediate": 7, "advanced": 5},
            "fast_track": {"beginner": 3, "intermediate": 2, "advanced": 2},
            "practice_focused": {"beginner": 6, "intermediate": 4, "advanced": 3}
        }
        
        level_key = level.lower()
        total_days = days_config.get(mode, days_config["balanced"]).get(level_key, 5)
        
        # Time distribution per mode
        time_dist = {
            "balanced": {"video": 0.40, "coding": 0.50, "revision": 0.10},
            "deep_learning": {"video": 0.50, "coding": 0.40, "revision": 0.10},
            "fast_track": {"video": 0.30, "coding": 0.60, "revision": 0.10},
            "practice_focused": {"video": 0.25, "coding": 0.65, "revision": 0.10}
        }
        
        dist = time_dist.get(mode, time_dist["balanced"])
        
        # Generate topics using Gemini
        topics = _generate_topics(skill, level, total_days)
        
        # Build daily plan
        daily_plan = []
        difficulties = _get_difficulty_progression(level, total_days)
        
        for day in range(1, total_days + 1):
            topic = topics[day - 1] if day <= len(topics) else f"{skill} Practice Day {day}"
            difficulty = difficulties[day - 1] if day <= len(difficulties) else level
            
            video_time = int(daily_time * dist["video"])
            coding_time = int(daily_time * dist["coding"])
            revision_time = int(daily_time * dist["revision"])
            
            daily_plan.append({
                "day": day,
                "topic": topic,
                "difficulty": difficulty,
                "goal": f"Master {topic}",
                "tasks": [
                    {"type": "video", "time": video_time, "description": f"Watch tutorial on {topic}"},
                    {"type": "coding", "time": coding_time, "description": f"Practice {topic} with exercises"},
                    {"type": "revision", "time": revision_time, "description": "Review and reinforce concepts"}
                ],
                "completed": False
            })
        
        schedule = {
            "schedule_enabled": True,
            "mode": mode,
            "skill": skill,
            "level": level,
            "total_days": total_days,
            "daily_time": daily_time,
            "daily_plan": daily_plan,
            "current_day": 1,
            "progress_percentage": 0
        }
        
        # Save schedule to session
        update_session(session_id, {"schedule": schedule})
        
        logger.info(f"Generated {mode} schedule for {skill}: {total_days} days")
        
        return schedule
        
    except Exception as e:
        logger.error(f"Error generating schedule: {e}")
        return {"error": str(e)}


def _generate_topics(skill: str, level: str, total_days: int) -> list:
    """Generate topic list using Gemini"""
    try:
        prompt = f"""Generate a learning roadmap for {skill} for a {level} learner.

Return EXACTLY {total_days} topics, one per day, in order of difficulty.
Start with fundamentals and progress to advanced concepts.

Return as a simple numbered list:
1. Topic 1
2. Topic 2
...

Only return the list, no explanations."""

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        # Parse topics
        topics = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                # Remove numbering
                topic = line.split(".", 1)[-1].strip()
                topics.append(topic)
        
        # Ensure we have enough topics
        while len(topics) < total_days:
            topics.append(f"{skill} Advanced Practice")
        
        return topics[:total_days]
        
    except Exception as e:
        logger.error(f"Error generating topics: {e}")
        # Fallback topics
        return [f"{skill} Day {i+1}" for i in range(total_days)]


def _get_difficulty_progression(level: str, total_days: int) -> list:
    """Get difficulty progression for each day"""
    if level.lower() == "beginner":
        # Start easy, gradually increase
        difficulties = []
        for i in range(total_days):
            if i < total_days // 3:
                difficulties.append("Easy")
            elif i < 2 * total_days // 3:
                difficulties.append("Medium")
            else:
                difficulties.append("Hard")
        return difficulties
    
    elif level.lower() == "intermediate":
        difficulties = []
        for i in range(total_days):
            if i < total_days // 2:
                difficulties.append("Medium")
            else:
                difficulties.append("Hard")
        return difficulties
    
    else:  # Advanced
        return ["Hard"] * total_days


def get_schedule(session_id: str) -> dict:
    """Get current schedule for a session"""
    try:
        session = get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        schedule = session.get('schedule', {})
        if not schedule:
            return {"schedule_enabled": False}
        
        return schedule
        
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        return {"error": str(e)}


def update_schedule_progress(session_id: str, day: int, completed: bool = True) -> dict:
    """Update schedule progress - mark day as completed"""
    try:
        session = get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        schedule = session.get('schedule', {})
        if not schedule:
            return {"error": "No schedule found"}
        
        # Update daily plan
        for plan in schedule.get('daily_plan', []):
            if plan['day'] == day:
                plan['completed'] = completed
                break
        
        # Calculate progress
        completed_days = sum(1 for p in schedule['daily_plan'] if p.get('completed'))
        total_days = len(schedule['daily_plan'])
        progress = int((completed_days / total_days) * 100) if total_days > 0 else 0
        
        schedule['progress_percentage'] = progress
        schedule['current_day'] = day + 1 if completed else day
        
        # Save updated schedule
        update_session(session_id, {"schedule": schedule})
        
        return {
            "day_completed": day,
            "progress_percentage": progress,
            "current_day": schedule['current_day'],
            "total_days": total_days
        }
        
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        return {"error": str(e)}


# MCP Tool Definitions
TOOL_DEFINITIONS = [
    {
        "name": "generate_schedule",
        "description": "Generate personalized learning schedule based on mode and available time",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"},
                "skill": {"type": "string", "description": "Skill to learn"},
                "level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"], "description": "User level"},
                "mode": {"type": "string", "enum": ["balanced", "deep_learning", "fast_track", "practice_focused"], "description": "Schedule mode"},
                "daily_time": {"type": "integer", "description": "Daily time available in minutes"}
            },
            "required": ["session_id", "skill", "level", "mode", "daily_time"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Get current learning schedule for a session",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "update_schedule_progress",
        "description": "Update schedule progress - mark a day as completed",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "User session ID"},
                "day": {"type": "integer", "description": "Day number to update"},
                "completed": {"type": "boolean", "description": "Whether day is completed"}
            },
            "required": ["session_id", "day"]
        }
    }
]
