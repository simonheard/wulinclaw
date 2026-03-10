# Dynamics Gate 接入说明

目标：把“是否发言”的概率与状态更新从 LLM 中剥离，由脚本统一处理。

## 命令

### 1) 收到消息时决策

```bash
python3 scripts/dynamics_gate.py decide \
  --agent xiaobai \
  --speaker-type user \
  --event-id tg-100-420 \
  --text "今天客栈来新人了"
```

返回：
- `allow=true` 才允许 agent 继续生成回复
- `allow=false` 直接 NO_REPLY

默认会写日志到 `logs/`：
- `decision.log.jsonl`
- `speak.log.jsonl`
- `metrics.log.jsonl`

> 机器人消息用 `--speaker-type bot --speaker-agent <发言bot的agent_id>`。

### 2) agent 真的发出去后

```bash
python3 scripts/dynamics_gate.py speak \
  --agent xiaobai \
  --interest-level high \
  --event-id tg-send-100-421
```

这一步用于执行 `drop_self_speak`（自己发言后的欲望下降）。

### 3) 查看状态

```bash
python3 scripts/dynamics_gate.py status
```

## 兴趣判定模式

`dynamics_gate` 支持：
- `--interest-mode keyword`
- `--interest-mode hybrid`（默认）
- `--interest-mode llm`（当前为 stub，接口已预留）

独立调试：

```bash
python3 scripts/interest_classifier.py --agent xiaobai --text "今天江湖事很多" --mode hybrid
```

## 规则实现摘要

- 概率：`p = global_pace * desire`
- 兴趣度不参与概率乘数，只决定恢复/下降幅度
- user 消息：按兴趣恢复，且支持 cold start boost
- bot 消息：
  - 自己消息 self-ignore
  - 其他 bot 消息执行 `drop_other_speak`
- 真正发送后再执行 `drop_self_speak`

## 幂等建议

- `event_id` 必传并全局唯一（建议带 chatId + messageId）
- 脚本会对同一 `event_id` 去重，避免重复更新 desire
