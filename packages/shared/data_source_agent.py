from __future__ import annotations

import re
from pathlib import Path

from packages.shared.api_models import DataSourceAgentRequestView, DataSourceAgentResponseView, DataSourceCatalogView, DataSourceEntryView, DataSourceRetryView, DataSourceTimeoutsView
from packages.shared.config import dump_yaml
from packages.shared.errors import AppError
from packages.shared.settings import DataSourcesConfig, SourceSettings, load_data_sources_config


class DataSourceAgentService:
    MODEL_NAME = 'local-data-source-agent'

    def __init__(self, *, config_path: Path) -> None:
        self._config_path = Path(config_path)

    def list_catalog(self) -> DataSourceCatalogView:
        config = load_data_sources_config(self._config_path)
        return self._build_catalog(config)

    def add_source_from_dialog(self, request: DataSourceAgentRequestView) -> DataSourceAgentResponseView:
        config = load_data_sources_config(self._config_path)
        parsed = self._parse_request(request)
        config.sources[parsed.name] = SourceSettings(
            primary=parsed.primary,
            fallback=parsed.fallback,
            backup=parsed.backup,
        )
        self._persist(config)
        catalog = self._build_catalog(config)
        assistant_message = (
            f'已添加数据源 {parsed.name}。当前主源为 {parsed.primary}'
            + (f'，fallback 为 {parsed.fallback}' if parsed.fallback else '')
            + (f'，backup 为 {parsed.backup}' if parsed.backup else '')
            + '。'
        )
        return DataSourceAgentResponseView(
            assistant_message=assistant_message,
            saved_source=parsed,
            source_count=len(catalog.sources),
            follow_up_questions=['是否还要继续补充另一个 source key，或调整 timeouts / retry？'],
            model=self.MODEL_NAME,
        )

    def _parse_request(self, request: DataSourceAgentRequestView) -> DataSourceEntryView:
        combined = "\n".join([*(message.content for message in request.conversation), request.message])
        name = self._extract(r'(?:新增|添加|增加)(?:一个)?数据源\s*([A-Za-z0-9_-]+)', combined)
        if not name:
            name = self._extract(r'数据源\s*([A-Za-z0-9_-]+)', combined)
        primary = self._extract(r'(?:主源|primary)\s*[:：=]?\s*([A-Za-z0-9_-]+)', combined)
        fallback = self._extract(r'(?:fallback|备用|备源|次源)\s*[:：=]?\s*([A-Za-z0-9_-]+)', combined)
        backup = self._extract(r'(?:backup|备份)\s*[:：=]?\s*([A-Za-z0-9_-]+)', combined)

        if not name:
            raise AppError(422, 'data_source_name_missing', '没有识别到数据源名称，请明确说明“新增数据源 xxx”。')
        if not primary:
            raise AppError(422, 'data_source_primary_missing', '没有识别到主源，请明确说明“主源 yfinance”。')

        return DataSourceEntryView(name=name, primary=primary, fallback=fallback, backup=backup)

    def _persist(self, config: DataSourcesConfig) -> None:
        payload = {
            'sources': {
                name: {
                    'primary': settings.primary,
                    **({'fallback': settings.fallback} if settings.fallback else {}),
                    **({'backup': settings.backup} if settings.backup else {}),
                }
                for name, settings in config.sources.items()
            },
            'timeouts': {
                'connect_seconds': config.timeouts.connect_seconds,
                'read_seconds': config.timeouts.read_seconds,
            },
            'retry': {
                'max_attempts': config.retry.max_attempts,
                'backoff_seconds': config.retry.backoff_seconds,
            },
        }
        dump_yaml(self._config_path, payload)

    def _build_catalog(self, config: DataSourcesConfig) -> DataSourceCatalogView:
        return DataSourceCatalogView(
            sources=[
                DataSourceEntryView(
                    name=name,
                    primary=settings.primary,
                    fallback=settings.fallback,
                    backup=settings.backup,
                )
                for name, settings in sorted(config.sources.items())
            ],
            timeouts=DataSourceTimeoutsView(
                connect_seconds=config.timeouts.connect_seconds,
                read_seconds=config.timeouts.read_seconds,
            ),
            retry=DataSourceRetryView(
                max_attempts=config.retry.max_attempts,
                backoff_seconds=config.retry.backoff_seconds,
            ),
        )

    def _extract(self, pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1)
