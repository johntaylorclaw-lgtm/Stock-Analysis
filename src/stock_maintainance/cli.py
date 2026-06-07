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
from .phase4_audit import run_phase4_audit
from .incremental_compare import compare_incremental_window
from .daily_validate import validate_daily
from .daily_light import run_daily_light
from .weekly_full import run_weekly_full
from .dictionary import refresh_dictionary
from .run_summary import summarize_run
from .export import export_parquet
from .sample_stock import sample_stock
from .ingest import (
    default_index_codes,
    smoke_tushare,
    sync_adj_factor_batch,
    sync_adj_factor_range,
    sync_adj_factor_for_stock,
    sync_daily_for_date,
    sync_daily_range,
    sync_financial_sample,
    sync_financial_batch,
    sync_financial_incremental_range,
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
    print("docs are up to date")
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


def cmd_phase4_audit(args: argparse.Namespace) -> int:
    paths = run_phase4_audit(end_date=args.end_date, output_prefix=args.output_prefix)
    for path in paths.values():
        print(path)
    return 0


def cmd_compare_incremental_window(args: argparse.Namespace) -> int:
    result = compare_incremental_window(
        start_date=args.start_date,
        end_date=args.end_date,
        tables=args.table,
        snapshot_prefix=args.snapshot_prefix,
        output_prefix=args.output_prefix,
        abs_tol=args.abs_tol,
        rel_tol=args.rel_tol,
    )
    print(json.dumps({"json": str(result.json_path), "markdown": str(result.markdown_path), **result.report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.passed or not args.fail_on_diff else 1


def cmd_validate_daily(args: argparse.Namespace) -> int:
    result = validate_daily(
        as_of_date=args.as_of_date,
        max_auto_trade_days=args.max_auto_trade_days,
        validation_days=args.validation_days,
        tables=args.table,
        output_prefix=args.output_prefix,
    )
    print(json.dumps({"json": str(result.json_path), "markdown": str(result.markdown_path), **result.report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.passed or not args.fail_on_warning else 1


def cmd_sample_stock(args: argparse.Namespace) -> int:
    result = sample_stock(
        ts_code=args.ts_code,
        start_date=args.start_date,
        end_date=args.end_date,
        row_limit=args.rows,
        output_prefix=args.output_prefix,
        build_excel=not args.json_only,
    )
    print(
        json.dumps(
            {
                "json": str(result.json_path),
                "xlsx": str(result.xlsx_path) if result.xlsx_path else None,
                "ts_code": result.payload["stock"]["ts_code"],
                "base_table_count": len(result.payload["base_tables"]),
                "derived_table_count": len(result.payload["derived_tables"]),
                "quality_table_count": len(result.payload["quality_report"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_daily_light(args: argparse.Namespace) -> int:
    result = run_daily_light(
        as_of_date=args.as_of_date,
        max_auto_trade_days=args.max_auto_trade_days,
        validation_days=args.validation_days,
        dry_run=args.dry_run,
        allow_confirmed_history=args.allow_confirmed_history,
        include_financial=args.include_financial,
        include_index_weight=args.include_index_weight,
        output_prefix=args.output_prefix,
    )
    print(json.dumps({"json": str(result.json_path), "markdown": str(result.markdown_path), **result.report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


def cmd_weekly_full(args: argparse.Namespace) -> int:
    result = run_weekly_full(
        as_of_date=args.as_of_date,
        reference_days=args.reference_days,
        compare_days=args.compare_days,
        tables=args.table,
        snapshot_prefix=args.snapshot_prefix,
        output_prefix=args.output_prefix,
        dry_run=args.dry_run,
        create_snapshot_from_current=args.create_snapshot_from_current,
    )
    print(json.dumps({"json": str(result.json_path), "markdown": str(result.markdown_path), **result.report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


def cmd_refresh_dictionary(args: argparse.Namespace) -> int:
    result = refresh_dictionary(
        build_excel=not args.skip_excel,
        skip_feature_schema_sync=args.skip_feature_schema_sync,
        output_prefix=args.output_prefix,
    )
    print(json.dumps({"json": str(result.json_path), **result.report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


def cmd_summarize_run(args: argparse.Namespace) -> int:
    result = summarize_run(
        mode=args.mode,
        run_id=args.run_id,
        as_of_date=args.as_of_date,
        phase=args.phase,
        output_prefix=args.output_prefix,
    )
    print(json.dumps({"markdown": str(result.markdown_path), **result.report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


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
            run_cache_steps=not args.skip_cache_steps,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_export_parquet(args: argparse.Namespace) -> int:
    result = export_parquet(
        source=args.source,
        dataset=args.dataset,
        start_date=args.start_date,
        end_date=args.end_date,
        columns=args.column,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
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


def cmd_sync_adj_factor_range(args: argparse.Namespace) -> int:
    result = sync_adj_factor_range(args.start_date, args.end_date, limit=args.limit)
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


def cmd_sync_financial_incremental_range(args: argparse.Namespace) -> int:
    result = sync_financial_incremental_range(
        args.start_date,
        args.end_date,
        report_start_date=args.report_start_date,
        report_end_date=args.report_end_date,
        limit=args.limit,
        resume=not args.no_resume,
        all_stocks=args.all_stocks,
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
        "phase4-audit": cmd_phase4_audit,
        "compare-incremental-window": cmd_compare_incremental_window,
        "validate-daily": cmd_validate_daily,
        "daily-light": cmd_daily_light,
        "weekly-full": cmd_weekly_full,
        "refresh-dictionary": cmd_refresh_dictionary,
        "summarize-run": cmd_summarize_run,
        "sample-stock": cmd_sample_stock,
        "plan-features": cmd_plan_features,
        "build-features": cmd_build_features,
        "export-parquet": cmd_export_parquet,
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
            child.add_argument("--skip-cache-steps", action="store_true")
        if name == "phase4-audit":
            child.add_argument("--end-date")
            child.add_argument("--output-prefix", default="phase4_audit_report")
        if name == "compare-incremental-window":
            child.add_argument("--start-date", required=True)
            child.add_argument("--end-date", required=True)
            child.add_argument("--table", action="append")
            child.add_argument("--snapshot-prefix", default="audit_tmp_phase4_full_")
            child.add_argument("--output-prefix", default="incremental_window_compare")
            child.add_argument("--abs-tol", type=float, default=1e-6)
            child.add_argument("--rel-tol", type=float, default=1e-12)
            child.add_argument("--fail-on-diff", action="store_true")
        if name == "validate-daily":
            child.add_argument("--as-of-date")
            child.add_argument("--max-auto-trade-days", type=int, default=10)
            child.add_argument("--validation-days", type=int, default=1)
            child.add_argument("--table", action="append")
            child.add_argument("--output-prefix", default="validate_daily_report")
            child.add_argument("--fail-on-warning", action="store_true")
        if name == "daily-light":
            child.add_argument("--as-of-date")
            child.add_argument("--max-auto-trade-days", type=int, default=10)
            child.add_argument("--validation-days", type=int, default=1)
            child.add_argument("--dry-run", action="store_true")
            child.add_argument("--allow-confirmed-history", action="store_true")
            child.add_argument("--include-financial", action="store_true")
            child.add_argument("--include-index-weight", action="store_true")
            child.add_argument("--output-prefix", default="daily_light_run")
        if name == "weekly-full":
            child.add_argument("--as-of-date")
            child.add_argument("--reference-days", type=int, default=40)
            child.add_argument("--compare-days", type=int, default=10)
            child.add_argument("--table", action="append")
            child.add_argument("--snapshot-prefix", default="audit_tmp_phase4_full_")
            child.add_argument("--output-prefix", default="weekly_full_run")
            child.add_argument("--dry-run", action="store_true")
            child.add_argument("--create-snapshot-from-current", action="store_true")
        if name == "refresh-dictionary":
            child.add_argument("--skip-excel", action="store_true")
            child.add_argument("--skip-feature-schema-sync", action="store_true")
            child.add_argument("--output-prefix", default="refresh_dictionary")
        if name == "summarize-run":
            child.add_argument("--mode", choices=["status", "daily", "weekly", "phase"], required=True)
            child.add_argument("--run-id")
            child.add_argument("--as-of-date")
            child.add_argument("--phase", default="phase5")
            child.add_argument("--output-prefix")
        if name == "sample-stock":
            child.add_argument("--ts-code")
            child.add_argument("--start-date")
            child.add_argument("--end-date")
            child.add_argument("--rows", type=int, default=20)
            child.add_argument("--output-prefix", default="phase5_sample_stock")
            child.add_argument("--json-only", action="store_true")
        if name == "export-parquet":
            child.add_argument("--source", default="stock_features_core")
            child.add_argument("--dataset")
            child.add_argument("--start-date", required=True)
            child.add_argument("--end-date", required=True)
            child.add_argument("--column", action="append")
            child.add_argument("--dry-run", action="store_true")
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

    sync_adj_range = sub.add_parser("sync-adj-factor-range")
    sync_adj_range.add_argument("start_date")
    sync_adj_range.add_argument("end_date")
    sync_adj_range.add_argument("--limit", type=int)
    sync_adj_range.set_defaults(func=cmd_sync_adj_factor_range)

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

    sync_financial_incremental_parser = sub.add_parser("sync-financial-incremental-range")
    sync_financial_incremental_parser.add_argument("start_date")
    sync_financial_incremental_parser.add_argument("end_date")
    sync_financial_incremental_parser.add_argument("--report-start-date")
    sync_financial_incremental_parser.add_argument("--report-end-date")
    sync_financial_incremental_parser.add_argument("--limit", type=int)
    sync_financial_incremental_parser.add_argument("--no-resume", action="store_true")
    sync_financial_incremental_parser.add_argument("--all-stocks", action="store_true")
    sync_financial_incremental_parser.set_defaults(func=cmd_sync_financial_incremental_range)

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
