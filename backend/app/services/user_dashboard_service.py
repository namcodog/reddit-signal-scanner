"""User dashboard service: history, usage stats, membership info."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.task import Task, TaskStatus
from ..models.user import (
    MEMBERSHIP_LEVEL_LITERAL_MAP,
    MembershipLevel,
    MembershipLevelLiteral,
    User,
)
from ..schemas.user_management import (
    MembershipFeatures,
    MembershipInfoResponse,
    UserHistoryItem,
    UserUsageStatsResponse,
)


@dataclass(slots=True)
class MembershipPlan:
    label: str
    monthly_quota: Optional[int]
    features: MembershipFeatures


class UserDashboardService:
    """Aggregate data for personal center endpoints."""

    def __init__(self) -> None:
        self._plans: Dict[MembershipLevel, MembershipPlan] = {
            MembershipLevel.FREE: MembershipPlan(
                label="Free",
                monthly_quota=10,
                features=MembershipFeatures(
                    can_export_report=False,
                    realtime_updates=False,
                    priority_support=False,
                    max_tasks_per_month=10,
                    highlight="免费额度，每月10次标准分析",
                ),
            ),
            MembershipLevel.PRO: MembershipPlan(
                label="Pro",
                monthly_quota=100,
                features=MembershipFeatures(
                    can_export_report=True,
                    realtime_updates=True,
                    priority_support=False,
                    max_tasks_per_month=100,
                    highlight="专业版，适合成长型团队",
                ),
            ),
            MembershipLevel.ENTERPRISE: MembershipPlan(
                label="Enterprise",
                monthly_quota=None,
                features=MembershipFeatures(
                    can_export_report=True,
                    realtime_updates=True,
                    priority_support=True,
                    max_tasks_per_month=None,
                    highlight="企业版，无限制分析额度",
                ),
            ),
        }
        self._ordered_levels: List[MembershipLevel] = [
            MembershipLevel.FREE,
            MembershipLevel.PRO,
            MembershipLevel.ENTERPRISE,
        ]
        self._level_literal_map: Dict[MembershipLevel, MembershipLevelLiteral] = MEMBERSHIP_LEVEL_LITERAL_MAP

    def _month_window(self) -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _status_label(self, status: TaskStatus) -> str:
        mapping = {
            TaskStatus.PENDING: "待处理",
            TaskStatus.PROCESSING: "处理中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.FAILED: "已失败",
            TaskStatus.DEAD_LETTER: "死信",
        }
        return mapping.get(status, status.value)

    async def get_user_record(
        self,
        user_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> Optional[User]:
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_task_history(
        self,
        user_id: UUID,
        limit: int,
        db: AsyncSession,
    ) -> List[UserHistoryItem]:
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        history: List[UserHistoryItem] = []
        for item in tasks:
            status = TaskStatus(item.status) if not isinstance(item.status, TaskStatus) else item.status
            description = item.product_description
            if description and len(description) > 120:
                description = description[:117] + "..."
            history.append(
                UserHistoryItem(
                    task_id=item.id,
                    status=status.value,
                    status_label=self._status_label(status),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    completed_at=item.completed_at,
                    description=description,
                )
            )
        return history

    async def get_usage_stats(
        self,
        user_id: UUID,
        membership_level: MembershipLevel,
        db: AsyncSession,
    ) -> UserUsageStatsResponse:
        month_start = self._month_window()

        counts_stmt = (
            select(Task.status, func.count())
            .where(Task.user_id == user_id)
            .group_by(Task.status)
        )
        counts_result = await db.execute(counts_stmt)
        counts_map: Dict[str, int] = {}
        for status_value, count in counts_result.all():
            status_key = (
                status_value.value
                if isinstance(status_value, TaskStatus)
                else str(status_value)
            )
            counts_map[status_key] = int(count)

        total_tasks = sum(counts_map.values())
        completed = counts_map.get(TaskStatus.COMPLETED.value, 0)
        failed = counts_map.get(TaskStatus.FAILED.value, 0)
        processing = counts_map.get(TaskStatus.PROCESSING.value, 0)
        pending = counts_map.get(TaskStatus.PENDING.value, 0)

        month_stmt = (
            select(func.count())
            .where(Task.user_id == user_id, Task.created_at >= month_start)
        )
        current_month_total = int((await db.execute(month_stmt)).scalar_one())

        last_activity_stmt = (
            select(func.max(Task.updated_at))
            .where(Task.user_id == user_id)
        )
        last_activity = (await db.execute(last_activity_stmt)).scalar_one_or_none()

        plan = self._plans[membership_level]
        quota = plan.monthly_quota
        remaining = None if quota is None else max(quota - current_month_total, 0)

        return UserUsageStatsResponse(
            total_tasks=total_tasks,
            completed_tasks=completed,
            failed_tasks=failed,
            active_tasks=processing,
            pending_tasks=pending,
            current_month_total=current_month_total,
            current_month_quota=quota,
            remaining_quota=remaining,
            last_activity_at=last_activity,
        )

    async def get_membership_info(
        self,
        user_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> Optional[MembershipInfoResponse]:
        user = await self.get_user_record(user_id, tenant_id, db)
        if user is None:
            return None

        membership = MembershipLevel.ensure(
            getattr(user, "membership_level", None)
        )

        plan = self._plans[membership]
        usage_stats = await self.get_usage_stats(user_id, membership, db)

        used = usage_stats.current_month_total
        remaining = usage_stats.remaining_quota

        try:
            current_idx = self._ordered_levels.index(membership)
        except ValueError:
            current_idx = 0

        upgrade_options: List[MembershipLevelLiteral] = [
            self._level_literal_map[level]
            for level in self._ordered_levels[current_idx + 1 :]
        ]

        return MembershipInfoResponse(
            level=self._level_literal_map[membership],
            label=plan.label,
            used_this_month=used,
            remaining_quota=remaining,
            quota=plan.monthly_quota,
            features=plan.features,
            upgrade_options=upgrade_options,
        )

    async def update_membership_level(
        self,
        user_id: UUID,
        tenant_id: UUID,
        target: MembershipLevel,
        db: AsyncSession,
    ) -> Optional[MembershipInfoResponse]:
        user = await self.get_user_record(user_id, tenant_id, db)
        if user is None:
            return None

        stored_level = MembershipLevel.ensure(
            getattr(user, "membership_level", None)
        )

        if stored_level != target:
            user.membership_level = self._level_literal_map[target]
            user.updated_at = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return await self.get_membership_info(user_id, tenant_id, db)
