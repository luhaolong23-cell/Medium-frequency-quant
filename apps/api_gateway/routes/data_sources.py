from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, DataSourceCatalogView
from packages.shared.container import get_container

router = APIRouter(prefix='/data-sources', tags=['data-sources'])


@router.get('', response_model=ApiSuccess[DataSourceCatalogView])
def list_data_sources() -> ApiSuccess[DataSourceCatalogView]:
    return ApiSuccess(data=get_container().data_source_agent_service.list_catalog())
