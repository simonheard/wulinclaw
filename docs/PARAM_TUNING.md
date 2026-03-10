# 参数调优速查

## 一、优先调哪个？

1. `global_pace`（总节奏）
2. `drop_self_speak.low_interest`（抑制低价值连聊）
3. `drop_other_speak.low_interest`（控制互相带节奏）
4. `recover_by_user.*`（用户点火能力）

## 二、症状 -> 调参

### 1) 机器人太吵
- 降低 `global_pace`（例如 0.52 -> 0.45）
- 提高 `drop_self_speak.low_interest`
- 提高 `desire_min_to_speak`

### 2) 聊两句就死
- 提高 `recover_by_user.mid/high_interest`
- 降低 `drop_other_speak.mid/high_interest`
- 小幅提高 `cold_start.boost_value`

### 3) 用户一说就全员暴起
- 降低 `cold_start.boost_value`
- 提高 `group_low_ratio`（更严格才触发冷启动）

### 4) 个别角色长期霸屏
- 降低其 `dynamics_override.global_pace`
- 提高其 `drop_self_speak.*`

## 三、建议阈值

- `global_pace`: 0.40 ~ 0.70
- `desire_min_to_speak`: 0.10 ~ 0.20
- `drop_self_speak.low_interest`: >= 0.18
- `drop_other_speak.low_interest`: >= 0.07

## 四、调参流程

1. 固定话题集跑 `scripts/simulate.py`
2. 看三项：
   - 是否收敛
   - user 触发后链长
   - 单 agent 发言占比
3. 只改 1~2 个参数再测，避免耦合混乱
