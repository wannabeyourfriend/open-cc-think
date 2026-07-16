# 签名回放式完整 CoT 轨迹采集的研究依据

本文档统一约定 Signature-CoT 流水线所用的术语、校准数据来源与实验对照方法。生产目标是
Harbor 平台上的 Terminal-Bench 2.0；但提示词（prompt）的选择必须在**独立的数据**上进行，
以确保该基准不会被当作优化集使用。

## 我们究竟在测量什么

本项目会保存三种彼此**不可互换**的模型输出：

1. **供应商 CoT 摘要**：Claude Sonnet 4.6 在 `thinking.display="summarized"` 下返回的可读文本。
2. **可见的回答 / 动作**：供环境使用的助手文本与结构化工具调用。
3. **签名全跨度还原**：通过回放**完整签名的决策状态**、并要求模型输出两个隐藏的边界金丝雀
   （canary）标记，从而诱导出的文本。

技术依据如下：AWS 文档指出，Converse 的 `reasoningContent.reasoningText.signature` 必须连同
**未经改动的先前消息**一起回传，才能保持推理连续性；Anthropic 文档则指出，Sonnet 4.6 返回的是
**摘要**而非完整内部思考，而 `display="omitted"` 与 `display="summarized"` 携带的是**同一个签名**。
本项目正是从这一技术切口切入研究：

- [Amazon Bedrock Converse 推理内容](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Amazon Bedrock 自适应思考](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-adaptive-thinking.html)
- [Claude 扩展思考的展示与摘要](https://platform.claude.com/docs/en/docs/build-with-claude/extended-thinking)

需要强调：**边界完整的还原并不等于对供应商原文的密码学级证明**。即便在还原出的跨度之内，
模型仍可能省略、改写或编造内容。因此，产物中该字段被标注为 `signed_full_cot_recovery`，
而**绝不**标注为 `ground_truth_cot`。

## 相关文献

### CoT 的有效性与忠实性

- Wei 等，[Chain-of-Thought Prompting Elicits Reasoning in Large Language
  Models](https://arxiv.org/abs/2201.11903)：在算术、常识与符号任务上确立了 CoT 提示方法。
- Yao 等，[ReAct](https://arxiv.org/abs/2210.03629)：将推理与动作交错进行，是决策级终端轨迹在
  概念上最接近的基线。
- Turpin 等，[Language Models Don't Always Say What They
  Think](https://arxiv.org/abs/2305.04388)：表明看似合理的解释可能会隐去真正起因的因果影响。
- Lanham 等，[Measuring Faithfulness in Chain-of-Thought
  Reasoning](https://arxiv.org/abs/2307.13702)：通过对 CoT 施加干预来评估忠实性，发现其随任务与
  模型有显著差异。
- Korbak 等，[Chain of Thought Monitorability: A New and Fragile Opportunity for AI
  Safety](https://arxiv.org/abs/2507.11473)：主张保留可监控的推理，同时警示这只是一个不完善的信号。
- OpenAI 的[可监控性评估](https://openai.com/index/evaluating-chain-of-thought-monitorability/)：
  将「仅 CoT」「仅动作」「二者结合」三类观测分开。本项目的轨迹 schema 保留了同样的区分。

### 提示词优化

- Zhou 等，[Automatic Prompt Engineer](https://arxiv.org/abs/2211.01910)：把指令当作程序，
  并在评估集上进行选择。
- Yang 等，[OPRO](https://arxiv.org/abs/2309.03409)：让 LLM 依据带评分的历史提示来提出新提示。
- Fernando 等，[PromptBreeder](https://arxiv.org/abs/2309.16797)：对任务提示与变异提示进行演化。

在首轮受控扫描中，本项目采用一种更小、更可审计的方法：**冻结的候选池、在相同签名上做配对评估、
按场景做宏平均评分、逐次减半（successive halving），以及最终留出的一段校准切片**。生成式的
提示变异只有在该基线稳定之后才会引入。

### 已有的推理与智能体轨迹数据

- [OpenThoughts](https://arxiv.org/abs/2506.04178)：研究跨数学、代码、科学领域的开放推理数据配方。
- [OpenCodeReasoning](https://arxiv.org/abs/2504.01943)：研究代码推理的蒸馏与数据过滤。
- [SWE-Gym](https://arxiv.org/abs/2412.21139)：发布可执行的软件工程任务与智能体轨迹。
- [R2E-Gym](https://arxiv.org/abs/2504.07164)：构建过程化的仓库级环境与轨迹。
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)：评测真实的终端智能体；
  新的 Terminal-Bench 2.0 运行使用 [Harbor](https://www.harborframework.com/docs/tutorials/running-terminal-bench)。
- Harbor 的 [ATIF v1.7 RFC](https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md)
  是输出契约：**一次原始 LLM 推理对应一个 ATIF 智能体步骤**。

这些数据集大多只包含模型产出的理由（rationale）或可见的 ReAct 思考。它们并未提供本项目所针对的
组合：在**同一条**已验证的 ATIF 记录中，同时包含供应商摘要、签名状态的全跨度还原、精确的工具
协议，以及可见回答。

## 冻结的校准数据来源

已入库的清单（manifest）每个场景包含 12 个实例，共 36 个：

| 场景 | 来源 | 选用理由 |
| --- | --- | --- |
| 代码 | [OpenAI HumanEval](https://github.com/openai/human-eval) | 紧凑、确定性的代码提示；与 Terminal-Bench 相互独立 |
| 数学 | [OpenAI GSM8K 训练集](https://github.com/openai/grade-school-math) | 多步算术，且最终答案可解析 |
| 对话 | [LMSYS MT-Bench](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge) | 涵盖非代码、非数学类别的多轮开放式对话 |

实例通过固定随机种子与 SHA-256 排序，从官方源文件中**确定性地**选出。数学使用 GSM8K 的训练集；
对话层（chat stratum）则排除 MT-Bench 的数学、代码与推理类别。所有源文件的字节哈希都存入清单。

## 优化流程

1. 用 Sonnet 4.6，在自适应思考、高强度（high effort）、`display="summarized"` 下，对每个固定
   实例采集一次。
2. 为每个决策保留其精确前缀、助手内容、签名、可见回答 / 动作，以及工具结果（tool-result）桥接。
3. 在**每个场景的前两个实例**上评估全部候选提示词。
4. 保留得分前半，在**每个场景的接下来两个实例**上评估幸存者。
5. 再保留前半，在**每个场景的接下来四个实例**上评估决赛入围者。
6. 冻结胜出者，并在**每个场景剩余的四个实例**上报告其表现。
7. 排名依据：场景宏平均有效率、双金丝雀成功率、质量、覆盖率代理指标、拒答率、泄漏率与波动性。
   **不要**用抽取提示去优化答案正确性。
8. 只要有任一原始决策缺少签名，或有任一还原决策缺少有序的起始 / 结束金丝雀，就**拒绝**该条
   生产轨迹。

原始智能体指标与抽取 / 回放指标需**分开报告**。抽取调用**绝不**作为智能体动作插入 ATIF 轨迹中。