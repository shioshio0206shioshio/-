"""下書き生成に使う LLM。config の llm.provider で切り替える。

- anthropic: Claude API（ANTHROPIC_API_KEY が必要）
- command:   任意の CLI にプロンプトを標準入力で渡す（例: codex exec -）
- none:      LLM を使わずテンプレートだけで下書きを作る
"""

from __future__ import annotations

import json
import re
import subprocess

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "application": {"type": "string"},
        "email_subject": {"type": "string"},
        "email_body": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "proposed_price": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["application", "email_subject", "email_body", "questions", "proposed_price", "notes"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    pass


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise LLMError("JSON が返ってきませんでした")
    return json.loads(m.group(0))


class AnthropicBackend:
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium"):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def generate(self, system: str, prompt: str) -> dict:
        # 安全分類器が断った場合はサーバー側で別モデルに切り替える（fallbacks: "default"）
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": DRAFT_SCHEMA},
            },
        )
        if response.stop_reason == "refusal":
            raise LLMError("モデルが生成を断りました")
        if response.stop_reason == "max_tokens":
            raise LLMError("出力が途中で切れました")
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)


class CommandBackend:
    def __init__(self, command: list[str], timeout: float = 300):
        self.command = command
        self.timeout = timeout

    def generate(self, system: str, prompt: str) -> dict:
        full = (
            f"{system}\n\n{prompt}\n\n"
            "次のキーを持つ JSON オブジェクトだけを出力してください（前後に説明文を付けない）: "
            + ", ".join(DRAFT_SCHEMA["required"])
        )
        result = subprocess.run(
            self.command, input=full, capture_output=True, text=True, encoding="utf-8", timeout=self.timeout
        )
        if result.returncode != 0:
            raise LLMError(f"コマンドが失敗しました: {result.stderr.strip()[:300]}")
        return _parse_json(result.stdout)


def make_backend(cfg: dict):
    provider = cfg.get("provider", "none")
    if provider == "anthropic":
        return AnthropicBackend(cfg.get("model", "claude-opus-5-5"), cfg.get("effort", "medium"))
    if provider == "command":
        return CommandBackend(cfg["command"], cfg.get("timeout", 300))
    return None
