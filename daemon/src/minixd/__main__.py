from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from minixd.app import create_app


def main() -> None:
    data_dir = os.environ.get("MINIX_DAEMON_DATA_DIR")
    uvicorn.run(
        create_app(
            mock=os.environ.get("MINIX_DAEMON_MOCK", "true").lower() == "true",
            data_dir=Path(data_dir) if data_dir else None,
        ),
        host="127.0.0.1",
        port=int(os.environ.get("MINIX_DAEMON_PORT", "39281")),
    )


if __name__ == "__main__":
    main()
