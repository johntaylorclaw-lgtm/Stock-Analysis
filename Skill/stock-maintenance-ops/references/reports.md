# Reports

Primary report directories:

```text
reports/
reports/summaries/
outputs/phase5/
outputs/variable_dictionary/
```

## Summary Reports

| Report | Meaning |
|---|---|
| `reports/summaries/status_summary_*.md` | Current database status |
| `reports/summaries/daily_summary_*.md` | Hermes daily follow-up summary |
| `reports/summaries/weekly_summary_*.md` | Hermes weekly follow-up summary |

## Source Reports

| Report | Meaning |
|---|---|
| `phase5_daily_light_*` | daily-light source run |
| `phase5_weekly_full_*` | weekly-full source run |
| `phase5_validate_daily_*` | daily validation |
| `phase5_compare_incremental_*` | field-level compare |
| `phase5_refresh_dictionary_*` | dictionary refresh |

## Acceptance Status

| Status | Meaning |
|---|---|
| `pass` | all critical checks passed |
| `warning` | non-blocking issue, summarize clearly |
| `blocked` | requires user confirmation or missing prerequisite |
| `fail` | validation or compare failed |

Hermes should cite the Markdown summary path first, then source report paths when helpful.
