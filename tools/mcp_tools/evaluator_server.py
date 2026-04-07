# Evaluator Agent MCP Server
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from tools.mcp_tools import evaluator
from utils.logger import get_logger

logger = get_logger(__name__)

app = Server("skillup-evaluator-tools")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="generate_evaluation",
            description="Generate a 5-question evaluation pack for a skill and level",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "skill": {"type": "string"},
                    "level": {
                        "type": "string",
                        "enum": ["Beginner", "Intermediate", "Advanced"],
                    },
                    "question_count": {"type": "integer"},
                },
                "required": ["session_id", "skill", "level"],
            },
        ),
        Tool(
            name="evaluate_answers",
            description="Evaluate submitted answers, score them, and save the result",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "skill": {"type": "string"},
                    "level": {"type": "string"},
                    "answers": {"type": "array", "items": {"type": "string"}},
                    "questions": {"type": "array", "items": {"type": "object"}},
                    "practice_summary": {"type": "object"},
                },
                "required": ["session_id", "answers"],
            },
        ),
        Tool(
            name="fetch_jobs",
            description="Fetch relevant jobs for a skill and level using RapidAPI JSearch",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "skill": {"type": "string"},
                    "level": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["skill"],
            },
        ),
        Tool(
            name="get_evaluation_result",
            description="Get saved evaluation result for a session",
            inputSchema={
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    logger.info(f"Evaluator MCP Tool called: {name}")

    try:
        if name == "generate_evaluation":
            result = evaluator.generate_evaluation(
                session_id=arguments.get("session_id", ""),
                skill=arguments.get("skill", ""),
                level=arguments.get("level", "Beginner"),
                question_count=arguments.get("question_count", 5),
            )
        elif name == "evaluate_answers":
            result = evaluator.evaluate_answers(
                session_id=arguments.get("session_id", ""),
                skill=arguments.get("skill", ""),
                level=arguments.get("level", ""),
                answers=arguments.get("answers", []),
                questions=arguments.get("questions"),
                practice_summary=arguments.get("practice_summary"),
            )
        elif name == "fetch_jobs":
            result = evaluator.fetch_jobs(
                skill=arguments.get("skill", ""),
                level=arguments.get("level", ""),
                limit=arguments.get("limit", 10),
                session_id=arguments.get("session_id", ""),
            )
        elif name == "get_evaluation_result":
            result = evaluator.get_evaluation_result(
                session_id=arguments.get("session_id", ""),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        logger.info(f"Evaluator MCP Tool completed: {name}")
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        logger.error(f"Evaluator MCP tool error: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    logger.info("Starting Evaluator Agent MCP Server via stdio...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
