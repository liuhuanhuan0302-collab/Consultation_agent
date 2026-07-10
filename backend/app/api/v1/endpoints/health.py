"""
系统健康检查 — K8s / Docker 探活用，无需鉴权。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db


router = APIRouter()


# ── GET /api/health ─────────────────────────────────────────────
# 功能：返回服务状态 + 数据库连通性
# 鉴权：无
# 返回：{ status: "ok"|"degraded", environment, database: "ok"|"unavailable" }
@router.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "environment": get_settings().environment,
        "database": db_status,
    }
