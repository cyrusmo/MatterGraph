import pytest


@pytest.fixture(scope="module", autouse=True)
def _set_demo_data() -> None:
  from mattergraph_api.services import store_service
  from mattergraph_api.services.demo_service import get_demo_store

  store_service.reset_store(get_demo_store())
