from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any

from app.services.conductor import conductor_instance, HandoffContract

router = APIRouter(prefix="/agent", tags=["agent"])

class AgentOffloadRequest(BaseModel):
    thought_id: str
    instructions: str
    thought_data: Dict[str, Any]

@router.post("/offload", response_model=HandoffContract)
async def offload_task_to_agent(request: AgentOffloadRequest):
    """
    Receives a task from the UI and hands it off to the Zephyr Master Conductor.
    """
    try:
        contract = conductor_instance.receive_task(
            thought_id=request.thought_id,
            instructions=request.instructions,
            thought_data=request.thought_data
        )
        return contract
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
