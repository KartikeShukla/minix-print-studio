from __future__ import annotations

import uvicorn

from minixd.app import create_app


def main() -> None:
    uvicorn.run(create_app(mock=True), host="127.0.0.1", port=39281)


if __name__ == "__main__":
    main()
