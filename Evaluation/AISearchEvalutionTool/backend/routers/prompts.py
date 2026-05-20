from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from models import PromptConfigCreate, PromptConfigResponse
from db.database import get_active_prompt, get_app, get_prompts, save_prompt
from agents.prompts import DEFAULT_PROMPTS

router = APIRouter(prefix="/apps/{app_id}/prompts", tags=["prompts"])

VALID_AGENTS = {"agent1", "agent2", "agent3", "judge"}


@router.get("", response_model=list[PromptConfigResponse])
def list_prompts(app_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return get_prompts(app_id)


@router.get("/defaults")
def get_default_prompts():
    return DEFAULT_PROMPTS


@router.get("/{agent_name}/active", response_model=PromptConfigResponse)
def get_active(app_id: str, agent_name: str):
    if agent_name not in VALID_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {VALID_AGENTS}")
    row = get_active_prompt(app_id, agent_name)
    if not row:
        raise HTTPException(404, "No active prompt found")
    return row


@router.put("/{agent_name}", response_model=PromptConfigResponse)
def update_prompt(app_id: str, agent_name: str, body: PromptConfigCreate):
    if agent_name not in VALID_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {VALID_AGENTS}")
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return save_prompt(app_id, agent_name, body.prompt_text)


@router.post("/{agent_name}/upload", response_model=PromptConfigResponse)
async def upload_prompt(app_id: str, agent_name: str, file: UploadFile = File(...)):
    if agent_name not in VALID_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {VALID_AGENTS}")
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    content = await file.read()
    prompt_text = content.decode("utf-8")
    return save_prompt(app_id, agent_name, prompt_text)


@router.post("/{agent_name}/reset", response_model=PromptConfigResponse)
def reset_prompt(app_id: str, agent_name: str):
    if agent_name not in VALID_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {VALID_AGENTS}")
    default = DEFAULT_PROMPTS.get(agent_name)
    if not default:
        raise HTTPException(404, "No default prompt for this agent")
    return save_prompt(app_id, agent_name, default)
