# Archive Stale Slack Channels

## Summary

Add a daily django-q2 scheduled task that finds bot-created Slack channels where Slack's workspace retention policy has deleted all message history, posts a notice explaining the channel is being archived due to inactivity, and archives the channel.

## Scope

- Included: all Slack channels tracked via `ExternalLink(type=SLACK)` records, both public and private.
- Excluded: channels not created by Firetower (no ExternalLink record), channels that still have any message history.

## Detection Logic

A channel is considered "stale" when ALL of these are true:

1. An `ExternalLink(type=SLACK)` record exists for it.
2. `conversations_info` confirms the channel exists and `is_archived` is false.
3. `conversations_history(limit=1)` returns zero messages -- meaning Slack's retention policy has wiped all content.

If `conversations_info` fails (channel deleted, bot removed, etc.), skip it and log a warning. Do not treat API errors as "no history."

## Archive Flow Per Channel

1. Post a message: "This channel is being archived by Firetower because all message history has been removed by the workspace retention policy and there doesn't appear to be any active discussions."
2. Call `conversations_archive` to archive the channel.
3. Log the channel ID and incident number.

## New Code

### `SlackService.archive_channel(channel_id)` -- `src/firetower/integrations/services/slack.py`

Wraps `conversations_archive`. Returns bool. Logs errors on `SlackApiError`.

### `archive_stale_channels()` -- `src/firetower/incidents/tasks.py`

Decorated with `@datadog_log`. Steps:

1. If `SlackService` has no client (missing bot token), disable this schedule in django-q and return early.
2. Query `ExternalLink.objects.filter(type=ExternalLinkType.SLACK)` and select_related incident.
3. For each link, parse channel ID via `SlackService.parse_channel_id_from_url`.
4. Call `conversations_info` -- skip if channel is already archived or API errors.
5. Call `conversations_history` with `limit=1` -- if messages list is non-empty, skip.
6. Post the archival notice via `SlackService.post_message`.
7. Archive via `SlackService.archive_channel`.

Use a single `SlackService` instance for the entire task run. Do not fail the whole task if one channel errors -- log and continue.

### `SCHEDULES` entry

```python
"archive_stale_channels": {
    "func": "firetower.incidents.tasks.archive_stale_channels",
    "schedule_type": Schedule.DAILY,
    "repeats": -1,
}
```

### Migration `0019_schedule_archive_stale_channels`

Data migration following the same pattern as `0016_schedule_demo.py`. Creates the django-q Schedule record.

### `SlackService.get_channel_history` change

Add an optional `limit` parameter (default `None` = current behavior of paginating everything). When `limit` is set, pass it directly and do not paginate. The archive task calls this with `limit=1`.

## Observability

- `@datadog_log` decorator provides `django_q.task.run`, `django_q.task.success`, `django_q.task.error` metrics.
- Per-run counters logged at INFO level: channels scanned, archived, skipped, errored.

## Error Handling

- Single channel failure must not abort the task. Catch `SlackApiError` per channel, log, continue.
- If `SlackService` has no client (missing bot token), disable this schedule via `Schedule.objects.filter(name="archive_stale_channels").update(repeats=0)`, log an error, and return.

## Testing

- Unit test `archive_stale_channels` with mocked `SlackService`:
  - Channel with no history -> archived (post + archive called).
  - Channel with history -> skipped.
  - Channel already archived -> skipped.
  - Channel API error -> skipped with error logged.
  - No Slack client -> schedule disabled.
- Unit test `SlackService.archive_channel`.
- Unit test `get_channel_history` with `limit` parameter.
