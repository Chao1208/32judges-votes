# 串联复现论文的公开结果

[English](REPRODUCE.md)

这是论文 *How Many Humans Are 32 LLM Judges Worth?* 公开复现的总入口。**实验从已发布的
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
`majority_label`。CC-1000 不需要外部输入：它的分数层已带有人类毒性计数。

## Step 4：运行全部公开复现步骤

```bash
python reproduce.py \
  --chaosnli /absolute/path/to/chaosNLI_v1.0 \
  --output-dir results/paper-reproduction
```

总入口以 **0 次模型/API 调用**依次执行：

1. 全部公开投票文件的完整性检查；
2. 21 个分析单元测试；
3. 重新计算 MNLI-m、SNLI、alphaNLI 的固定面板指标，并与论文保存的主表值逐项比较；
4. 固定池渐近线、闭式校准、CC-1000 固定面板和完整的面板选择实验，每项既与保存的未取整值
   比较，也与论文印刷的数字比较。

第 4 步在四个数据集上各枚举全部 C(32,5) = 201,376 与 C(32,7) = 3,365,856 个面板，
笔记本上约 2.5 分钟；其余步骤只需数秒。成功时终端最后输出 `PASS`，产物写入
`results/paper-reproduction/`：

```text
summary.json
step1_archive_integrity.log
step2_unit_tests.log
step3_paper_table.log
step4_extended.log
paper-table/paper_comparison.json
paper-table/*_paper-retained.json
extended/extended_comparison.json
```

`paper_comparison.json` 记录每个指标的论文值、复算值、绝对误差和是否通过。默认绝对容差
为 `1e-10`；只有明确需要时才用 `--atol` 修改。`extended_comparison.json` 列出第 4 步
的每项检查及其类型：`saved_unrounded`（在 `--atol` 之内）或 `printed_in_paper`（在印刷
末位的半个单位之内）。
`summary.json` 同时显式记录 `model_api_calls: 0` 与
`network_requests_during_run: 0`。

## Step 5：理解复现结果

**固定面板（第 3 步）。** 该流程复现固定 32-judge 基线面板的 PR、分布误差 `E`、人类分歧量
`J`、`nu_MSE`、`gamma_co_all`、二元错误有效票数 `n_eff` 和 `nu_H`。投票和人类计数都会
重新读取并按 UID 对齐；`nu_H` 反解公开且经哈希核对的人类校准曲线，不重新生成 Monte Carlo
曲线。

论文历史主表保留了 6 个明确标记的确定性占位标签，所以总入口为精确对照使用
`--failure-policy paper-retained`。新分析默认应使用更安全的 `drop-items`，详见
[ANALYSIS.zh-CN.md](ANALYSIS.zh-CN.md)。

**固定池渐近线（第 4.2 节、附录 C）。** `src/formulas.py:pool_asymptote` 固定
`mu2 = ||平均残差||^2`、成员平均方差 `v_bar` 与平均中心化协方差 `rho_bar`，于是
`E(m) = mu2 + v_bar (1/m + (1-1/m) rho_bar)`。它给出 `nu_MSE` 的中心化与未中心化极限、
观测值占中心化极限的份额，以及从 32 名扩到 64 名 judge 的增量。

**闭式校准（第 3.3 节）。** `closed_form_delta` 由人类分布计算
`delta = <s2 - 2 s3 + s2^2> / (n <1 - s2>^2)`，`nu_closed_form` 精确反解
`PR0(m) = m / (1 + (m-1) delta)`，在 `PR >= 1/delta` 处为 NaN。

**CC-1000（第 4.9 节）。** `src/civil_comments.py` 读取经哈希核对的分数层，题目按
`id_sha256` 排序、judge 按 key 排序，取 `h_i = (1 - p_i, p_i)`，`p_i` 为标注者中判毒的
比例；gold 为 `1[p_i > 0.5]`，`n_eff` 剔除 `p_i = 0.5` 的 10 题。有限标注纠偏为
`(J + b) / (E - b)`，`b = mean((1 - ||h_i||^2) / (M_i - 1))`。`nu_H` 反解保存的 CC-1000
Monte Carlo 曲线 `reference/calibration_curve_civil_comments.csv`。

**面板选择（第 4.10 节、表 7–8、附录 A.7）。** `src/selection.py` 重算每个选出的面板和
每个枚举计数，定义如下：

- `acc` 从不打破并列。每题得分为 `1[gold ∈ M] / |M|`，`M` 为众数标签集合，即均匀打破
  并列时的期望。因 `|M| <= 3`，乘以 `lcm(1,2,3) = 6` 后为整数，故 `acc_int_sum_lut6`
  是精确整数和，`acc = acc_int_sum_lut6 / (6n)`。这与固定面板表所用的确定性哈希多数票
  不同。
- `nu_H_closed_form` 反解闭式参照曲线，而非 `reference/calibration_curves.csv` 的 Monte
  Carlo 网格；两者在四个完整 32-judge 面板上相差 0.027%–0.077%，且闭式在不足两次独立
  抽样处仍然精确，部分基线正落在那里。
- `E` 为面板分布误差，`nu_MSE = J / E`；`omega_bar` 为成员残差能量均值；`q_bar` 为归一化
  残差 Gram 矩阵非对角元平方的均值，`PR = k / (1 + (k-1) q_bar)`。
- `S0` 取单体准确率最高的 `k` 名，并列按 judge key。候选集是 `S0` 至多换两名成员的邻域，
  大小 `k(32-k) + C(k,2)C(32-k,2)`，先列换一名的，同类内先按换出者、再按换入者排序。
- 规则 A 在 `acc > acc(S0)` 的候选中取 `nu_H` 最大；规则 E 在同一集合中取 `E` 最小；
  规则 D 取 `acc` 最大，再取 `nu_H` 最大。仍并列时取上述顺序中的第一个。
- `in_joint_improvement_set` 标记该面板是否在准确率和 `nu_H` 上都严格优于 `S0`；`S0`
  本身留空。

`reference/panel_selection.csv` 发布选出的面板，每个（数据集, k, 规则）一行，不跑第 4 步
也能核对。`judge_keys` 可关联到 `panel/*.json` 与投票文件。

## 复现边界

本流程核验固定完整基线面板、论文保存的主表值、固定池渐近线、闭式校准、CC-1000 固定面板
和面板选择实验，不覆盖呈现顺序分析、随机子面板曲线、厂商家族分解、新的校准模拟（Monte
Carlo 曲线从 `reference/` 读取）、切分稳定性、成员增量诊断、平票率依据、后续几何/loss
诊断或作图。上述边界也会写入 `summary.json`；运行成功不能表述成对论文每张图和所有实验的
端到端复现。
