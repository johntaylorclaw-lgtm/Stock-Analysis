from __future__ import annotations

import argparse
import json
import sys

from .config import load_pipeline, load_schema_registry, load_sources, load_variable_registry
from .audit import run_quality_audit
from .database import DB_PATH, connect, init_database, refresh_source_api_status
from .docs import check_docs, generate_docs, render_schema_summary
from .features.build import build_features
from .features.planner import build_feature_plan, render_plan_markdown
from .ingest import (
    default_index_codes,
    smoke_tushare,
    sync_adj_factor_batch,
    sync_adj_factor_for_stock,
    sync_daily_for_date,
    sync_daily_range,
    sync_financial_sample,
    sync_financial_batch,
    sync_financial_events_batch,
    FINANCIAL_EVENT_APIS,
    sync_concepts,
    sync_index_daily_range,
    sync_index_weight_month,
    sync_index_weight_range,
    sync_index_basic,
    sync_market_behavior_for_date,
    sync_market_behavior_range,
    sync_dividend_batch,
    sync_disclosure_schedule,
    sync_disclosure_schedule_batch,
    sync_pledge_stat_batch,
    sync_sw_industry,
    sync_stock_company,
    sync_stock_status_history,
    sync_stock_basic,
    sync_trade_calendar,
)
from .schema import all_create_table_sql, schema_summary
from .validate import validate_schema_registry, validate_variable_registry, validate_variable_schema_alignment
from .views import create_views
from .paths import REPORTS_DIR


def cmd_plan(_: argparse.Namespace) -> int:
    pipeline = load_pipeline()
    sources = load_sources()
    schema = load_schema_registry()
    variables = load_variable_registry()
    summary = {
        "phase": "Phase 1 skeleton",
        "stock_scope": pipeline["stock_scope"],
        "default_index_pool": pipeline["default_index_pool"],
        "source_api_count": len(sources["tushare"]["apis"]),
        "registered_table_count": len(schema["tables"]),
        "registered_variable_count": len(variables["variables"]),
        "daily_policy": pipeline["daily_policy"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_schema_summary(_: argparse.Namespace) -> int:
    print(render_schema_summary())
    return 0


def cmd_emit_ddl(_: argparse.Namespace) -> int:
    print(all_create_table_sql(load_schema_registry()))
    return 0


def cmd_docs_generate(_: argparse.Namespace) -> int:
    paths = generate_docs()
    for path in paths:
        print(path)
    return 0


def cmd_docs_check(_: argparse.Namespace) -> int:
    diffs = check_docs()
    if diffs:
        for diff in diffs:
            print(diff)
        return 1
    print("generated docs are up to date")
    return 0


def cmd_validate_config(_: argparse.Namespace) -> int:
    schema = load_schema_registry()
    variables = load_variable_registry()
    errors = []
    errors.extend(validate_schema_registry(schema))
    errors.extend(validate_variable_registry(variables))
    errors.extend(validate_variable_schema_alignment(variables, schema))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("config validation passed")
    return 0


def cmd_init_db(_: argparse.Namespace) -> int:
    init_database()
    print(f"initialized DuckDB: {DB_PATH}")
    return 0


def cmd_refresh_source_status(_: argparse.Namespace) -> int:
    with connect() as con:
        init_database(con)
        refresh_source_api_status(con)
    print("refreshed metadata_source_api status")
    return 0


def cmd_create_views(_: argparse.Namespace) -> int:
    create_views()
    print("created analytical views")
    return 0


def cmd_audit_quality(_: argparse.Namespace) -> int:
    paths = run_quality_audit()
    for path in paths:
        print(path)
    return 0


def cmd_plan_features(args: argparse.Namespace) -> int:
    plan = build_feature_plan(
        load_variable_registry(),
        modules=args.module,
        start_date=args.start_date,
        end_date=args.end_date,
        mode=args.mode,
    )
    if args.format == "json":
        content = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)
    else:
        content = render_plan_markdown(plan)
    if args.output:
        output = REPORTS_DIR / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(output)
    else:
        print(content)
    return 2 if plan.requires_confirmation and args.fail_on_confirmation else 0


def cmd_build_features(args: argparse.Namespace) -> int:
    try:
        result = build_features(
            modules=args.module,
            start_date=args.start_date,
            end_date=args.end_date,
            mode=args.mode,
            dry_run=args.dry_run,
            allow_confirmed_history=args.allow_confirmed_history,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_smoke_tushare(_: argparse.Namespace) -> int:
    print(json.dumps(smoke_tushare(), ensure_ascii=False, indent=2))
    return 0


def cmd_sync_master(args: argparse.Namespace) -> int:
    result = {}
    result.update(sync_stock_basic())
    result.update(sync_stock_company())
    result.update(sync_stock_status_history())
    result.update(sync_trade_calendar(start_date=args.start_date, end_date=args.end_date))
    result.update(sync_index_basic())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_daily_date(args: argparse.Namespace) -> int:
    print(json.dumps(sync_daily_for_date(args.trade_date), ensure_ascii=False, indent=2))
    return 0


def cmd_sync_daily_range(args: argparse.Namespace) -> int:
    result = sync_daily_range(args.start_date, args.end_date, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_market_behavior_date(args: argparse.Namespace) -> int:
    print(json.dumps(sync_market_behavior_for_date(args.trade_date), ensure_ascii=False, indent=2))
    return 0


def cmd_sync_market_behavior_range(args: argparse.Namespace) -> int:
    result = sync_market_behavior_range(args.start_date, args.end_date, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_dividend_batch(args: argparse.Namespace) -> int:
    result = sync_dividend_batch(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_disclosure_schedule(args: argparse.Namespace) -> int:
    result = sync_disclosure_schedule(start_date=args.start_date, end_date=args.end_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_disclosure_schedule_batch(args: argparse.Namespace) -> int:
    result = sync_disclosure_schedule_batch(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_pledge_stat_batch(args: argparse.Namespace) -> int:
    result = sync_pledge_stat_batch(limit=args.limit, resume=not args.no_resume)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_adj_factor(args: argparse.Namespace) -> int:
    result = sync_adj_factor_for_stock(args.ts_code, start_date=args.start_date, end_date=args.end_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_adj_factor_batch(args: argparse.Namespace) -> int:
    result = sync_adj_factor_batch(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_index_daily(args: argparse.Namespace) -> int:
    codes = args.index_code or default_index_codes()
    result = sync_index_daily_range(args.start_date, args.end_date, index_codes=codes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_index_weight_month(args: argparse.Namespace) -> int:
    codes = args.index_code or default_index_codes()
    result = sync_index_weight_month(args.month, index_codes=codes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_index_weight_range(args: argparse.Namespace) -> int:
    codes = args.index_code or default_index_codes()
    result = sync_index_weight_range(
        args.start_month,
        args.end_month,
        index_codes=codes,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_sw_industry(args: argparse.Namespace) -> int:
    result = sync_sw_industry(limit_members=args.limit_members)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_concepts(args: argparse.Namespace) -> int:
    result = sync_concepts(limit_concepts=args.limit_concepts)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_financial_sample(args: argparse.Namespace) -> int:
    result = sync_financial_sample(args.ts_code, start_date=args.start_date, end_date=args.end_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_financial_batch(args: argparse.Namespace) -> int:
    result = sync_financial_batch(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_financial_events_batch(args: argparse.Namespace) -> int:
    apis = args.api or FINANCIAL_EVENT_APIS
    result = sync_financial_events_batch(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        apis=apis,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stock-maintain", description="Stock data maintenance CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    commands = {
        "plan": cmd_plan,
        "schema-summary": cmd_schema_summary,
        "emit-ddl": cmd_emit_ddl,
        "docs-generate": cmd_docs_generate,
        "docs-check": cmd_docs_check,
        "validate-config": cmd_validate_config,
        "init-db": cmd_init_db,
        "refresh-source-status": cmd_refresh_source_status,
        "create-views": cmd_create_views,
        "audit-quality": cmd_audit_quality,
        "plan-features": cmd_plan_features,
        "build-features": cmd_build_features,
        "smoke-tushare": cmd_smoke_tushare,
    }
    for name, func in commands.items():
        child = sub.add_parser(name)
        if name == "plan-features":
            child.add_argument("--module", action="append")
            child.add_argument("--start-date")
            child.add_argument("--end-date")
            child.add_argument("--mode", choices=["daily", "history"], default="daily")
            child.add_argument("--format", choices=["markdown", "json"], default="markdown")
            child.add_argument("--output")
            child.add_argument("--fail-on-confirmation", action="store_true")
        if name == "build-features":
            child.add_argument("--module", action="append")
            child.add_argument("--start-date")
            child.add_argument("--end-date")
            child.add_argument("--mode", choices=["daily", "history"], default="daily")
            child.add_argument("--dry-run", action="store_true")
            child.add_argument("--allow-confirmed-history", action="store_true")
        child.set_defaults(func=func)

    sync_master = sub.add_parser("sync-master")
    sync_master.add_argument("--start-date", default="20060101")
    sync_master.add_argument("--end-date")
    sync_master.set_defaults(func=cmd_sync_master)

    sync_daily = sub.add_parser("sync-daily-date")
    sync_daily.add_argument("trade_date")
    sync_daily.set_defaults(func=cmd_sync_daily_date)

    sync_daily_range_parser = sub.add_parser("sync-daily-range")
    sync_daily_range_parser.add_argument("start_date")
    sync_daily_range_parser.add_argument("end_date")
    sync_daily_range_parser.add_argument("--limit", type=int)
    sync_daily_range_parser.set_defaults(func=cmd_sync_daily_range)

    sync_market_behavior = sub.add_parser("sync-market-behavior-date")
    sync_market_behavior.add_argument("trade_date")
    sync_market_behavior.set_defaults(func=cmd_sync_market_behavior_date)

    sync_market_behavior_range_parser = sub.add_parser("sync-market-behavior-range")
    sync_market_behavior_range_parser.add_argument("start_date")
    sync_market_behavior_range_parser.add_argument("end_date")
    sync_market_behavior_range_parser.add_argument("--limit", type=int)
    sync_market_behavior_range_parser.set_defaults(func=cmd_sync_market_behavior_range)

    sync_dividend = sub.add_parser("sync-dividend-batch")
    sync_dividend.add_argument("--start-date", default="20060101")
    sync_dividend.add_argument("--end-date")
    sync_dividend.add_argument("--limit", type=int)
    sync_dividend.add_argument("--no-resume", action="store_true")
    sync_dividend.set_defaults(func=cmd_sync_dividend_batch)

    sync_disclosure = sub.add_parser("sync-disclosure-schedule")
    sync_disclosure.add_argument("--start-date", default="20060101")
    sync_disclosure.add_argument("--end-date")
    sync_disclosure.set_defaults(func=cmd_sync_disclosure_schedule)

    sync_disclosure_batch = sub.add_parser("sync-disclosure-schedule-batch")
    sync_disclosure_batch.add_argument("--start-date", default="20060101")
    sync_disclosure_batch.add_argument("--end-date")
    sync_disclosure_batch.add_argument("--limit", type=int)
    sync_disclosure_batch.add_argument("--no-resume", action="store_true")
    sync_disclosure_batch.set_defaults(func=cmd_sync_disclosure_schedule_batch)

    sync_pledge = sub.add_parser("sync-pledge-stat-batch")
    sync_pledge.add_argument("--limit", type=int)
    sync_pledge.add_argument("--no-resume", action="store_true")
    sync_pledge.set_defaults(func=cmd_sync_pledge_stat_batch)

    sync_adj = sub.add_parser("sync-adj-factor")
    sync_adj.add_argument("ts_code")
    sync_adj.add_argument("--start-date", default="20060101")
    sync_adj.add_argument("--end-date")
    sync_adj.set_defaults(func=cmd_sync_adj_factor)

    sync_adj_batch = sub.add_parser("sync-adj-factor-batch")
    sync_adj_batch.add_argument("--start-date", default="20060101")
    sync_adj_batch.add_argument("--end-date")
    sync_adj_batch.add_argument("--limit", type=int)
    sync_adj_batch.add_argument("--no-resume", action="store_true")
    sync_adj_batch.set_defaults(func=cmd_sync_adj_factor_batch)

    sync_index_daily = sub.add_parser("sync-index-daily")
    sync_index_daily.add_argument("start_date")
    sync_index_daily.add_argument("end_date")
    sync_index_daily.add_argument("--index-code", action="append")
    sync_index_daily.set_defaults(func=cmd_sync_index_daily)

    sync_index_weight = sub.add_parser("sync-index-weight-month")
    sync_index_weight.add_argument("month")
    sync_index_weight.add_argument("--index-code", action="append")
    sync_index_weight.set_defaults(func=cmd_sync_index_weight_month)

    sync_index_weight_range_parser = sub.add_parser("sync-index-weight-range")
    sync_index_weight_range_parser.add_argument("start_month")
    sync_index_weight_range_parser.add_argument("end_month")
    sync_index_weight_range_parser.add_argument("--index-code", action="append")
    sync_index_weight_range_parser.add_argument("--no-resume", action="store_true")
    sync_index_weight_range_parser.set_defaults(func=cmd_sync_index_weight_range)

    sync_sw = sub.add_parser("sync-sw-industry")
    sync_sw.add_argument("--limit-members", type=int)
    sync_sw.set_defaults(func=cmd_sync_sw_industry)

    sync_concepts_parser = sub.add_parser("sync-concepts")
    sync_concepts_parser.add_argument("--limit-concepts", type=int)
    sync_concepts_parser.set_defaults(func=cmd_sync_concepts)

    sync_financial = sub.add_parser("sync-financial-sample")
    sync_financial.add_argument("ts_code")
    sync_financial.add_argument("--start-date", default="20240101")
    sync_financial.add_argument("--end-date")
    sync_financial.set_defaults(func=cmd_sync_financial_sample)

    sync_financial_batch_parser = sub.add_parser("sync-financial-batch")
    sync_financial_batch_parser.add_argument("--start-date", default="20060101")
    sync_financial_batch_parser.add_argument("--end-date")
    sync_financial_batch_parser.add_argument("--limit", type=int)
    sync_financial_batch_parser.add_argument("--no-resume", action="store_true")
    sync_financial_batch_parser.set_defaults(func=cmd_sync_financial_batch)

    sync_financial_events = sub.add_parser("sync-financial-events-batch")
    sync_financial_events.add_argument("--start-date", default="20060101")
    sync_financial_events.add_argument("--end-date")
    sync_financial_events.add_argument("--limit", type=int)
    sync_financial_events.add_argument("--api", action="append")
    sync_financial_events.add_argument("--no-resume", action="store_true")
    sync_financial_events.set_defaults(func=cmd_sync_financial_events_batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
