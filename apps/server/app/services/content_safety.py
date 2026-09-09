"""内容安全过滤（PRD §6.2）。

M1 为 mock 实现（接口已预留）；M5 接入真实 API
（国内：阿里云/腾讯云内容安全；海外：OpenAI Moderation，以部署地域为准）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SafetyResult:
    passed: bool
    reason: str | None = None


class ContentSafetyChecker:
    """输入侧过滤接口。M5 替换为真实 API 客户端。"""

    def check_image(self, image_path: Path) -> SafetyResult:
        return SafetyResult(passed=True, reason="mock-checker")


class MockContentSafetyChecker(ContentSafetyChecker):
    """M1 mock：全部放行。"""
