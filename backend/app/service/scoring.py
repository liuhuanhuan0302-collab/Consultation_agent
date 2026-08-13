"""
评分引擎 — 核心算法模块，纯函数无副作用。

评分流程：
  1. 每模块得分 = (模块实际得分 / 模块题目总分) × 模块满分
  2. 总分 = 参与答题的各模块得分之和，满分随实际题库动态计算
  3. 总分等级按得分率换算：≤25% 高风险 / ≤50% 较弱 / ≤75% 良好 / >75% 优秀
  4. 维度等级：<0.25 高风险 / <0.50 较弱 / <0.75 良好 / ≥0.75 优秀

注意：题目原始分值可能 ≠ 4（某些模块做了压缩），
     因此先按实际可能总分归一化，再乘以模块满分做加权。
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# 默认总分满分，用于兼容既有规则；实际评分时由参与答题的模块动态计算。
TOTAL_MAX_SCORE = 260

@dataclass(frozen=True)
class QuestionScoreSpec:
    """题目输入规格 — 评分时传入"""
    id: int
    module_id: int
    max_score: int  # 本题最高分，通常为 4


@dataclass(frozen=True)
class ModuleScoreSpec:
    """模块输入规格 — 评分时传入"""
    id: int
    code: str
    name: str
    max_score: int  # 模块满分（加权后的显示分值）


@dataclass(frozen=True)
class DimensionScoreResult:
    """单维度评分结果"""
    module_id: int
    module_code: str
    module_name: str
    raw_score: int     # 加权后的实际得分
    max_score: int     # 模块满分
    score_rate: float  # 得分率 0-1
    risk_level: str    # 风险等级


@dataclass(frozen=True)
class ScoreResult:
    """完整评分结果"""
    total_score: int
    max_score: int      # 参与答题模块的满分之和
    score_rate: float   # 综合得分率
    risk_level: str
    dimensions: list[DimensionScoreResult]


def classify_total_score(score: int, max_score: int = TOTAL_MAX_SCORE) -> str:
    """总分 -> 风险等级（按当前问卷满分等比例换算，兼容历史 260 分阈值）。"""
    rate = score / max_score if max_score else 0
    if rate <= 0.25:
        return "高风险"
    if rate <= 0.5:
        return "较弱"
    if rate <= 0.75:
        return "良好"
    return "优秀"


def classify_dimension_rate(rate: float) -> str:
    """维度得分率 -> 风险等级。"""
    if rate < 0.25:
        return "高风险"
    if rate < 0.5:
        return "较弱"
    if rate < 0.75:
        return "良好"
    return "优秀"


def compute_scores(
    modules: list[ModuleScoreSpec],
    questions: list[QuestionScoreSpec],
    answers: dict[int, int],
) -> ScoreResult:
    """
    核心评分算法。

    输入：
      modules   — 全部 10 个模块
      questions — 全部 68 题
      answers   — {question_id: score}，score 范围 0-4

    返回：ScoreResult 包含总分、得分率、风险等级、10 维度明细。

    算法：
      对每个模块：
        ① 累计该模块内所有题目的实际可能总分（各题 max_score 之和）
        ② 累计该模块内所有题目的实际得分（截断到题目 max_score）
        ③ 模块得分 = (② / ①) × 模块满分，四舍五入
      总分 = 各模块得分之和
    """
    question_map = {question.id: question for question in questions}
    missing = sorted(set(question_map) - set(answers))
    if missing:
        raise ValueError(f"Missing answers for question ids: {missing}")

    # 初始化各模块的实际得分和可能总分
    module_input_scores = {module.id: 0 for module in modules}
    module_possible_scores = {module.id: 0 for module in modules}
    for question in questions:
        module_possible_scores[question.module_id] += question.max_score

    # 累加每题得分（截断到题目 max_score，防止异常数据）
    for question_id, answer_score in answers.items():
        if question_id not in question_map:
            raise ValueError(f"Unknown question id: {question_id}")
        question = question_map[question_id]
        if answer_score < 0 or answer_score > 4:
            raise ValueError(f"Invalid score for question id {question_id}: {answer_score}")
        module_input_scores[question.module_id] += min(answer_score, question.max_score)

    # 按模块计算加权得分
    dimensions: list[DimensionScoreResult] = []
    for module in modules:
        possible_score = module_possible_scores[module.id] or module.max_score
        # 归一化：实际得分 / 可能总分 × 模块满分
        weighted = Decimal(module_input_scores[module.id]) * Decimal(module.max_score) / Decimal(possible_score)
        raw_score = int(weighted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        rate = round(raw_score / module.max_score, 4) if module.max_score else 0
        dimensions.append(
            DimensionScoreResult(
                module_id=module.id,
                module_code=module.code,
                module_name=module.name,
                raw_score=raw_score,
                max_score=module.max_score,
                score_rate=rate,
                risk_level=classify_dimension_rate(rate),
            )
        )

    total = sum(dimension.raw_score for dimension in dimensions)
    total_max_score = sum(module.max_score for module in modules)
    rate = round(total / total_max_score, 4) if total_max_score else 0
    return ScoreResult(
        total_score=total,
        max_score=total_max_score,
        score_rate=rate,
        risk_level=classify_total_score(total, total_max_score),
        dimensions=dimensions,
    )
