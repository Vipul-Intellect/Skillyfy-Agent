import requests

from config.settings import settings
from executor_service.runtime import (
    execute_code as execute_code_local,
    get_execution_config as get_execution_config_local,
    normalize_language,
    validate_code as validate_code_local,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def _executor_headers() -> dict:
    headers = {}
    if settings.EXECUTOR_SHARED_SECRET:
        headers["X-Executor-Secret"] = settings.EXECUTOR_SHARED_SECRET
    return headers


def _call_executor_service(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    base_url = (settings.EXECUTOR_SERVICE_URL or "").rstrip("/")
    if not base_url:
        raise ValueError("EXECUTOR_SERVICE_URL is not configured")

    url = f"{base_url}{path}"
    timeout = settings.EXECUTOR_REQUEST_TIMEOUT

    if method == "GET":
        response = requests.get(url, headers=_executor_headers(), timeout=timeout)
    else:
        response = requests.post(url, json=payload or {}, headers=_executor_headers(), timeout=timeout)

    response.raise_for_status()
    body = response.json()
    if not body.get("success", False):
        raise RuntimeError(body.get("error", "Executor service request failed"))
    return body.get("data", {})


def execute_code(code: str, language: str, stdin: str = "") -> dict:
    """Execute code using the executor service, falling back to local runtime if needed."""
    normalized = normalize_language(language)
    try:
        if settings.EXECUTOR_SERVICE_URL:
            return _call_executor_service(
                "/execute",
                method="POST",
                payload={
                    "code": code,
                    "language": normalized,
                    "stdin": stdin,
                },
            )
    except Exception as e:
        logger.warning(f"Executor service call failed, using local runtime fallback: {e}")

    return execute_code_local(code=code, language=normalized, stdin=stdin)


def get_execution_config() -> dict:
    """Return editor/runtime config for the coding environment."""
    try:
        if settings.EXECUTOR_SERVICE_URL:
            return _call_executor_service("/config", method="GET")
    except Exception as e:
        logger.warning(f"Execution config service call failed, using local config fallback: {e}")

    return get_execution_config_local()


def validate_code(code: str, language: str) -> dict:
    """Validate code syntax using the executor service, falling back locally."""
    normalized = normalize_language(language)
    try:
        if settings.EXECUTOR_SERVICE_URL:
            return _call_executor_service(
                "/validate",
                method="POST",
                payload={
                    "code": code,
                    "language": normalized,
                },
            )
    except Exception as e:
        logger.warning(f"Validation service call failed, using local validation fallback: {e}")

    return validate_code_local(code=code, language=normalized)


TOOL_DEFINITIONS = [
    {
        "name": "execute_code",
        "description": "Execute code in various programming languages using the isolated executor service",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to execute"},
                "language": {"type": "string", "description": "Programming language"},
                "stdin": {"type": "string", "description": "Standard input for the code"},
            },
            "required": ["code", "language"],
        },
    },
    {
        "name": "validate_code",
        "description": "Validate code syntax without executing",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to validate"},
                "language": {"type": "string", "description": "Programming language"},
            },
            "required": ["code", "language"],
        },
    },
    {
        "name": "get_execution_config",
        "description": "Return the coding environment config for Monaco and the supported execution runtimes.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
