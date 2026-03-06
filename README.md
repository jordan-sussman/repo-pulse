# repo-pulse <img width="50" height="30" alt="pulse-icon" src="https://github.com/user-attachments/assets/1ad5aaed-64c7-4836-b7f8-7386d0f90ec0" />

*See what's been happening in your codebase at a glance.*

A CLI that parses git history to surface the most active files and themes in a codebase; zero dependencies, zero config.


## Usage

Run from any git repository:

```bash
python3 repo_pulse.py
```

Or run from outside the repository by passing the path:

```bash
cd ~/projects/my-app
python3 ~/downloads/repo-pulse/repo_pulse.py
```


## Example output

```
────────────────────────────────────────────────────────────

  repo-pulse | codebase activity report

  30 days ago → today  ·  182 commits  ·  733 files touched

  hotspots

   🔴  src/api/controllers/
      🔴  users_controller.ts       18 commits  +1,240 -380
      🔴  auth_controller.ts        14 commits  +403 -180

   🔴  lib/core/
      🔴  query_engine.py           12 commits  +494 -46
      🟢  permissions.py             8 commits  +142 -94
      🟢  validators.py              8 commits  +75 -34

   🟡  tests/integration/
      🟡  auth_test.py               9 commits  +639 -88
      🔵  users_test.py              6 commits  +432 -652

   🟡  config/
      🟡  package-lock.json          7 commits  +43 -1,089
      🔵  settings.rb                8 commits  +67 -25

   🟢  app/views/
      🟢  dashboard.tsx              8 commits  +120 -116

      🔴 high  🟡 moderate  🟢 low  🔵 minimal

  themes

   schema    3,751 mentions across 176 files
   migration 1,841 mentions across 170 files
   session   1,854 mentions across 147 files
   render    1,919 mentions across 131 files
   pipeline    979 mentions across 87 files
   deploy      894 mentions across 87 files

────────────────────────────────────────────────────────────
```

### Examples using options

```bash
python3 repo_pulse.py --flat
python3 repo_pulse.py --days 7
python3 repo_pulse.py --author "jane"
python3 repo_pulse.py --dir src/api
python3 repo_pulse.py --ignore-files "docs,generated"
python3 repo_pulse.py --no-themes
python3 repo_pulse.py --themes 15 --ignore-themes "utils,config"
```

## Options

| Flag              | Default | Description                                      |
| ----------------- | ------- | ------------------------------------------------ |
| `--days, -d`      | `30`    | Lookback window in days                          |
| `--top, -t`       | `20`    | Max files to show                                |
| `--author, -a`    | —       | Filter by author name or email                   |
| `--dir`           | —       | Scope to a subdirectory                          |
| `--flat`          | —       | Flat ranked list instead of grouped by directory |
| `--ignore-files`  | —       | Comma-separated list of paths to ignore          |
| `--themes`        | `10`    | Number of themes to show                         |
| `--no-themes`     | —       | Disable themes section                           |
| `--ignore-themes` | —       | Comma-separated list of terms to ignore          |
| `--no-color`      | —       | Disable colored output                           |
| `--help, -h`      | —       | Show help message                                |

## How scoring works

Files are ranked by a weighted score that combines two signals:

| Signal               | Weight | What it measures                                  |
| -------------------- | ------ | ------------------------------------------------- |
| **Commit frequency** | 70%    | How often the file was changed (distinct commits) |
| **Churn volume**     | 30%    | How many lines were added and deleted             |

Both values are normalized against the most active file in the result set, so scores are always relative to the current time window and filters.

```
score = (commits / max_commits) × 0.7 + (lines_changed / max_lines) × 0.3
```

This means a file touched in many small commits will rank higher than a file with one large change. Frequent edits are a stronger signal of a hotspot than raw line count, but a file with massive churn still gets a boost from the volume component. Color heat indicators reflect score quartiles; red 'high' is top 25%, down to blue 'minimal' for the bottom 25%.

## Requirements

- Python 3.9+
- git
