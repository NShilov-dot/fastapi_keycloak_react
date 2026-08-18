from fastapi import APIRouter

from app.api.v1 import auth, health, signup
from app.api.v1.admin import router as admin_router
from app.api.v1.tasks import router as tasks_router

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(signup.router)
router.include_router(tasks_router)
router.include_router(admin_router)
