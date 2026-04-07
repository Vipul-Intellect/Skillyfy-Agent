from utils.logger import get_logger

logger = get_logger(__name__)

AGENT_REGISTRY = {}


def register_agent(name: str, agent):
    """Register or replace an agent instance by name."""
    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        raise ValueError("Agent name is required")

    AGENT_REGISTRY[normalized_name] = agent
    logger.info(f"A2A agent registered: {normalized_name}")
    return agent


def get_agent(name: str):
    """Fetch an agent instance from the registry."""
    normalized_name = (name or "").strip().lower()
    return AGENT_REGISTRY.get(normalized_name)


def list_agents():
    """Return the sorted list of registered agent names."""
    return sorted(AGENT_REGISTRY.keys())


def clear_registry():
    """Clear the registry. Useful for tests."""
    AGENT_REGISTRY.clear()
    logger.info("A2A agent registry cleared")
