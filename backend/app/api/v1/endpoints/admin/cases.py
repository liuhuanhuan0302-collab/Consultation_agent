"""AI 场景案例 — 列表 / 新增。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CaseStudy, User
from app.repositories.case_repo import list_case_studies
from app.schemas import CaseStudyCreate, CaseStudyRead
from app.utils.auth import ContentManager, LeadViewer
from app.utils.logging_utils import write_operation_log

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.11 案例列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/cases
# 功能：查看所有 AI 场景案例
# 鉴权：admin / operator / sales / consultant
# 返回：CaseStudyRead[] 数组
@router.get("/api/admin/cases", response_model=list[CaseStudyRead])
def list_cases(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[CaseStudy]:
    return list_case_studies(db)


# ══════════════════════════════════════════════════════════════════
# 3.12 新增案例
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/cases
# 功能：创建新的 AI 场景案例（用于报告中的推荐匹配）
#       案例按 module_code 匹配低分维度，按 industry 匹配客户行业
# 鉴权：admin / operator
# 请求：{ title*, industry*, function_area*, module_code*,
#          maturity?, roi_level?, difficulty?, description*,
#          expected_benefit*, priority_tag?, is_active? }
# 返回：案例对象
@router.post("/api/admin/cases", response_model=CaseStudyRead)
def create_case(payload: CaseStudyCreate, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> CaseStudy:
    case = CaseStudy(**payload.model_dump())
    db.add(case)
    write_operation_log(db, user, "create_case", "case", payload.title)
    db.commit()
    db.refresh(case)
    return case
