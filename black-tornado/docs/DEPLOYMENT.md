# Persistent deployment and operation

## Railway checklist (deployment not executed here)

1. Put this project into a private repository, excluding `.env`, tokens, database exports, caches and virtual environments. No account password is required.
2. Create a Railway project with a persistent PostgreSQL service. Attach its `DATABASE_URL` to one persistent application service built from the supplied Dockerfile.
3. The application binds `0.0.0.0:$PORT`. `railway.toml` selects `/health`, restart-on-failure and one replica. This is a long-running service, **not cron**. PostgreSQL retains locks, outcomes, quotes and snapshots across application restarts.
4. Keep `DRY_RUN=true`. Set `ADMIN_API_KEY` through Railway secrets, and choose `KILL_SWITCH=true` if starting paused. Set an appropriate timezone display (`Asia/Karachi`, already default). Never commit secrets.
5. Verify `/health`, then `/health/feeds` and `/stats`. A healthy HTTP endpoint is not proof every feed symbol is available. Verify five streaming groups for the 48-symbol documented universe, at most ten subscriptions per connection. Broken/stale symbols must be individually excluded, not filled with invented data.
6. Observe sustained cadence on your actual instance. `cycle_ms`, `overruns`, readiness/rejections, reconnects and notification acknowledgement latency are exposed. There is no hard real-time guarantee under CPU/network pressure. If delivery cannot begin 10–15 seconds before entry, cancel; do not relabel a late opportunity.
7. Record several complete forward paper lifecycles and boundary observations. Confirm lock recovery with an actual controlled restart. Test the bot in a private Telegram test chat before enabling delivery to a channel.
8. Only after your review set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` and `DRY_RUN=false`. The bot needs channel posting permissions. This enables **messages only**, not broker trading. The configured channel accepted a labeled signal and result delivery test; production market alert selection and actual settlement still need forward review.

For an upgrade on an existing database: pause new publications, let the old active lifecycle finish, back up the database and then restart with the new code. Historical legacy records are retained; BT cumulative database/audit totals exclude legacy strategy IDs and isolate paper versus acknowledged live delivery. Arbitrary future migrations are not implemented: schema initialization is for fresh/repeated v1, not a general migration framework.

## Failure semantics

- Durable compare-and-swap delivery claims prevent repeated attempts after restart. Telegram lacks idempotency keys, so an ambiguous failure can cause an omitted message; do not promise exactly-once delivery.
- Old missed/reserved alerts are canceled, not posted for an entry already in the past. Existing active outcomes resume from persisted state. Missing boundary prices time out to UNVERIFIED.
- Quotes must be source-time and receipt-time bounded. No official payout/spread/fill result is inferred. Feed-estimated W/L is not an actual Quotex account result.
- `KILL_SWITCH` or authenticated admin pause stops new entries but preserves settlement. Pause is not a request to delete audit rows or unlock an unresolved lifecycle.
- Configure database backups/retention and resource alarms. Versioned as-of provider candle archives and object-store tick archiving are not included. Long-term archival/retention design is your deployment responsibility.

## Verification boundaries

Real local PostgreSQL, current public feed and local HTTP paper service have been exercised. Docker build, Railway deployment, GitHub workflow execution, comparison against actual Quotex fills remain untested. Authorized Telegram posting permissions and two TEST deliveries were verified. Supplied CI has a PostgreSQL 17 service but must still be run on your repository. The temporary Arena preview is not a Railway deployment and is not an always-on hosting commitment.
