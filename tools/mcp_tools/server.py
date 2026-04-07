# MCP Server for Orchestrator Agent
import sys
import os

# Add project root to path (needed when running as subprocess)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from utils.logger import get_logger

logger = get_logger(__name__)

# Import tool functions
from tools.mcp_tools import trending, resume, assessment

# Create MCP Server
app = Server("skillup-orchestrator-tools")

@app.list_tools()
async def list_tools():
    """List all available MCP tools"""
    return [
        Tool(
            name="fetch_trending_skills",
            description="Fetch top 7 trending tech skills. If target_role is provided (e.g., 'ML Engineer', 'AI Engineer', 'Backend Developer'), returns role-specific skills.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_role": {"type": "string", "description": "Optional: Target job role for role-specific trending skills (e.g., 'ML Engineer', 'AI Engineer')"}
                },
                "required": []
            }
        ),
        Tool(
            name="analyze_resume",
            description="Analyze resume text and extract technical skills, experience level, and domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "The resume text content"},
                    "session_id": {"type": "string", "description": "User session ID"}
                },
                "required": ["resume_text", "session_id"]
            }
        ),
        Tool(
            name="analyze_resume_document",
            description="Analyze a resume PDF or image and extract technical skills, experience level, and domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "Original file name"},
                    "mime_type": {"type": "string", "description": "Uploaded file MIME type"},
                    "file_data_base64": {"type": "string", "description": "Base64-encoded file contents"},
                    "session_id": {"type": "string", "description": "User session ID"}
                },
                "required": ["file_name", "mime_type", "file_data_base64", "session_id"]
            }
        ),
        Tool(
            name="find_skill_gaps_with_recommendations",
            description="Find skill gaps by comparing user skills with job requirements and recommend trending skills",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_skills": {"type": "array", "items": {"type": "string"}, "description": "List of user's current skills"},
                    "target_role": {"type": "string", "description": "Target job role"},
                    "session_id": {"type": "string", "description": "User session ID"},
                    "force_live_market_profile": {"type": "boolean", "description": "When true, wait for a live market profile instead of returning a warming fallback"}
                },
                "required": ["user_skills", "target_role", "session_id"]
            }
        ),
        Tool(
            name="generate_assessment_questions",
            description="Generate skill assessment questions based on declared user level",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "The skill to assess"},
                    "declared_level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"], "description": "User's declared skill level"},
                    "session_id": {"type": "string", "description": "User session ID"}
                },
                "required": ["skill", "declared_level", "session_id"]
            }
        ),
        Tool(
            name="validate_user_level",
            description="Validate user's skill level based on their answers to assessment questions",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "User session ID"},
                    "answers": {"type": "array", "items": {"type": "string"}, "description": "User's answers to assessment questions"}
                },
                "required": ["session_id", "answers"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute MCP tool"""
    logger.info(f"MCP Tool called: {name} with args: {arguments}")
    
    try:
        if name == "fetch_trending_skills":
            result = trending.fetch_trending_skills(
                target_role=arguments.get("target_role")
            )
        elif name == "analyze_resume":
            result = resume.analyze_resume(
                resume_text=arguments.get("resume_text", ""),
                session_id=arguments.get("session_id", "")
            )
        elif name == "analyze_resume_document":
            result = resume.analyze_resume_document(
                file_name=arguments.get("file_name", ""),
                mime_type=arguments.get("mime_type", ""),
                file_data_base64=arguments.get("file_data_base64", ""),
                session_id=arguments.get("session_id", "")
            )
        elif name == "find_skill_gaps_with_recommendations":
            result = resume.find_skill_gaps_with_recommendations(
                user_skills=arguments.get("user_skills", []),
                target_role=arguments.get("target_role", ""),
                session_id=arguments.get("session_id", ""),
                force_live_market_profile=arguments.get("force_live_market_profile", False),
            )
        elif name == "generate_assessment_questions":
            result = assessment.generate_assessment_questions(
                skill=arguments.get("skill", ""),
                declared_level=arguments.get("declared_level", "Beginner"),
                session_id=arguments.get("session_id", "")
            )
        elif name == "validate_user_level":
            result = assessment.validate_user_level(
                session_id=arguments.get("session_id", ""),
                answers=arguments.get("answers", []),
                questions=arguments.get("questions"),
                declared_level=arguments.get("declared_level"),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        logger.info(f"MCP Tool result: {name} completed")
        return [TextContent(type="text", text=json.dumps(result))]
        
    except Exception as e:
        logger.error(f"MCP Tool error: {name} - {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

async def run_server():
    """Run the MCP server via stdio"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    logger.info("Starting MCP Server via stdio...")
    asyncio.run(run_server())
