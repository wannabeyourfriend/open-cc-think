"""Minimal Bedrock Converse transport with bearer-token authentication."""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .config import ProviderConfig
from .models import BedrockResponse, Json


class ProviderError(RuntimeError):
    pass


class BedrockClient:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._temperature_supported = True

    @property
    def endpoint(self) -> str:
        return self.config.endpoint or (
            "https://bedrock-runtime.%s.amazonaws.com" % self.config.region
        )

    def converse(
        self,
        messages: List[Json],
        *,
        max_tokens: int,
        system: Optional[List[Json]] = None,
        tool_config: Optional[Json] = None,
        additional_model_request_fields: Optional[Json] = None,
        temperature: Optional[float] = None,
    ) -> BedrockResponse:
        payload: Json = {
            "messages": messages,
            "inferenceConfig": {"maxTokens": int(max_tokens)},
        }
        if temperature is not None and self._temperature_supported:
            payload["inferenceConfig"]["temperature"] = float(temperature)
        if system:
            payload["system"] = system
        if tool_config:
            payload["toolConfig"] = tool_config
        if additional_model_request_fields:
            payload["additionalModelRequestFields"] = additional_model_request_fields

        model_path = urllib.parse.quote(self.config.model, safe="")
        while True:
            request = urllib.request.Request(
                "%s/model/%s/converse" % (self.endpoint.rstrip("/"), model_path),
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": "Bearer " + self.config.api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.config.timeout_seconds
                ) as response:
                    data = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                body = exc.read(2000).decode("utf-8", errors="replace")
                lower = body.casefold()
                if (
                    exc.code == 400
                    and "temperature" in payload["inferenceConfig"]
                    and "temperature" in lower
                    and "deprecated" in lower
                ):
                    # Newer Claude models reject this formerly supported field.
                    # The rejected request generated no output, so retry once and
                    # remember the capability for continuation calls.
                    payload["inferenceConfig"].pop("temperature", None)
                    self._temperature_supported = False
                    continue
                raise ProviderError("Bedrock HTTP %s: %s" % (exc.code, body)) from exc
            except (
                urllib.error.URLError,
                TimeoutError,
                http.client.RemoteDisconnected,
            ) as exc:
                raise ProviderError("Bedrock request failed: %s" % exc) from exc

        output = data.get("output") if isinstance(data, dict) else None
        message = output.get("message") if isinstance(output, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            raise ProviderError("Bedrock response did not contain output.message.content")
        return BedrockResponse(
            content=content,
            stop_reason=str(data.get("stopReason", "")),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
            raw=data,
        )
