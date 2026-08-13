import pytest

from app.service.scoring import ModuleScoreSpec, QuestionScoreSpec, classify_total_score, compute_scores
from app.seed import MODULES, distribute_question_max_scores


def build_specs():
    modules = []
    questions = []
    question_id = 1
    for module_id, (code, name, _description, max_score, _sort_order, question_count) in enumerate(MODULES, start=1):
        modules.append(ModuleScoreSpec(module_id, code, name, max_score))
        for max_question_score in distribute_question_max_scores(question_count, max_score):
            questions.append(QuestionScoreSpec(question_id, module_id, max_question_score))
            question_id += 1
    return modules, questions


def test_full_score_is_260_and_excellent():
    modules, questions = build_specs()
    answers = {question.id: 4 for question in questions}

    result = compute_scores(modules, questions, answers)

    assert result.total_score == 260
    assert result.max_score == 260
    assert result.risk_level == "优秀"
    assert len(result.dimensions) == 10


def test_total_max_score_follows_the_included_question_banks():
    modules = [
        ModuleScoreSpec(1, "M01", "题库一", 28),
        ModuleScoreSpec(2, "M02", "题库二", 24),
    ]
    questions = [
        QuestionScoreSpec(1, 1, 4),
        QuestionScoreSpec(2, 2, 4),
    ]

    result = compute_scores(modules, questions, {1: 4, 2: 4})

    assert result.total_score == 52
    assert result.max_score == 52
    assert result.score_rate == 1


@pytest.mark.parametrize(
    ("score", "level"),
    [(0, "高风险"), (65, "高风险"), (66, "较弱"), (130, "较弱"), (131, "良好"), (195, "良好"), (196, "优秀")],
)
def test_total_score_thresholds(score, level):
    assert classify_total_score(score) == level


def test_missing_answer_is_rejected():
    modules, questions = build_specs()
    answers = {question.id: 2 for question in questions[:-1]}

    with pytest.raises(ValueError):
        compute_scores(modules, questions, answers)
