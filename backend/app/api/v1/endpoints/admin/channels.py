"""渠道管理 — 列表 / 新增更新 / 删除二维码。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChannelSource, User
from app.repositories.qr_code_repo import get_channel_by_code, list_channels as list_channel_sources
from app.schemas import ChannelRead, ChannelUpsert, MessageResponse
from app.utils.auth import ContentManager, LeadViewer
from app.utils.logging_utils import write_operation_log

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# 3.13 渠道列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/channels
# 功能：查看所有推广渠道
#       渠道二维码：GET /api/public/channels/{code}/qr
# 鉴权：admin / operator / sales / consultant
# 返回：ChannelRead[] 数组
@router.get("/api/admin/channels", response_model=list[ChannelRead])
def list_channels(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[ChannelSource]:
    return list_channel_sources(db)


# ══════════════════════════════════════════════════════════════════
# 3.14 新增渠道
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/channels
# 功能：创建或更新推广渠道
#       创建后可调用 GET /api/public/channels/{code}/qr 获取二维码图片
# 鉴权：admin / operator
# 请求：{ code*, name*, description?, is_active* }
# 返回：渠道对象
@router.post("/api/admin/channels", response_model=ChannelRead)
def upsert_channel(payload: ChannelUpsert, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> ChannelSource:
    channel = get_channel_by_code(db, payload.code)
    if not channel:
        channel = ChannelSource(code=payload.code)
        db.add(channel)
    channel.name = payload.name
    channel.description = payload.description
    channel.is_active = payload.is_active
    write_operation_log(db, user, "upsert_channel", "channel_source", payload.code)
    db.commit()
    db.refresh(channel)
    return channel


# ══════════════════════════════════════════════════════════════════
# 3.15 删除渠道二维码
# ══════════════════════════════════════════════════════════════════
# 方法：DELETE
# 路径：/api/admin/channels/{channel_id}
# 功能：删除渠道及其二维码入口，原二维码链接立即失效
# 鉴权：admin / operator
@router.delete("/api/admin/channels/{channel_id}", response_model=MessageResponse)
def delete_channel(channel_id: int, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> MessageResponse:
    channel = db.get(ChannelSource, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    code = channel.code
    db.delete(channel)
    write_operation_log(db, user, "delete_channel", "channel_source", code)
    db.commit()
    return MessageResponse(message="渠道二维码已删除")
