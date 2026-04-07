import asyncio
import inspect
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from utils.logger import get_logger
from a2a.registry import get_agent, list_agents, register_agent

logger = get_logger(__name__)


@dataclass
class A2AMessage:
    from_agent: str
    to_agent: str
    message_type: str
    session_id: str
    payload: dict = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self):
        """Validate required A2A message fields."""
        if not self.from_agent:
            raise ValueError("from_agent is required")
        if not self.to_agent:
            raise ValueError("to_agent is required")
        if not self.message_type:
            raise ValueError("message_type is required")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dictionary")
        return True

    def to_dict(self):
        """Serialize message to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        """Create a validated message from a dictionary."""
        message = cls(
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", ""),
            message_type=data.get("message_type", ""),
            session_id=data.get("session_id", ""),
            payload=data.get("payload", {}),
            message_id=data.get("message_id", str(uuid.uuid4())),
            timestamp=data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
        )
        message.validate()
        return message


class A2AProtocol:
    START_LEARNING = "start_learning"
    GET_VIDEOS = "get_videos"
    REQUEST_EVALUATION = "request_evaluation"
    START_EVALUATION = "start_evaluation"
    EVALUATION_COMPLETE = "evaluation_complete"
    FETCH_JOBS = "fetch_jobs"

    def __init__(self):
        self.message_log = []

    def register_agent(self, name: str, agent):
        """Register an agent for A2A routing."""
        return register_agent(name, agent)

    def get_registered_agents(self):
        """Return registered agent names."""
        return list_agents()

    async def send_message(self, message):
        """Send a validated message to the destination agent."""
        if isinstance(message, dict):
            message = A2AMessage.from_dict(message)
        elif not isinstance(message, A2AMessage):
            raise TypeError("message must be an A2AMessage or dictionary")

        message.validate()

        recipient = get_agent(message.to_agent)
        if recipient is None:
            error = f"Target agent not registered: {message.to_agent}"
            logger.error(error)
            response_envelope = {
                "success": False,
                "error": error,
                "message": message.to_dict(),
            }
            self.message_log.append(response_envelope)
            return response_envelope

        handler = getattr(recipient, "handle_a2a_message", None)
        if handler is None:
            error = f"Agent '{message.to_agent}' has no handle_a2a_message method"
            logger.error(error)
            response_envelope = {
                "success": False,
                "error": error,
                "message": message.to_dict(),
            }
            self.message_log.append(response_envelope)
            return response_envelope

        logger.info(
            f"A2A message {message.message_type}: "
            f"{message.from_agent} -> {message.to_agent}"
        )

        if inspect.iscoroutinefunction(handler):
            response = await handler(message)
        else:
            response = handler(message)
            if inspect.isawaitable(response):
                response = await response

        response_envelope = {
            "success": True,
            "message": message.to_dict(),
            "response": response,
        }
        self.message_log.append(response_envelope)
        return response_envelope

    def send_message_sync(self, message):
        """Sync wrapper for contexts that are not already async."""
        return asyncio.run(self.send_message(message))


a2a_protocol = A2AProtocol()
