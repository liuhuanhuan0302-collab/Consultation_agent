"""题库管理 — 查看 / 新增 / 更新 / 下线模块与题目。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Question, QuestionModule, User
from app.repositories.questionnaire_repo import (
    active_modules_with_questions,
    get_module_by_code,
    get_question_by_module_and_code,
    next_module_code,
    next_question_code,
)
from app.schemas import MessageResponse, ModuleRead, ModuleUpsert, QuestionRead, QuestionUpsert
from app.utils.auth import ContentManager, LeadViewer
from app.utils.logging_utils import write_operation_log

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.8 查看题库
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/questions
# 功能：查看所有模块和题目（含非激活题）
# 鉴权：admin / operator / sales / consultant
# 返回：ModuleRead[] 数组
@router.get("/api/admin/questions", response_model=list[ModuleRead])
def admin_list_questions(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[QuestionModule]:
    return active_modules_with_questions(db)


# ══════════════════════════════════════════════════════════════════
# 3.9 新增/更新模块
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/modules
# 功能：创建或更新题库模块（code 已存在则更新，不存在则新增）
# 鉴权：admin / operator
# 请求：{ code*, name*, description?, max_score*, sort_order*, is_active* }
# 返回：模块对象
@router.post("/api/admin/modules", response_model=ModuleRead)
def upsert_module(payload: ModuleUpsert, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> QuestionModule:
    module = get_module_by_code(db, payload.code)
    if not module:
        module = QuestionModule(code=payload.code)
        db.add(module)
    elif not module.is_active:
        # 已归档模块不复用原编码，避免无意中把历史题库重新激活。
        module = QuestionModule(code=next_module_code(db, payload.code))
        db.add(module)
    module.name = payload.name
    module.description = payload.description
    module.max_score = payload.max_score
    module.sort_order = payload.sort_order
    module.is_active = payload.is_active
    write_operation_log(db, user, "upsert_module", "question_module", module.code)
    db.commit()
    db.refresh(module)
    return module


# ══════════════════════════════════════════════════════════════════
# 3.10 新增/更新题目
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/questions
# 功能：在指定模块下创建或更新题目
#       code 在模块内已存在则更新，不存在则新增
# 鉴权：admin / operator
# 请求：{ module_code*, code*, dimension?, text*, option_text?,
#          sort_order*, max_score*(1-4), is_active* }
# 返回：题目对象
# 错误：404 如果 module_code 不存在
@router.post("/api/admin/questions", response_model=QuestionRead)
def upsert_question(payload: QuestionUpsert, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> Question:
    module = get_module_by_code(db, payload.module_code)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    question = get_question_by_module_and_code(db, module.id, payload.code)
    if not question:
        question = Question(module_id=module.id, code=payload.code)
        db.add(question)
    elif not question.is_active:
        # 已归档题目不复用原编码，避免无意中把历史题目重新激活。
        question = Question(module_id=module.id, code=next_question_code(db, module.id, payload.code))
        db.add(question)
    question.text = payload.text
    question.dimension = payload.dimension
    question.option_text = payload.option_text
    question.sort_order = payload.sort_order
    question.max_score = payload.max_score
    question.is_active = payload.is_active
    write_operation_log(db, user, "upsert_question", "question", question.code)
    db.commit()
    db.refresh(question)
    return question


# ══════════════════════════════════════════════════════════════════
# 3.10.1 下线题目 / 题库模块
# ══════════════════════════════════════════════════════════════════
@router.delete("/api/admin/questions/{question_id}", response_model=MessageResponse)
def archive_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> MessageResponse:
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.is_active = False
    write_operation_log(db, user, "archive_question", "question", str(question.id))
    db.commit()
    return MessageResponse(message="题目已删除，不会影响已生成的诊断报告")


@router.delete("/api/admin/modules/{module_id}", response_model=MessageResponse)
def archive_module(module_id: int, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> MessageResponse:
    module = db.query(QuestionModule).filter(QuestionModule.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    module.is_active = False
    for question in module.questions:
        question.is_active = False
    write_operation_log(db, user, "archive_question_module", "question_module", str(module.id))
    db.commit()
    return MessageResponse(message="题库已删除，不会影响已生成的诊断报告")
