"""Static install guidance for local CLI agents (no auto-install — D4)."""

from __future__ import annotations

_HINTS: dict[str, dict[str, str]] = {
    "claude": {
        "install_command": "npm install -g @anthropic-ai/claude-code",
        "docs_url": "https://docs.anthropic.com/en/docs/claude-code",
        "platform_note": "装后需 `claude` 登录授权。",
    },
    "codex": {
        "install_command": "npm install -g @openai/codex",
        "docs_url": "https://github.com/openai/codex",
        "platform_note": "亦可用 OpenAI Codex 桌面安装；装后需登录。",
    },
    "cursor-agent": {
        "install_command": "curl https://cursor.com/install -fsS | bash",
        "docs_url": "https://www.cursor.com/cli",
        "platform_note": "Windows 见官方文档；装后 `cursor-agent login`。",
    },
    "trae": {
        "install_command": "见官方文档安装 Trae CLI",
        "docs_url": "https://docs.trae.cn/cli",
        "platform_note": "需含 `trae-cli` 的版本；装后登录。",
    },
    "antigravity": {
        "install_command": "见官方安装包",
        "docs_url": "https://antigravity.google",
        "platform_note": "装后在其 CLI 设置中配置模型与登录。",
    },
}


def get_install_hint(agent_id: str) -> dict[str, str] | None:
    return _HINTS.get((agent_id or "").strip())
