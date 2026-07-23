import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SystemConfigRepository:
    async def list_items(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    prop_key,
                    prop_value,
                    description,
                    is_editable,
                    updated_by,
                    updated_at
                FROM sys_props
                ORDER BY prop_key
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def get_item(
        self,
        session: AsyncSession,
        prop_key: str,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT
                    prop_key,
                    prop_value,
                    description,
                    is_editable,
                    updated_by,
                    updated_at
                FROM sys_props
                WHERE prop_key = :prop_key
                """
            ),
            {"prop_key": prop_key},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def update_item(
        self,
        session: AsyncSession,
        *,
        prop_key: str,
        prop_value: Any,
        updated_by: str,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                UPDATE sys_props
                SET
                    prop_value = CAST(:prop_value AS JSONB),
                    updated_by = :updated_by,
                    updated_at = CURRENT_TIMESTAMP
                WHERE prop_key = :prop_key
                  AND is_editable = TRUE
                RETURNING
                    prop_key,
                    prop_value,
                    description,
                    is_editable,
                    updated_by,
                    updated_at
                """
            ),
            {
                "prop_key": prop_key,
                "prop_value": json.dumps(prop_value),
                "updated_by": updated_by,
            },
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None
