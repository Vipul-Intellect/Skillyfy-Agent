import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config.settings import settings
from tools.mcp_tools.resume import _normalize_cache_key, _refresh_market_role_profile


def main():
    refreshed = []
    failed = []

    for role in settings.HOT_MARKET_ROLES:
        role_key = _normalize_cache_key(role)
        result = _refresh_market_role_profile(role, role_key)
        if result:
            refreshed.append(role)
        else:
            failed.append(role)

    print(
        {
            "refreshed_roles": refreshed,
            "failed_roles": failed,
            "refreshed_count": len(refreshed),
            "failed_count": len(failed),
        }
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
