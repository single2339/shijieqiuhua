"""Agent skill system — runtime-loadable YAML skill files that augment agent behavior.

Pattern: Claude Code's SKILL.md — declarative rules + configurable parameters
that get merged into an agent's system prompt and LLM config at runtime.

A Skill does NOT define new code paths. It modifies:
  - system_prompt_augment: appended to the agent's base system prompt
  - params: overrides for temperature, max_tokens, etc.
  - rules: do/don't directives injected into the prompt
  - framework: step-by-step reasoning chain the LLM should follow
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).resolve().parent.parent / "config" / "skills"


class SkillRule(BaseModel):
    do: list[str] = Field(default_factory=list)
    dont: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    description: str = ""
    agent_types: list[str] = Field(default_factory=list)
    system_prompt_augment: str = ""
    output_format: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    rules: SkillRule = Field(default_factory=SkillRule)
    framework: str = ""

    def render_prompt_augment(self) -> str:
        """Build the full prompt fragment this skill injects."""
        parts: list[str] = []

        if self.system_prompt_augment:
            parts.append(self.system_prompt_augment)

        if self.rules.do or self.rules.dont:
            parts.append("\n## 行为规则")
            for r in self.rules.do:
                parts.append(f"- 必须: {r}")
            for r in self.rules.dont:
                parts.append(f"- 禁止: {r}")

        if self.framework:
            parts.append(f"\n## 推理框架\n\n{self.framework}")

        if self.output_format:
            parts.append(f"\n## 输出格式\n\n{self.output_format}")

        return "\n".join(parts)


class SkillLoader:
    """Loads and caches Skill YAML files from SKILL_DIR."""

    _cache: dict[str, Skill] = {}

    @classmethod
    def list_all(cls) -> list[str]:
        if not SKILL_DIR.exists():
            return []
        return sorted(p.stem for p in SKILL_DIR.glob("*.yaml"))

    @classmethod
    def load(cls, name: str) -> Skill:
        if name in cls._cache:
            return cls._cache[name]

        path = SKILL_DIR / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Skill '{name}' not found at {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        skill = Skill(**data)
        cls._cache[name] = skill
        log.debug("Loaded skill: %s", name)
        return skill

    @classmethod
    def load_for_task(cls, skill_names: list[str]) -> list[Skill]:
        skills: list[Skill] = []
        for name in skill_names:
            try:
                skills.append(cls.load(name))
            except FileNotFoundError:
                log.warning("Skill '%s' not found, skipping", name)
        return skills

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache.clear()
