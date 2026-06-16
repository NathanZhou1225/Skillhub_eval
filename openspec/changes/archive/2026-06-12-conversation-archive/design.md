# Design — conversation-archive

## API

`DELETE /conversations/{conversation_id}?perspective=author|expert` → 204

- Sets `status='archived'`, `archived_at=now`
- Does not delete `lui_messages`, `evaluation_runs`, or staging

## Gates

| Condition | Author | Expert |
|-----------|--------|--------|
| Run in `RUNNING_STATUSES` | 409 | 409 |
| `status=frozen` | 403 | allow |
| `awaiting_human_review` + `human_review_required` | 403 | allow |
| Already archived | 404 | 404 |

## DB

`SCHEMA_VERSION=8`: `conversations.archived_at TEXT`

`list_conversations`: `WHERE c.status != 'archived'`

## UI

侧栏 hover「×」→ confirm → DELETE；删当前会话后自动选列表最新一条。
