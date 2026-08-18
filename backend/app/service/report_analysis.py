"""诊断报告分析数据组装，基于本次提交的实际题库生成。"""

from app.models import DimensionScore, Report


def build_question_scores(report: Report) -> list[dict]:
    """输出本次答卷全部题项得分，供报告图表和证据表使用。"""
    answers = sorted(
        report.submission.answers,
        key=lambda item: (item.question.module.sort_order, item.question.sort_order, item.question.code),
    )
    return [
        {
            "question_code": answer.question.code,
            "question_text": answer.question.text,
            "module_code": answer.question.module.code,
            "module_name": answer.question.module.name,
            "score": answer.score,
            "max_score": answer.question.max_score,
            "score_rate": answer.score / answer.question.max_score if answer.question.max_score else 0,
        }
        for answer in answers
    ]


def build_core_findings(dimensions: list[DimensionScore], question_scores: list[dict]) -> list[dict]:
    """根据最低得分维度及对应题项生成可追溯的管理层发现。"""
    questions_by_module: dict[str, list[dict]] = {}
    for item in question_scores:
        questions_by_module.setdefault(item["module_code"], []).append(item)
    for items in questions_by_module.values():
        items.sort(key=lambda item: (item["score_rate"], item["question_code"]))

    findings: list[dict] = []
    for dimension in sorted(dimensions, key=lambda item: item.score_rate)[:3]:
        module_questions = questions_by_module.get(dimension.module.code, [])
        weakest_question = module_questions[0] if module_questions else None
        dimension_rate = round(dimension.score_rate * 100)
        if weakest_question:
            question_rate = round(float(weakest_question["score_rate"]) * 100)
            evidence = (
                f'{weakest_question["question_code"]}「{weakest_question["question_text"]}」'
                f'得分 {weakest_question["score"]}/{weakest_question["max_score"]}（{question_rate}%）；'
                f'{dimension.module.name}维度得分率为 {dimension_rate}%。'
            )
        else:
            evidence = f'{dimension.module.name}维度得分 {dimension.raw_score}/{dimension.max_score}，得分率为 {dimension_rate}%。'
        findings.append(
            {
                "finding": f"{dimension.module.name}是当前最需要优先补齐的环节",
                "evidence": evidence,
                "meaning": (
                    f"该结果反映企业在{dimension.module.name}相关基础上仍有改进空间；"
                    "建议在后续访谈中确认具体业务场景、责任分工和可用数据，再确定 AI 试点切入点。"
                ),
            }
        )
    return findings
