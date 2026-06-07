import json
import unittest
from datetime import date

import httpx

from packages.shared.api_models import (
    AgentDialogueMessageView,
    ThemeHeatView,
    ThemeStrategyAgentRequestView,
)
from packages.shared.settings import MarketSettings, MarketsConfig
from packages.shared.theme_agent import ThemeStrategyAgentService


class ThemeStrategyAgentServiceTests(unittest.TestCase):
    def test_compose_theme_strategy_uses_openai_and_parses_json_response(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured['method'] = request.method
            captured['url'] = str(request.url)
            captured['headers'] = dict(request.headers)
            captured['payload'] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    'choices': [
                        {
                            'message': {
                                'content': json.dumps(
                                    {
                                        'assistant_message': '我会先聚焦半导体和机器人，再用增量抬升策略做跟进。',
                                        'strategy_name': '客户对话策略 1',
                                        'strategy_description': '围绕半导体、机器人和消费电子做热度抬升。',
                                        'patch': {
                                            'additions': ['机器人'],
                                            'boosts': ['半导体'],
                                            'suppressions': ['煤炭'],
                                        },
                                        'market_targets': [
                                            {'market_code': 'US_EQ', 'country_code': 'US', 'reason': '美股相关性最高。'},
                                        ],
                                        'recommended_tools': [
                                            {'name': 'theme_context_reader', 'reason': '读取当前热门题材快照。'},
                                            {'name': 'patch_builder', 'reason': '把客户要求转成增量更新。'},
                                        ],
                                        'recommended_skills': [
                                            {'name': 'hot-theme-rotation', 'reason': '处理热门题材轮动。'},
                                            {'name': 'client-dialogue', 'reason': '把客户偏好翻译成策略语言。'},
                                        ],
                                        'follow_up_questions': ['是否需要只保留已跟踪市场？'],
                                        'model': 'gpt-5.4',
                                        'theme_snapshot_count': 1,
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        service = ThemeStrategyAgentService(
            api_key='test-key',
            model='gpt-5.4',
            transport=httpx.MockTransport(handler),
            markets_config=MarketsConfig(
                markets=[
                    MarketSettings(
                        market_code='US_EQ',
                        market_name='United States Equities',
                        country_code='US',
                        region='NORTH_AMERICA',
                        proxies=[],
                    ),
                    MarketSettings(
                        market_code='JP_EQ',
                        market_name='Japan Equities',
                        country_code='JP',
                        region='ASIA',
                        proxies=[],
                    ),
                ]
            ),
        )
        request = ThemeStrategyAgentRequestView(
            selected_market='ALL',
            message='给我一个更偏进攻的热门题材策略，优先机器人和半导体。',
            conversation=[AgentDialogueMessageView(role='user', content='先看热门题材')],
        )

        themes = [
            ThemeHeatView(
                trade_date=date(2026, 5, 25),
                market_code='US_EQ',
                theme_type='industry',
                theme_name='半导体',
                raw_heat_score=7.2,
                smoothed_heat_score=7.5,
                constituent_count=15,
                source='test',
            )
        ]

        response = service.compose_theme_strategy(request=request, themes=themes)

        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['url'], 'https://api.openai.com/v1/chat/completions')
        self.assertIn('authorization', captured['headers'])
        self.assertEqual(captured['payload']['model'], 'gpt-5.4')
        self.assertEqual(captured['payload']['response_format'], {'type': 'json_object'})
        self.assertEqual(len(captured['payload']['messages']), 2)
        self.assertIn('后端预置工具', captured['payload']['messages'][1]['content'])
        self.assertIn('theme_context_reader', captured['payload']['messages'][1]['content'])
        self.assertIn('theme-market-mapper', captured['payload']['messages'][1]['content'])
        self.assertIn('支持的市场清单', captured['payload']['messages'][1]['content'])
        self.assertIn('US_EQ | United States Equities', captured['payload']['messages'][1]['content'])
        self.assertEqual(response.strategy_name, '客户对话策略 1')
        self.assertEqual(response.patch.boosts, ['半导体'])
        self.assertEqual(response.market_targets[0].market_code, 'US_EQ')
        self.assertEqual(response.recommended_tools[0].name, 'theme_context_reader')
        self.assertEqual(response.recommended_skills[0].name, 'hot-theme-rotation')


if __name__ == '__main__':
    unittest.main()
