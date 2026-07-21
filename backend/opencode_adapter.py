"""OpenCode adapter for OSINT backend intelligence workflows."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EMPTY_AGENT_OUTPUT = "Agent 未产生文本输出，请尝试重新提问。"


@dataclass
class OpenCodeResult:
    ok: bool
    text: str
    raw_stdout: str
    error: str = ""
    text_events: int = 0
    tool_events: int = 0
    duration_ms: float = 0.0


def is_empty_agent_output(answer: str) -> bool:
    stripped = (answer or "").strip()
    return not stripped or stripped == DEFAULT_EMPTY_AGENT_OUTPUT


def parse_opencode_output(stdout: str, duration_ms: float = 0.0) -> OpenCodeResult:
    parts: list[str] = []
    tool_results: list[str] = []
    errors: list[str] = []
    text_events = 0
    tool_events = 0

    for line in stdout.strip().split("\n"):
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")
        part = event.get("part", {}) if isinstance(event.get("part", {}), dict) else {}
        if event_type == "text":
            text = part.get("text", "")
            if text:
                text_events += 1
                parts.append(text)
        elif event_type == "tool_use":
            tool_events += 1
            state = part.get("state", {}) if isinstance(part.get("state", {}), dict) else {}
            output = state.get("output", "")
            if output and "Error executing" not in output:
                tool_results.append(str(output)[:500])
        elif event_type == "error":
            data = event.get("error", {})
            if isinstance(data, dict):
                message = data.get("data", {}).get("message") if isinstance(data.get("data"), dict) else None
                errors.append(str(message or data.get("name") or "OpenCode error"))
            else:
                errors.append(str(data))

    if parts:
        return OpenCodeResult(
            ok=True,
            text="\n".join(parts),
            raw_stdout=stdout,
            text_events=text_events,
            tool_events=tool_events,
            duration_ms=duration_ms,
        )

    if errors:
        return OpenCodeResult(
            ok=False,
            text="",
            raw_stdout=stdout,
            error="; ".join(errors),
            text_events=text_events,
            tool_events=tool_events,
            duration_ms=duration_ms,
        )

    if tool_results:
        return OpenCodeResult(
            ok=True,
            text="工具调用结果:\n" + "\n---\n".join(tool_results[:5]),
            raw_stdout=stdout,
            text_events=text_events,
            tool_events=tool_events,
            duration_ms=duration_ms,
        )

    return OpenCodeResult(
        ok=False,
        text="",
        raw_stdout=stdout,
        error=DEFAULT_EMPTY_AGENT_OUTPUT,
        text_events=text_events,
        tool_events=tool_events,
        duration_ms=duration_ms,
    )


class OpenCodeAdapter:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        opencode_bin: str | None = None,
        model: str | None = None,
        mode: str | None = None,
        opencode_url: str | None = None,
        cwd: str | Path | None = None,
    ):
        self.enabled = _env_bool("OPENCODE_ENABLED", True) if enabled is None else enabled
        self.opencode_bin = opencode_bin or os.getenv("OPENCODE_BIN", "/usr/local/bin/opencode")
        self.model = model or os.getenv("OPENCODE_MODEL", "deepseek/deepseek-chat")
        self.mode = mode or os.getenv("OPENCODE_MODE", "cli")
        self.opencode_url = opencode_url or os.getenv("OPENCODE_URL", "http://127.0.0.1:3001")
        self.cwd = Path(cwd) if cwd is not None else Path(__file__).resolve().parent.parent

    def build_args(self, agent: str, prompt: str) -> list[str]:
        args = [
            self.opencode_bin,
            "run",
            "--agent",
            agent,
            "--model",
            self.model,
            "--format",
            "json",
        ]
        if self.mode == "attach":
            args.extend(["--attach", self.opencode_url])
        args.append(prompt)
        return args

    async def run(self, agent: str, prompt: str, timeout: int | None = None) -> OpenCodeResult:
        if not self.enabled:
            return OpenCodeResult(ok=False, text="", raw_stdout="", error="OpenCode disabled")

        env = os.environ.copy()
        for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "OPENCODE_MODEL"):
            env.setdefault(key, os.getenv(key, ""))

        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *self.build_args(agent, prompt),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout or int(os.getenv("OPENCODE_TIMEOUT", "180")))
        except asyncio.TimeoutError:
            proc.kill()
            return OpenCodeResult(
                ok=False,
                text="",
                raw_stdout="",
                error=f"OpenCode timeout after {timeout or os.getenv('OPENCODE_TIMEOUT', '180')}s",
                duration_ms=(time.monotonic() - started) * 1000,
            )

        duration_ms = (time.monotonic() - started) * 1000
        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
        result = parse_opencode_output(stdout_text, duration_ms=duration_ms)
        if not result.ok and stderr_text:
            result.error = f"{result.error}; stderr: {stderr_text[:500]}"
        return result

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "model": self.model,
            "opencode_bin": self.opencode_bin,
            "opencode_url": self.opencode_url,
        }


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
