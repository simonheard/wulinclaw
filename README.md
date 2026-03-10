# 武林外传群聊基线（v1）

这套文件是**基线模板**，用于：
1. 创建多 agent 群聊时做 deep copy
2. 长期运行后做人格漂移校对

> 不直接作为运行态状态文件。运行态应复制到各 agent 工作目录再改。

## 目录

- `chat_dynamics.default.json`：全局动力学参数（管理员统一控制）
- `agents/*.yaml`：角色基线（人设、兴趣、override）
- `scripts/dynamics_gate.py`：统一决策与状态更新脚本（概率/欲望不交给 agent 算）
- `scripts/simulate.py`：快速收敛模拟测试
- `docs/INTEGRATION.md`：接入说明
- `docs/DESIGN.md`：完整设计文档（架构/规则/边界）
- `docs/PARAM_TUNING.md`：调参速查
- `docs/MISSING_CHECKLIST.md`：落地前缺漏清单

## alias 映射

- 小白 → 白展堂
- 小红 → 佟湘玉
- 小绿 → 郭芙蓉
- 小棕 → 李大嘴
- 小蓝 → 吕轻侯
- 小紫 → 莫小贝

## 合并规则（建议）

`effective_config = deepMerge(global_defaults, agent_override)`

优先级：
1. 全局默认 `chat_dynamics.default.json`
2. agent 内 `dynamics_override`
3. （可选）临时热更新参数

## 角色校对建议

每周检查：
- 语气是否偏离（口头禅、句长、语气强度）
- 兴趣词是否失真（高频触发是否还符合角色）
- 覆盖参数是否导致异常沉默/刷屏
