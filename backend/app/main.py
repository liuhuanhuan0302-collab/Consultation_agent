import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db import get_db, init_db
from app.seed import seed_initial_data
from app.utils.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s")

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if not settings.secret_key or settings.secret_key == "change-me-before-production":
        raise RuntimeError("SECRET_KEY 未设置或仍为默认值，请在 .env 中设置强随机密钥")
    if settings.environment == "production" and settings.database_url.startswith("sqlite"):
        raise RuntimeError("生产环境禁止使用 SQLite，请配置 MySQL/RDS 数据库")
    init_db()
    db = next(get_db())
    try:
        seed_initial_data(db)
    finally:
        db.close()
    if settings.environment == "development":
        # 开发环境没有独立的 report_worker 进程，直接在 API 进程内启动队列消费者，
        # 避免服务重启后报告任务无人处理、客户永久停留在等待页。
        from app.service.report_queue import run_report_delivery_worker

        loop = asyncio.get_event_loop()
        app.state.report_worker_task = loop.create_task(run_report_delivery_worker())
    logging.getLogger(__name__).info("应用启动完成，环境: %s", settings.environment)


@app.on_event("shutdown")
def shutdown() -> None:
    task = getattr(app.state, "report_worker_task", None)
    if task is not None:
        task.cancel()


register_exception_handlers(app)
app.state.limiter = Limiter(key_func=get_remote_address)
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(api_router)
