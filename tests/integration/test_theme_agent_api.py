import os
import unittest

from pydantic import BaseModel, Field
from fastapi.testclient import TestClient

from apps.api_gateway.main import app
from packages.shared.container import get_container, reset_container


class ThemeAgentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_provider = os.environ.get('QUANT_MARKET_DATA_PROVIDER')
        os.environ['QUANT_MARKET_DATA_PROVIDER'] = 'mock'
        reset_container()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self._original_provider is None:
            os.environ.pop('QUANT_MARKET_DATA_PROVIDER', None)
        else:
            os.environ['QUANT_MARKET_DATA_PROVIDER'] = self._original_provider
        reset_container()

    def test_theme_agent_endpoint_returns_model_plan(self) -> None:
        class FakeThemeAgentResponse(BaseModel):
            assistant_message: str = '已生成策略建议。'
            strategy_name: str = '客户对话策略 1'
            strategy_description: str = '围绕半导体和机器人做热度抬升。'
            patch: dict[str, list[str]] = Field(
                default_factory=lambda: {
                    'additions': ['机器人'],
                    'boosts': ['半导体'],
                    'suppressions': ['煤炭'],
                }
            )
            market_targets: list[dict[str, str]] = Field(
                default_factory=lambda: [
                    {'market_code': 'US_EQ', 'country_code': 'US', 'reason': '美股通常是全球题材定价中心。'}
                ]
            )
            recommended_tools: list[dict[str, str]] = Field(
                default_factory=lambda: [{'name': 'theme_context_reader', 'reason': '读取当前题材快照。'}]
            )
            recommended_skills: list[dict[str, str]] = Field(
                default_factory=lambda: [{'name': 'hot-theme-rotation', 'reason': '处理题材轮动。'}]
            )
            follow_up_questions: list[str] = Field(default_factory=list)
            model: str = 'gpt-5.4'
            theme_snapshot_count: int = 1

        class FakeThemeAgentService:
            def compose_theme_strategy(self, request, themes):
                self.last_request = request
                self.last_themes = themes
                return FakeThemeAgentResponse()

        get_container().theme_strategy_agent_service = FakeThemeAgentService()

        response = self.client.post(
            '/agent/themes/compose',
            json={
                'selected_market': 'ALL',
                'message': '给我一个更偏进攻的热门题材策略。',
                'conversation': [{'role': 'user', 'content': '先看热门题材'}],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['strategy_name'], '客户对话策略 1')
        self.assertEqual(payload['data']['patch']['boosts'], ['半导体'])
        self.assertEqual(payload['data']['market_targets'][0]['market_code'], 'US_EQ')
        self.assertEqual(payload['data']['recommended_tools'][0]['name'], 'theme_context_reader')
        self.assertEqual(payload['data']['recommended_skills'][0]['name'], 'hot-theme-rotation')


if __name__ == '__main__':
    unittest.main()
