from __future__ import annotations

import json
import os
from typing import Any

import httpx

from packages.shared.api_models import ThemeHeatView, ThemeStrategyAgentRequestView, ThemeStrategyAgentResponseView
from packages.shared.errors import AppError
from packages.shared.settings import MarketsConfig


class ThemeStrategyAgentService:
    DEFAULT_TOOL_CATALOG = (
        {'name': 'theme_context_reader', 'description': '读取当前热门题材快照和热度排序。'},
        {'name': 'patch_builder', 'description': '把客户对话转成题材新增、抬升和降温的增量更新。'},
        {'name': 'market_snapshot_summarizer', 'description': '压缩当前市场背景，帮助策略更贴合当下轮动。'},
    )
    DEFAULT_SKILL_CATALOG = (
        {'name': 'hot-theme-rotation', 'description': '识别热门题材轮动并优先强化强势方向。'},
        {'name': 'theme-market-mapper', 'description': '把热门题材映射到相关国家、交易所和市场代码，用于后续跨市场查股。'},
        {'name': 'client-dialogue', 'description': '把客户偏好翻译成策略语义和执行动作。'},
        {'name': 'incremental-strategy-design', 'description': '把一次对话落成可保存、可复用的策略版本。'},
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        markets_config: MarketsConfig | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv('OPENAI_API_KEY')
        self._base_url = (base_url or os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')).rstrip('/')
        self._model = model or os.getenv('OPENAI_MODEL', 'gpt-5.4')
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._markets_config = markets_config

    def compose_theme_strategy(
        self,
        *,
        request: ThemeStrategyAgentRequestView,
        themes: list[ThemeHeatView],
    ) -> ThemeStrategyAgentResponseView:
        if not self._api_key:
            raise AppError(
                503,
                'agent_backend_unavailable',
                'OPENAI_API_KEY 未配置，无法调用真实模型接口。',
            )

        payload = {
            'model': self._model,
            'messages': self._build_messages(request=request, themes=themes),
            'response_format': {'type': 'json_object'},
            'temperature': 0.3,
        }
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
        }

        with httpx.Client(base_url=self._base_url, timeout=self._timeout_seconds, transport=self._transport) as client:
            response = client.post('/chat/completions', headers=headers, json=payload)

        if response.status_code >= 400:
            raise AppError(502, 'agent_backend_error', f'模型接口调用失败: HTTP {response.status_code}')

        body = response.json()
        content = self._extract_content(body)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AppError(502, 'agent_response_invalid', '模型返回的内容不是有效 JSON。') from exc

        return ThemeStrategyAgentResponseView.model_validate(parsed)

    def _build_messages(
        self,
        *,
        request: ThemeStrategyAgentRequestView,
        themes: list[ThemeHeatView],
    ) -> list[dict[str, Any]]:
        theme_lines = self._summarize_themes(themes)
        market_lines = self._summarize_supported_markets()
        tool_lines = [f"- {item['name']}: {item['description']}" for item in self.DEFAULT_TOOL_CATALOG]
        skill_lines = [f"- {item['name']}: {item['description']}" for item in self.DEFAULT_SKILL_CATALOG]
        conversation_lines = [f'{message.role}: {message.content}' for message in request.conversation]

        system_prompt = (
            '你是量化交易系统里的热门题材策略智能体，负责和客户对话并生成新的题材策略。'
            '你必须基于当前热门题材快照、支持的市场清单、客户问题、后端预置工具和后端预置 skill 生成结构化建议。'
            '当客户要求把题材扩展到不同国家或不同股市时，优先使用 skill theme-market-mapper，'
            '并在 market_targets 中输出可直接用于后续查股 API 的市场代码清单。'
            '只输出 JSON，不要输出 Markdown、代码块或解释性前后缀。'
            '所有 recommended_tools、recommended_skills 和 market_targets 必须来自后端预置清单和支持市场清单。'
            'patch 的 additions / boosts / suppressions 最好只包含当前题材快照里出现的题材名称，'
            '如果客户明确要求新增题材，才可以放入新增项。'
        )

        user_prompt = '\n'.join(
            [
                f'客户选择的市场: {request.selected_market}',
                '当前热门题材快照:',
                *theme_lines,
                '支持的市场清单:',
                *market_lines,
                '后端预置工具:',
                *tool_lines,
                '后端预置 skill:',
                *skill_lines,
                '对话历史:',
                *(conversation_lines or ['- 无']),
                f'客户最新需求: {request.message}',
                '',
                '请返回以下 JSON 结构:',
                '{',
                '  "assistant_message": "...",',
                '  "strategy_name": "...",',
                '  "strategy_description": "...",',
                '  "patch": {"additions": [], "boosts": [], "suppressions": []},',
                '  "market_targets": [{"market_code": "...", "country_code": "...", "reason": "..."}],',
                '  "recommended_tools": [{"name": "...", "reason": "..."}],',
                '  "recommended_skills": [{"name": "...", "reason": "..."}],',
                '  "follow_up_questions": ["..."],',
                '  "model": "' + self._model + '",',
                '  "theme_snapshot_count": 0',
                '}',
            ]
        )

        return [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]

    def _summarize_themes(self, themes: list[ThemeHeatView]) -> list[str]:
        rows = sorted(themes, key=lambda item: item.smoothed_heat_score, reverse=True)[:8]
        if not rows:
            return ['- 暂无热门题材快照']
        return [
            f'- {index}. {item.theme_name} | 热度 {item.smoothed_heat_score} | 成分 {item.constituent_count} | 市场 {item.market_code}'
            for index, item in enumerate(rows, start=1)
        ]

    def _summarize_supported_markets(self) -> list[str]:
        if not self._markets_config or not self._markets_config.markets:
            return ['- 暂无支持市场清单']
        rows = sorted(self._markets_config.markets, key=lambda item: item.market_code)
        return [
            f'- {item.market_code} | {item.market_name} | country {item.country_code} | region {item.region}'
            for item in rows
        ]

    def _extract_content(self, body: dict[str, Any]) -> str:
        choices = body.get('choices') or []
        if not choices:
            raise AppError(502, 'agent_response_invalid', '模型接口没有返回 choices。')
        message = choices[0].get('message') or {}
        content = message.get('content')
        if not isinstance(content, str) or not content.strip():
            raise AppError(502, 'agent_response_invalid', '模型接口没有返回可解析的 message.content。')
        return content
