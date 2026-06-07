from __future__ import annotations

from .context import FeatureBuildContext
from ..schema import quote_ident


def delete_write_window(ctx: FeatureBuildContext, table_name: str) -> int:
    if ctx.dry_run:
        return 0
    if ctx.con is None:
        raise ValueError("feature build context has no database connection")
    result = ctx.con.execute(
        f"""
        DELETE FROM {quote_ident(table_name)}
        WHERE trade_date BETWEEN ? AND ?
        """,
        [ctx.write_start_date, ctx.write_end_date],
    )
    try:
        return int(result.fetchone()[0])
    except Exception:
        return 0
