from fastapi import APIRouter

from app.services.mirofish import mirofish_deep_swarm, mirofish_diagnostics, mirofish_predict, mirofish_status

router = APIRouter(prefix="/mirofish", tags=["mirofish"])


@router.get("/status")
def status():
    return mirofish_status()


@router.post("/predict")
async def predict(payload: dict):
    return await mirofish_predict(payload)


@router.post("/deep-swarm")
async def deep_swarm(payload: dict):
    return await mirofish_deep_swarm(payload)


@router.post("/diagnostics")
async def diagnostics(payload: dict | None = None):
    return await mirofish_diagnostics(payload or {})
