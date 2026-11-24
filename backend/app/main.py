"""FastAPI application entrypoint for Kirana Khata Agent."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import approvals, dashboard, inventory, khata, orders, settings as settings_router, suppliers, voice, webhooks
from app.seed import seed_database_if_empty
from app.services.telegram_poller import telegram_polling_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database_if_empty(db)
    tg_task = asyncio.create_task(telegram_polling_loop())
    try:
        yield
    finally:
        tg_task.cancel()
        try:
            await tg_task
        except asyncio.CancelledError:
            pass


settings = get_settings()

app = FastAPI(
    title="Kirana Khata Agent API",
    description="MCP-powered digital khata, inventory, and WhatsApp/Telegram operations backend for Kirana Khata Agent.",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in settings.frontend_origin.split(",")
    if origin.strip()
]
for local_origin in ("http://127.0.0.1:3000", "http://localhost:3000"):
    if local_origin not in allowed_origins:
        allowed_origins.append(local_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(orders.router)
app.include_router(khata.router)
app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(approvals.router)
app.include_router(voice.router)
app.include_router(webhooks.router)
app.include_router(settings_router.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "shop_name": settings.shop_name,
        "app_mode": settings.app_mode,
    }
