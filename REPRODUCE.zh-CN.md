# 串联复现论文的公开固定面板结果

[English](REPRODUCE.md)

这是论文 *How Many Humans Is a Judge Panel Worth?* 公开复现的总入口。**实验从已发布的
32 名 judge 逐题投票开始，模型/API 调用严格为 0 次。** `reproduce.py` 不读取 API
密钥、不发网络请求，全部分析在本地离线完成。

建立环境和单独取得有独立许可的 ChaosNLI 输入，可能在实验开始前涉及下载。一旦这些输入
已落到本地，Step 4 全程离线，API 调用为 0。

## Step 1：克隆仓库

```bash
git clone https://github.com/Chao1208/32judges-votes.git
cd 32judges-votes
```

## Step 2：建立 Python 环境

需要 Python 3.9 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Step 3：单独取得 ChaosNLI

ChaosNLI 保留 CC BY-NC 4.0 条款，本仓库不转发。请从其官方项目取得 ChaosNLI v1.0，
并找到含以下三个文件的目录：

```text
chaosNLI_mnli_m.jsonl
chaosNLI_snli.jsonl
chaosNLI_alphanli.jsonl
```

复现只读取每集已发布 1000 个题目 ID 对应的 `uid`、`label_counter` 和
`majority_label`。

## Step 4：运行全部公开复现步骤

```bash
python reproduce.py \
  --chaosnli /absolute/path/to/chaosNLI_v1.0 \
  --output-dir results/paper-reproduction
```

总入口以 **0 次模型/API 调用**依次执行：

1. 191 个公开投票文件的完整性检查；
2. 11 个分析单元测试；
3. 重新计算 MNLI-m、SNLI、alphaNLI 的固定面板指标，并与论文保存的主表值逐项比较。

成功时终端最后输出 `PASS`，产物写入 `results/paper-reproduction/`：

```text
summary.json
step1_archive_integrity.log
step2_unit_tests.log
step3_paper_table.log
paper-table/paper_comparison.json
paper-table/*_paper-retained.json
```

`paper_comparison.json` 记录每个指标的论文值、复算值、绝对误差和是否通过。默认绝对容差
为 `1e-10`；只有明确需要时才用 `--atol` 修改。
`summary.json` 同时显式记录 `model_api_calls: 0` 与
`network_requests_during_run: 0`。

## Step 5：理解复现结果

该流程复现固定 32-judge 基线面板的 PR、分布误差 `E`、人类分歧量 `J`、`nu_MSE`、
`gamma_co_all`、二元错误有效票数 `n_eff` 和 `nu_H`。投票和人类计数都会重新读取并
按 UID 对齐；`nu_H` 反解公开且经哈希核对的人类校准曲线，不重新生成 Monte Carlo 曲线。

论文历史主表保留了 6 个明确标记的确定性占位标签，所以总入口为精确对照使用
`--failure-policy paper-retained`。新分析默认应使用更安全的 `drop-items`，详见
[ANALYSIS.zh-CN.md](ANALYSIS.zh-CN.md)。

## 复现边界

本流程核验固定完整基线面板和论文保存的主表值，不覆盖呈现顺序分析、选择子面板、厂商家族
分解、新的校准模拟、切分稳定性、成员增量诊断、后续几何/loss 诊断或作图。上述边界也会
写入 `summary.json`；运行成功不能表述成对论文每张图和所有实验的端到端复现。
