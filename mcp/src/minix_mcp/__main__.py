from __future__ import annotations

import json

from minix_mcp.daemon_client import build_app_not_running_response


def main() -> None:
    print(json.dumps(build_app_not_running_response()))


if __name__ == "__main__":
    main()
