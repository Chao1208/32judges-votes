# 离线固定面板分析

[English](ANALYSIS.md)

本包复算论文 EN0.2CH0.4 的固定 32 名评审基线面板指标。输入为仓库公开票及用户自行取得的
ChaosNLI 人类计数；不调用模型、不联网下载。公开包不含原始回答或推理轨迹，分析直接从最终
`label` 分数开始。需要 Python 3.9+ 与 NumPy。

## 运行

```bash
python3 -m pip install -r requirements.txt
python3 src/analyze_panel.py --dataset mnli_m \
  --chaosnli path/to/chaosNLI_v1.0 --output results/mnli_m_clean.json
```

从 <https://github.com/easonnie/chaos_nli> 及其数据下载链接自行取得上游数据。
`--chaosnli` 目录应含 `chaosNLI_mnli_m.jsonl`、`chaosNLI_snli.jsonl` 和 `chaosNLI_alphanli.jsonl`。
也可用 `--human-data path/to/file.jsonl` 传入该集完整或抽样 JSONL。
必需字段为 `uid`、`label_counter`（非负整数、每题合计100）和 `majority_label`。
未出现的计数标签视为0；gold保留该字段及原始平票处理，不能改成计数的首个 `argmax`。
`old_label` 是另一种目标，不是默认gold。

代码若作为论文补充单独提供，加 `--repo-root path/to/32judges-votes` 指向含
`datasets/<数据集>/` 与 `meta/judges.csv` 的公开数据仓库（v1.0-paper 那种顶层 `votes/`、`items/` 的布局同样可用）。从分析代码包目录执行命令即可；
代码和数据无需位于同一父目录。

## 占位失败与论文复现

默认 `--failure-policy drop-items` 剔除任一评审存在 `parse_fail` 的整道题，保留矩形面板。
MNLI-m/SNLI/alphaNLI分别有1/0/5个占位格，影响1/0/5题，所以清洁口径保留999/1000/995题。
占位标签不是真实模型判断。论文主表保留了这些已登记确定性标签，复算时须显式选择：

```bash
python3 src/analyze_panel.py --dataset mnli_m \
  --chaosnli path/to/chaosNLI_v1.0 --failure-policy paper-retained \
  --output results/mnli_m_paper-retained.json
python3 src/verify_paper.py --chaosnli path/to/chaosNLI_v1.0 \
  --output-dir results/paper-verification --verify-archive
```

`verify_paper.py` 重读三集输入并逐项比较 `meta/analysis/reported_values.json`，写出绝对误差，
默认容差 `1e-10`。代码与数据分开时同样支持 `--repo-root`。只核验固定主表，不代表全篇复现。

## 指标与校准边界

残差为 `r[a,i]=onehot(vote[a,i])-h[i]`。未中心化Gram矩阵
`K[a,b]=mean_i <r[a,i],r[b,i]>` 按正对角归一得到 `C`，不是Pearson矩阵。

| 输出 | 定义 |
|---|---|
| PR | `k²/sum(C²)`，实现采用等价的PSD谱式 |
| E | `mean_i ||mean_a r[a,i]||²` |
| J | `mean_i (1-||h[i]||²)` |
| ν_MSE | `J/E`，要求J与E均正 |
| γ_co,all | 各评审残差先跨题中心化；`sum_i ||sum_a r_centered[a,i]||²/(k sum_ai ||r_centered[a,i]||²)` |
| n_eff | supplied gold下二元错误的Pearson相关均值φ̄代入 `k/(1+(k-1)φ̄)` |
| ν_H | 保存的人类条件独立均值PR曲线的线性反解 |

γ_co是原始残差尺度的中心化方差份额，不含全部均值偏差。全one-hot空间计算与正交零和基计算等价。
n_eff分母须大于 `1e-14` 数值正性阈值，更小值按数值退化处理。退化指标输出JSON `null`及明确原因，不将未定义相关强行填0。

校准CSV是EN0.2CH0.4已保存的派生结果：网格2–12、16、24、32、48、64、96、128，每点12复本，种子基42。
本程序只读 `h` 锚曲线，**不重新进行Monte Carlo模拟**。manifest同时检查CSV哈希、题目集合与
人类计数语义指纹。上游JSON空白及额外题目文本不影响语义匹配。

剔题或改变人类参考后不能套旧曲线。因此默认清洁MNLI-m/alphaNLI的ν_H为 `null`，状态
`unavailable_changed_item_set`；SNLI题集未变可读取ν_H。`--no-calibration`可跳过校准读数。
新题集/新参考的曲线重校准不在本包支持范围内。低于首个网格点时数值2配
`nu_H_le_first_grid`，必须读作 **ν_H≤2**；超过网格量程则不给估计。

人类等价值只对指定参考和损失目标成立，不是人类劳动替代率；100人分布是经验参考，不是潜在真理。

## 检查与覆盖范围

```bash
python3 -m unittest discover -s tests -v
python3 scripts/verify.py  # 在数据仓库内运行
```

测试涵盖可手算独立平衡面板、复制与相消、中心化和未中心化区别、退化统计量、gold平票、
缺失/重复UID、非法计数、失败题并集过滤、校准与参考不匹配。单元测试不需要上游数据。

已支持：三集固定基线面板的上述指标，两种占位口径，输入哈希，主表比较。输出仅含指标与哈希，
不含上游题目文本或计数，也不嵌入输入绝对路径。

未覆盖：呈现顺序实验、随机/筛选子面板、家族分解、校准模拟、标签模检验、
跨半题稳定性、增员/排序诊断、后续几何/损失诊断或绘图。完整125,474条呈现档案仍保留；本CLI不执行
论文登记的122,000条筛选。代码并非全论文复现，仍有未覆盖的可复现性工作。

模型名称是请求标识，不代表已独立鉴定
后端版本。部分记录涉及缓存，baseline与presentation-v0是各自快照，不能把每行解释成一次全新调用。
档案没有独立识别同提示重答噪声地板。EN0.2CH0.4主表按本指南的`paper-retained`口径复现，新增CLI默认
`drop-items`用于清洁分析，以本指南明确的口径为准。

本包没有新认证完整上游数据发布版本；记录实际输入文件哈希、选中人类计数/gold语义哈希，
并核对其与已保存校准曲线的参考一致。

## 来源和许可

`src/formulas.py`改编自项目已核验纯数学模块，`src/votes_io.py`保留显式UID严格对齐原则，去掉内部
registry路径和采集依赖。公开入口对退化情况明确检查，无须API配置或密钥。

已发布的投票、题目清单与元数据使用原 `LICENSE` 的 CC BY 4.0；旧scripts使用未改动的 `LICENSE-CODE`（MIT）。
新增src、tests和分析文档使用 `src/LICENSE`（MIT）。meta/analysis的已保存派生摘要使用CC BY 4.0。
不转发ChaosNLI题目和人类计数；其CC BY-NC 4.0条款继续适用，关联数据请勿放入公开包。
