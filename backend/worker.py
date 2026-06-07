from __future__ import annotations

import asyncio
import os
import signal

from fastapi import FastAPI


async def _run() -> None:
    os.environ.setdefault("OSINT_ROLE", "worker")

    from backend.main import lifespan

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    async with lifespan(FastAPI()):
        await stop.wait()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
