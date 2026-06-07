from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, HealthView
from packages.shared.container import get_container

router = APIRouter()


@router.get('/health', response_model=ApiSuccess[HealthView])
def health() -> ApiSuccess[HealthView]:
    container = get_container()
    refdata_backend = getattr(container.refdata_repository, 'backend_name', 'unknown')
    feature_backend = getattr(container.market_data_repository, 'backend_name', 'unknown')
    regime_backend = getattr(container.regime_repository, 'backend_name', 'unknown')
    selection_backend = getattr(container.selection_repository, 'backend_name', 'unknown')
    trading_backend = getattr(container.trading_repository, 'backend_name', 'unknown')
    return ApiSuccess(
        data=HealthView(
            status='ok',
            services={
                'api_gateway': 'up',
                'refdata_service': f'{refdata_backend}_ready',
                'market_data_service': f'{container.market_data_service.source_mode}_{feature_backend}',
                'regime_service': f'{regime_backend}_ready',
                'selection_service': f'{container.selection_service.source_mode}_{selection_backend}',
                'trading_service': f'{container.trading_service.source_mode}_{trading_backend}',
            },
            market_count=len(container.refdata_service.list_markets()),
        )
    )
