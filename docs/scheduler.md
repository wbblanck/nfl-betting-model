# On-time scheduled runs (cron-job.org)

GitHub starts `schedule:` runs late, and on busy days not at all. On Thursday 2026-11-19 it skipped both Novig
recordings, two S1 runs and the wind run before the Thursday game. So one outside job starts everything on time:

- **cron-job.org** calls GitHub every 5 minutes to start `.github/workflows/scheduler.yml`.
- **`scripts/scheduler.py`** reads every workflow's own `schedule:` times. It starts each workflow whose time came
  due in the last 30 minutes and that has not run on main since that time. A workflow's times are still set only in
  its own file. Dispatched runs get the inputs the scheduled run would have used (S1 and wind grade or run, Novig
  `hours`).
- GitHub's own schedules stay on as a backup. If GitHub fires late after the dispatcher has already started a run,
  that run happens twice. Once the dispatcher has worked for a week, the `schedule:` blocks can be turned off.

## Setup (Will, once)
1. GitHub token: Settings > Developer settings > Fine-grained tokens > Generate. Repository access: only
   `wbblanck/nfl-betting-model`. Permissions: Actions, read and write. Pick an expiry and note it, because the job
   stops when the token expires.
2. cron-job.org: create a cronjob.
   - URL: `https://api.github.com/repos/wbblanck/nfl-betting-model/actions/workflows/scheduler.yml/dispatches`
   - Schedule: every 5 minutes.
   - Advanced: request method POST. Headers: `Authorization: Bearer <token>`,
     `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`.
     Request body: `{"ref":"main"}`.
   - Success is HTTP 204. Turn on failure notifications.
3. If you made the Novig-only job from docs/engine/NOVIG_INTEGRATION.md, delete it. The dispatcher covers it, and
   it skips a time that has already run anyway.

To see what would start today: `python scripts/scheduler.py --day`.
