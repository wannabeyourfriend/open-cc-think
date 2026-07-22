# 实验进度

## 2026-07-22

- 已完成 Claude Sonnet 4.6 两个 Fermi 问题的直接跨进程签名重放。
- 已确认直接重放不是完整的 R1/R2/R3/R4 条件协议。
- `implement_conditioned_replay` 子代理正在实现完整四阶段协议，改动范围限定为 `recover_cot.py`、`config/`、`prompts/`。
- `audit_protocol` 子代理第一次审查被自动分类中止，现已改写为纯实验方法与 Bedrock 消息合法性审查并重新运行。
- 工作树中已有约 535 个 tracked 数据、旧实验和文档文件处于删除状态；这些被视为已有清理工作，不回滚。
- 下一步：接收实现、执行静态与 mocked 测试、按审查清单修正、再运行 Claude Sonnet 4.6 实验并记录结果。
- 状态检查：两个子代理仍在运行，尚未报告实现完成或新的阻塞。
- 已要求实现代理优先交付可本地测试的最小完整协议；如 Bedrock 不接受某种伪历史结构，必须在结果中显式记录 protocol deviation。
- 独立方法审查已完成：同轮拼接两个独立 signed blocks 只能作为 `synthetic_splice` 结构探针，不能作为主实验。
- 主实验验收口径已修正为 exact sequential lineage：R1、R2、R3 必须沿真实连续前缀生成；R4 必须追加 R3 的真实完整响应后追问。
- Canary 只验证输出边界，不证明内容来源；最终结论固定为 signed-state recovery candidate，并强制 `ground_truth_cot_proven=false`。
- 已把审查清单发给实现代理，要求至少实现 direct、signed priming、text-only priming、unsigned target、corrupted target 等配对条件。
- `implement_conditioned_replay` 子代理在交付前被自动安全分类中止；其可能已留下部分工作树改动，现由主代理接管审查、补全和验证。
- 已确认 `audit_protocol` 完成；当前没有仍在运行的子代理。下一步先审查限定路径差异，避免把未完成实现直接用于线上实验。
- 实现子代理再次被自动安全分类中止，未交付可用代码；主代理已接管完整协议实现。
- Git 清理审查确认旧结果并未丢失，而是完整保存在本地且被忽略的 `archive/`；其中 `archive/experiments/local/live-fermi-smoke/` 含先前直接重放结果。
- 已识别本地归档中的 raw signature/checkpoint 权限偏宽，收尾时将收紧为仅当前用户可读写，并在 `.gitignore` 显式加入根级 `/archive/`。
- 已修正 blind replay：现在会清空完整历史前缀中所有 `reasoningText.text`，不再只清空目标轮摘要，避免 R1/R2 历史摘要成为可见混淆项。
- 当前正在实现真实连续 lineage 的 conditioned harvest/replay、R4 元认知追问及配对消融；尚未启动新的线上调用。
