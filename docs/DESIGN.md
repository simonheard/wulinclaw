# WulinClaw 设计说明（基线）

## 1. 目标

构建“多 bot 同群聊、由用户点燃、可自收敛”的仿真人群聊系统。

核心原则：
- **内容生成**交给 LLM
- **发言决策**交给脚本（可审计、可复现）

---

## 2. 架构

```text
Telegram 消息 -> OpenClaw 路由到 agent
                  -> (前置) dynamics_gate decide
                       allow=false => NO_REPLY
                       allow=true  => 继续生成回复
                  -> 发送成功后调用 dynamics_gate speak
```

组件：
- `chat_dynamics.default.json`：全局行为参数
- `agents/*.yaml`：角色基线与覆盖参数
- `scripts/dynamics_gate.py`：状态机 + 概率决策
- `state/dynamics.db`：运行态（desire、事件去重）

---

## 3. 状态变量

每个 agent：
- `desire`：发言欲望（0~1）

系统级：
- `event_seen`：去重表，保证同一事件不重复扣/加欲望

---

## 4. 规则（当前版本）

1) 概率（固定）
- `p = global_pace * desire`
- 兴趣度不参与概率乘数

2) user 消息
- 低欲望群体触发一次 `cold_start_boost`
- 按兴趣档位恢复 desire（高>中>低）

3) bot 消息
- self-ignore（自己消息不触发自己）
- 其他 bot 消息触发 `drop_other_speak`（小幅下降）

4) 真正发言后
- 说话者执行 `drop_self_speak`（大于 other drop）

5) 边界
- desire 始终 clamp 在 `[0,1]`
- `desire < desire_min_to_speak` 不可发言

---

## 5. 参数优先级

`effective = deepMerge(global_defaults, agent.dynamics_override)`

优先级：
1. 全局默认
2. agent 覆盖
3. （后续可加）管理员热更新

---

## 6. 为什么要脚本化

- 可复盘：每次 allow/deny 都可记录 reason
- 可控：统一油门 `global_pace`
- 可收敛：衰减和恢复一致执行，不依赖模型“自觉”
- 可测试：脚本可离线仿真

---

## 7. 已知限制

- 兴趣判定目前是关键词匹配，语义理解较弱
- 当前模拟为“简化消息流”，未接入真实 Telegram API 延迟/失败重试
- 尚未实现“每日自动重置 desire”或“夜间静默窗口”
