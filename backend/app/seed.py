import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CaseStudy, ChannelSource, Question, QuestionModule, ReportTemplate, Role, User
from app.utils.security import hash_password

logger = logging.getLogger(__name__)


MODULES = [
    ("M01", "一心", "以用户/客户为中心", 28, 1, 7),
    ("M02", "简化业务", "业务聚焦与差异化", 28, 2, 7),
    ("M03", "简练组织", "组织结构与协作", 26, 3, 7),
    ("M04", "简单团队", "人效与 AI 协作能力", 28, 4, 7),
    ("M05", "流程化", "流程精简与体验", 24, 5, 6),
    ("M06", "自动化", "工作流自动化", 24, 6, 6),
    ("M07", "数字化", "数据资产与指标体系", 26, 7, 7),
    ("M08", "智能化", "AI 能力嵌入业务流程", 26, 8, 7),
    ("M09", "生态化", "供应链与伙伴协同", 24, 9, 7),
    ("M10", "五差就绪度", "差异化、差距、差评、差错、差速管理", 26, 10, 7),
]

OFFICIAL_QUESTIONNAIRE_PATH = Path(__file__).resolve().parent / "data" / "official_questionnaire.json"


def distribute_question_max_scores(question_count: int, module_max_score: int) -> list[int]:
    scores = [4 for _ in range(question_count)]
    overflow = sum(scores) - module_max_score
    index = question_count - 1
    while overflow > 0 and index >= 0:
        reduce_by = min(overflow, scores[index] - 1)
        scores[index] -= reduce_by
        overflow -= reduce_by
        index -= 1
    return scores


def seed_initial_data(db: Session) -> None:
    settings = get_settings()
    if not db.query(User).first():
        if settings.environment.lower() == "production":
            if not settings.initial_admin_email or not settings.initial_admin_password:
                raise RuntimeError(
                    "生产环境首次启动必须设置 INITIAL_ADMIN_EMAIL 和 INITIAL_ADMIN_PASSWORD；"
                    "拒绝创建固定默认管理员账号"
                )
            admin_email = settings.initial_admin_email
            admin_password = settings.initial_admin_password
            admin_name = "系统管理员"
        else:
            admin_email = "admin@example.com"
            admin_password = "Admin123!"
            admin_name = "开发环境管理员"
        db.add(
            User(
                email=admin_email,
                name=admin_name,
                role=Role.admin.value,
                password_hash=hash_password(admin_password),
            )
        )
        if settings.environment.lower() == "production":
            logger.info("已使用 INITIAL_ADMIN_EMAIL 创建首个生产管理员账号")
        else:
            logger.warning("已创建开发环境演示管理员 admin@example.com / Admin123!；禁止用于生产环境")

    if not db.query(ChannelSource).filter(ChannelSource.code == "default").first():
        db.add(ChannelSource(code="default", name="默认渠道", description="官网和默认二维码入口"))

    if not db.query(QuestionModule).first():
        official_modules = load_official_questionnaire()
        if official_modules:
            seed_questionnaire_modules(db, official_modules)
        else:
            for code, name, description, max_score, sort_order, question_count in MODULES:
                module = QuestionModule(
                    code=code,
                    name=name,
                    description=description,
                    max_score=max_score,
                    sort_order=sort_order,
                )
                db.add(module)
                db.flush()
                for index, max_question_score in enumerate(distribute_question_max_scores(question_count, max_score), start=1):
                    db.add(
                        Question(
                            module_id=module.id,
                            code=f"{code}-Q{index:02d}",
                            dimension="示例维度",
                            text=f"{name}维度示例题 {index}：请根据企业当前真实情况选择 0-4 分。",
                            option_text="0=完全没有；1=初步尝试；2=局部运行；3=体系化落地；4=AI驱动闭环",
                            sort_order=index,
                            max_score=max_question_score,
                        )
                    )

    if not db.query(CaseStudy).first():
        seeds = [
            ("智能客服知识库", "通用", "客户服务", "M01", "闪电战", "用企业 FAQ、产品资料和服务 SOP 搭建客服助手，降低重复咨询压力。", "提升响应速度，沉淀高频问题，减少人工客服初筛工作。"),
            ("销售线索评分助手", "通用", "销售运营", "M02", "闪电战", "根据行业、规模、预算和紧迫度自动给线索打标签，辅助销售优先跟进。", "提升高意向客户识别效率，缩短商机响应时间。"),
            ("会议纪要与行动项生成", "通用", "组织协作", "M03", "闪电战", "自动整理会议纪要、责任人和待办，减少跨部门协作遗漏。", "提升协作透明度，降低会议后的人工整理成本。"),
            ("岗位 AI 助手试点", "通用", "人效提升", "M04", "攻坚战", "围绕销售、运营、研发或客服关键岗位配置 AI 助手和提示词模板。", "提升关键岗位产出稳定性，形成可复制的人效提升方法。"),
            ("订单流程自动化", "制造业", "流程自动化", "M06", "攻坚战", "打通询价、报价、订单确认和发货提醒中的重复节点。", "减少人工流转错误，提高订单处理时效。"),
            ("经营指标看板", "制造业", "数据分析", "M07", "攻坚战", "整合销售、库存、生产和回款指标，形成管理层每日经营看板。", "让管理层更快发现异常并推动动作闭环。"),
            ("质检异常分析助手", "制造业", "质量管理", "M08", "升维战", "基于质检记录和售后反馈归因异常，辅助定位高频质量问题。", "降低重复质量问题，提升改进优先级判断。"),
            ("供应商协同预警", "制造业", "供应链协同", "M09", "升维战", "结合交付周期、缺货记录和质量反馈识别供应商风险。", "提前识别交付风险，支撑采购和生产计划调整。"),
            ("差异化产品洞察", "通用", "战略增长", "M10", "攻坚战", "汇总客户反馈、竞品信息和销售记录，提炼可行动的差异化方向。", "帮助管理层识别更具胜率的产品和市场动作。"),
        ]
        for title, industry, area, module_code, tag, description, benefit in seeds:
            db.add(
                CaseStudy(
                    title=title,
                    industry=industry,
                    function_area=area,
                    module_code=module_code,
                    priority_tag=tag,
                    description=description,
                    expected_benefit=benefit,
                    roi_level="high" if tag == "闪电战" else "medium",
                )
            )

    if not db.query(ReportTemplate).filter(ReportTemplate.is_default.is_(True)).first():
        db.add(
            ReportTemplate(
                name="默认完整诊断报告",
                content="管理摘要、10维得分、核心短板、优先AI场景、案例推荐、下一步咨询建议",
                is_default=True,
            )
        )

    db.commit()


def load_official_questionnaire() -> list[dict] | None:
    if not OFFICIAL_QUESTIONNAIRE_PATH.exists():
        return None
    payload = json.loads(OFFICIAL_QUESTIONNAIRE_PATH.read_text(encoding="utf-8"))
    return payload.get("modules", [])


def seed_questionnaire_modules(db: Session, modules: list[dict]) -> None:
    for module_data in modules:
        module = QuestionModule(
            code=module_data["code"],
            name=module_data["name"],
            description=module_data.get("description"),
            max_score=module_data["max_score"],
            sort_order=module_data["sort_order"],
        )
        db.add(module)
        db.flush()
        for question_data in module_data["questions"]:
            db.add(
                Question(
                    module_id=module.id,
                    code=question_data["code"],
                    dimension=question_data.get("dimension"),
                    text=question_data["text"],
                    option_text=question_data.get("option_text"),
                    sort_order=question_data["sort_order"],
                    max_score=question_data.get("max_score", 4),
                )
            )
