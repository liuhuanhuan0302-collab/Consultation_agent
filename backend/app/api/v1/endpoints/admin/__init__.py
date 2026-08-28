"""管理后台路由包 — 按领域拆分为独立路由模块，共用工具放 _shared。"""

from fastapi import APIRouter

from app.api.v1.endpoints.admin import analytics, api_gateway, auth, cases, channels, leads, questions, reports, system_settings, users

router = APIRouter()
for submodule in (auth, users, leads, reports, questions, cases, channels, analytics, api_gateway, system_settings):
    router.include_router(submodule.router)

# 兼容既有导入路径（如 backend/tests 中的 from app.api.v1.endpoints.admin import xxx）
from app.api.v1.endpoints.admin._shared import escape_csv_cell  # noqa: E402
from app.api.v1.endpoints.admin.analytics import analytics_summary, list_events  # noqa: E402
from app.api.v1.endpoints.admin.auth import (  # noqa: E402
    admin_login,
    admin_logout,
    admin_me,
    change_current_password,
)
from app.api.v1.endpoints.admin.cases import create_case, list_cases  # noqa: E402
from app.api.v1.endpoints.admin.channels import (  # noqa: E402
    delete_channel,
    list_channels,
    upsert_channel,
)
from app.api.v1.endpoints.admin.leads import (  # noqa: E402
    admin_get_lead_detail,
    admin_list_leads,
    export_lead_word,
    export_leads,
    update_lead_diagnostic_email,
)
from app.api.v1.endpoints.admin.questions import (  # noqa: E402
    admin_list_questions,
    archive_module,
    archive_question,
    upsert_module,
    upsert_question,
)
from app.api.v1.endpoints.admin.reports import admin_get_report  # noqa: E402
from app.api.v1.endpoints.admin.users import create_user, list_users  # noqa: E402
