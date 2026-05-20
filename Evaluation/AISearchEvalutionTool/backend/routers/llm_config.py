from fastapi import APIRouter, HTTPException
from models import LLMConfigUpdate, LLMConfigResponse
from db.database import get_app, get_llm_configs, upsert_llm_config

router = APIRouter(prefix="/apps/{app_id}/llm-config", tags=["llm-config"])

VALID_AGENTS = {"agent1", "agent2", "agent3", "judge", "filter_generator", "insights"}


@router.get("", response_model=list[LLMConfigResponse])
def get_llm_config(app_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return get_llm_configs(app_id)


@router.put("/{agent_name}", response_model=LLMConfigResponse)
def update_llm_config(app_id: str, agent_name: str, body: LLMConfigUpdate):
    if agent_name not in VALID_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {VALID_AGENTS}")
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return upsert_llm_config(app_id, agent_name, body.model_dump())
