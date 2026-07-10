import argparse
import re
import sys
from pathlib import Path

import openpyxl

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import get_db, init_db
from app.models import Question, QuestionModule
from app.seed import MODULES


WEIGHTED_MAX_BY_SORT = {sort_order: max_score for _code, _name, _description, max_score, sort_order, _count in MODULES}


def parse_ints(value: object) -> list[int]:
    return [int(item) for item in re.findall(r"[0-9]+", str(value or ""))]


def iter_question_sheets(workbook):
    for worksheet in workbook.worksheets:
        if worksheet.title and worksheet.title[0].isdigit() and worksheet.title[0] != "0":
            yield worksheet


def read_workbook(path: Path) -> list[dict]:
    workbook = openpyxl.load_workbook(path, data_only=True)
    modules: list[dict] = []
    for sort_order, worksheet in enumerate(iter_question_sheets(workbook), start=1):
        title = str(worksheet["B2"].value or worksheet.title).strip()
        description = str(worksheet["B4"].value or "").strip()
        weighted_max = WEIGHTED_MAX_BY_SORT.get(sort_order)
        if not weighted_max:
            raise ValueError(f"No score weight configured for sheet {worksheet.title}")

        questions = []
        for index, row in enumerate(worksheet.iter_rows(min_row=8, values_only=True), start=1):
            question_code = row[1]
            if not question_code or not str(question_code).startswith("Q"):
                continue
            score_numbers = parse_ints(row[5])
            questions.append(
                {
                    "code": str(question_code).strip(),
                    "dimension": str(row[2] or "").strip(),
                    "text": str(row[3] or "").strip(),
                    "option_text": str(row[4] or "").strip(),
                    "max_score": score_numbers[-1] if score_numbers else 4,
                    "sort_order": len(questions) + 1,
                }
            )

        if not questions:
            raise ValueError(f"No questions found in sheet {worksheet.title}")

        modules.append(
            {
                "code": f"M{sort_order:02d}",
                "name": title,
                "description": description,
                "max_score": weighted_max,
                "sort_order": sort_order,
                "questions": questions,
            }
        )
    return modules


def import_questionnaire(path: Path) -> tuple[int, int]:
    modules = read_workbook(path)
    init_db()
    db = next(get_db())
    try:
        imported_question_count = 0
        for module_data in modules:
            module = db.query(QuestionModule).filter(QuestionModule.code == module_data["code"]).first()
            if not module:
                module = QuestionModule(code=module_data["code"])
                db.add(module)
                db.flush()

            module.name = module_data["name"]
            module.description = module_data["description"]
            module.max_score = module_data["max_score"]
            module.sort_order = module_data["sort_order"]
            module.is_active = True

            imported_codes = {question["code"] for question in module_data["questions"]}
            db.query(Question).filter(Question.module_id == module.id, ~Question.code.in_(imported_codes)).update(
                {"is_active": False}, synchronize_session=False
            )

            for question_data in module_data["questions"]:
                question = db.query(Question).filter(Question.module_id == module.id, Question.code == question_data["code"]).first()
                if not question:
                    question = Question(module_id=module.id, code=question_data["code"])
                    db.add(question)
                question.dimension = question_data["dimension"]
                question.text = question_data["text"]
                question.option_text = question_data["option_text"]
                question.max_score = question_data["max_score"]
                question.sort_order = question_data["sort_order"]
                question.is_active = True
                imported_question_count += 1

        db.commit()
        return len(modules), imported_question_count
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the official questionnaire workbook.")
    parser.add_argument("path", type=Path, help="Path to 智简组织转型准备度诊断问卷.xlsx")
    args = parser.parse_args()
    module_count, question_count = import_questionnaire(args.path)
    print(f"Imported {module_count} modules and {question_count} questions from {args.path}")


if __name__ == "__main__":
    main()
