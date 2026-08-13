"""
诊断服务 — 答卷保存、评分编排、线索等级判定。

评分编排流程：
  1. 从 DB 加载题目和答案
  2. 调用 compute_scores() 做规则评分
  3. 删除旧维度分数 → 写入新维度分数
  4. 更新提交状态和总分
  5. 根据评分结果 + 联系方式计算线索等级
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CompanyLead,
    DimensionScore,
    Question,
    QuestionAnswer,
    SubmissionStatus,
)
from app.repositories.consult_repo import (
    delete_dimension_scores,
    get_answer_map,
    get_existing_answers,
    get_submission_by_id,
)
from app.repositories.questionnaire_repo import active_modules_with_questions
from app.schemas import DimensionScoreRead, ScoreResponse
from app.service.scoring import ModuleScoreSpec, QuestionScoreSpec, compute_scores
from app.utils.time_utils import utc_now


def serialize_score(submission_id: int, score_result) -> ScoreResponse:
    """将评分 dataclass 转为 API 响应格式，取得分率最低的 3 个维度作为短板。"""
    dimensions = [
        DimensionScoreRead(
            module_code=item.module_code,
            module_name=item.module_name,
            raw_score=item.raw_score,
            max_score=item.max_score,
            score_rate=item.score_rate,
            risk_level=item.risk_level,
        )
        for item in score_result.dimensions
    ]
    return ScoreResponse(
        submission_id=submission_id,
        total_score=score_result.total_score,
        max_score=score_result.max_score,
        score_rate=score_result.score_rate,
        risk_level=score_result.risk_level,
        low_dimensions=sorted(dimensions, key=lambda item: item.score_rate)[:3],
        dimensions=dimensions,
    )


def persist_answers(db: Session, submission_id: int, answers: list) -> None:
    """
    保存/更新答卷。
    question_id 已存在则覆盖分数，不存在则新增。
    """
    question_ids = {answer.question_id for answer in answers}
    existing_map = get_existing_answers(db, submission_id, question_ids)
    for answer in answers:
        if answer.question_id in existing_map:
            existing_map[answer.question_id].score = answer.score
        else:
            db.add(QuestionAnswer(submission_id=submission_id, question_id=answer.question_id, score=answer.score))
    db.flush()


def calculate_lead_level(lead: CompanyLead, score_result) -> str:
    """
    线索等级判定：
      有联系方式 + 至少 2 个维度得分率 < 0.5 → high（高意向）
      有联系方式 → medium（中意向）
      无联系方式 → low（低意向）

    TODO: 当前规则较为简单，后续可引入行业权重、企业规模、营收等维度做更精准评分。
    """
    has_contact = bool(lead.phone or lead.wechat)
    low_dimension_count = len([item for item in score_result.dimensions if item.score_rate < 0.5])
    if has_contact and low_dimension_count >= 2:
        return "high"
    if has_contact:
        return "medium"
    return "low"


def summarize_customer_demand(lead: CompanyLead, score_result) -> str:
    """沉淀客户诉求，优先使用客户填写内容，缺省时根据低分维度生成。"""
    if lead.ai_focus and lead.ai_focus.strip():
        return lead.ai_focus.strip()
    low_dimensions = sorted(score_result.dimensions, key=lambda item: item.score_rate)[:3]
    low_names = "、".join(item.module_name for item in low_dimensions)
    return f"客户暂未填写明确 AI 诉求，当前建议优先关注：{low_names}。"


def score_submission(db: Session, submission_id: int) -> ScoreResponse:
    """
    评分编排函数 — 问卷提交后的核心处理。
    ① 校验提交存在
    ② 加载模块/题目/答案
    ③ 调用评分引擎
    ④ 写入维度得分和总分
    ⑤ 更新线索等级
    """
    db_submission = get_submission_by_id(db, submission_id)
    if not db_submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    answer_map = get_answer_map(db, submission_id)
    modules = active_modules_with_questions(db)
    questions = [
        question
        for module in modules
        for question in sorted(module.questions, key=lambda item: item.sort_order)
        if question.is_active
    ]
    try:
        score_result = compute_scores(
            [ModuleScoreSpec(module.id, module.code, module.name, module.max_score) for module in modules],
            [QuestionScoreSpec(question.id, question.module_id, question.max_score) for question in questions],
            answer_map,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 清除旧维度分数，写入新数据
    delete_dimension_scores(db, submission_id)
    for item in score_result.dimensions:
        db.add(
            DimensionScore(
                submission_id=submission_id,
                module_id=item.module_id,
                raw_score=item.raw_score,
                max_score=item.max_score,
                score_rate=item.score_rate,
                risk_level=item.risk_level,
            )
        )
    db_submission.total_score = score_result.total_score
    db_submission.max_score = score_result.max_score
    db_submission.score_rate = score_result.score_rate
    db_submission.risk_level = score_result.risk_level
    db_submission.status = SubmissionStatus.scored.value
    db_submission.submitted_at = db_submission.submitted_at or utc_now()
    # 更新线索等级
    db_submission.lead.lead_level = calculate_lead_level(db_submission.lead, score_result)
    db_submission.lead.demand_summary = summarize_customer_demand(db_submission.lead, score_result)
    db.flush()
    return serialize_score(submission_id, score_result)
