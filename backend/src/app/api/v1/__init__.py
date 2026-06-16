from fastapi import APIRouter

from app.api.v1 import health
from app.modules.tasks.interface.router import router as tasks_router

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(tasks_router)
