# 日志规范

`dynamics_gate.py` 默认输出到 `logs/`（可用 `--log-dir` 覆盖）。

## 1) decision.log.jsonl
每次 `decide` 一条，字段示例：
- `ts`
- `event_id`, `chat_id`, `message_id`
- `agent_id`
- `speaker_type`, `speaker_agent`
- `interest`, `interest_meta`（method/confidence/scores）
- `desire_before`, `desire_after`
- `p`, `allow`
- `reason`
- `cfg_hash`

## 2) speak.log.jsonl
每次 `speak` 一条：
- `agent_id`
- `interest`
- `drop_self`
- `desire_before`, `desire_after`
- `dedup`（若重复事件）

## 3) metrics.log.jsonl
轻量聚合事件流（便于后续接入 dashboard）：
- `kind`: `decide` 或 `speak`
- `agent_id`
- `allow`（仅 decide）
- `interest`
- `desire_after`
- `p` / `drop_self`

## 排障建议

- 刷屏：先看 `allow=true` 比例和 `interest=low` 的通过率
- 过于沉默：看 `desire_after` 是否长期低于 `desire_min_to_speak`
- 判定漂移：看 `interest_meta.method` 与 `confidence` 分布
