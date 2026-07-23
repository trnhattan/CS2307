from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AuthRepository:
    async def get_user_by_username(
        self,
        session: AsyncSession,
        username: str,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT
                    app_user.user_id,
                    app_user.username,
                    app_user.password_hash,
                    app_user.display_name,
                    app_user.role,
                    app_user.student_id,
                    student.student_code,
                    app_user.is_active
                FROM app_users app_user
                LEFT JOIN students student ON student.student_id = app_user.student_id
                WHERE app_user.username = :username
                """
            ),
            {"username": username},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None
