from __future__ import annotations

from fastapi import APIRouter

from mattergraph_api.services.workflow_service import (
  LeMaterialDemoWorkflowResponse,
  build_lematerial_demo_workflow,
)

router = APIRouter()


@router.get(
  "/workflows/lematerial/demo",
  response_model=LeMaterialDemoWorkflowResponse,
)
def lematerial_demo_workflow() -> LeMaterialDemoWorkflowResponse:
  return build_lematerial_demo_workflow()
