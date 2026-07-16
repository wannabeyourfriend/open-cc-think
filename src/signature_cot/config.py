"""Configuration loading without ever serializing credentials."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT / ".env.aws"


def read_env_file(path: Path) -> Dict[str, str]:
    """Read the small ``export KEY=value`` format used by .env.aws.

    This deliberately does not perform shell expansion or execute the file.
    """

    values: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        parsed = shlex.split(value, comments=False, posix=True)
        values[key] = parsed[0] if parsed else ""
    return values


def load_env_file(path: Path, override: bool = False) -> None:
    for key, value in read_env_file(path).items():
        if override or key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    model: str
    region: str = "us-east-1"
    timeout_seconds: float = 300.0
    endpoint: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        env_file: Optional[Path] = DEFAULT_ENV_FILE,
        model: Optional[str] = None,
        region: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> "ProviderConfig":
        if env_file is not None:
            if not env_file.exists():
                raise FileNotFoundError("environment file not found: %s" % env_file)
            load_env_file(env_file)

        api_key = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()
        selected_model = (
            model
            or os.environ.get("ANTHROPIC_SONNET_MODEL")
            or os.environ.get("MODEL")
            or "global.anthropic.claude-sonnet-4-6"
        ).strip()
        if not api_key:
            raise ValueError("AWS_BEARER_TOKEN_BEDROCK is not configured")
        if not selected_model:
            raise ValueError("a Bedrock model ID is required")
        return cls(
            api_key=api_key,
            model=selected_model,
            region=region or os.environ.get("AWS_REGION", "us-east-1"),
            timeout_seconds=timeout_seconds
            if timeout_seconds is not None
            else float(os.environ.get("HTTP_TIMEOUT", "300")),
            endpoint=os.environ.get("BEDROCK_RUNTIME_ENDPOINT") or None,
        )

    @property
    def safe_summary(self) -> Dict[str, object]:
        return {
            "provider": "amazon-bedrock-converse",
            "model": self.model,
            "region": self.region,
            "endpoint_override": bool(self.endpoint),
            "credential_configured": bool(self.api_key),
        }

