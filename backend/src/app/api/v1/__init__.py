from fastapi import APIRouter

from app.api.v1 import auth, health
from app.modules.tasks.interface.router import router as tasks_router
from app.modules.tenants.interface.router import router as admin_router

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(tasks_router)
router.include_router(admin_router)
