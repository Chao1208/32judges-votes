# ChaosNLI 评审投票数据集 — 32 名 LLM 评审、逐题、含呈现顺序调换臂

（English: [README.md](README.md)。本文件是中文对照版，内容一致。）

**32 名 LLM 评审**（10 个厂商家族）在 **ChaosNLI 三集各 1000 题**（MNLI-m、SNLI、alphaNLI）上的
逐题投票，另附一条**呈现顺序调换臂**——同一批评审在 500 题的子集上，把答案选项换个顺序重答一遍。
合计 221,474 格判断，随高层采集设置与逐文件完整性清单一并发布。

这是论文《How Many Humans Is a Judge Panel Worth?》的数据发布（见[引用](#引用)：论文引本仓库，
本仓库引论文）。发布它的理由很直接：这一线研究至今每篇都要自采一遍逐题投票，票便宜用、贵采。

ChaosNLI 本体**不在**本仓库转发（它是 CC BY-NC 4.0）。我们只发自己的票，按 ChaosNLI 的 `uid`
对齐，并给出抽样 uid 清单与关联脚本。`src/` 另提供离线固定面板分析，安装、
输入要求、失败口径、指标和覆盖范围见 [ANALYSIS.zh-CN.md](ANALYSIS.zh-CN.md)。
需要按 Step 1 到最终对照串联运行时，请直接使用[复现总入口](REPRODUCE.zh-CN.md)与
`python reproduce.py`。复现从已保存的 32-judge 投票开始，全程离线，**模型/API 调用为
0 次**。

## 目录结构

```
votes/<数据集>/<评审>.jsonl        基线臂：32 名评审 × 1000 题 × 3 个数据集
votes_swap/<数据集>/<评审>.jsonl   呈现顺序调换臂：同一批评审，500 题子集
items/<数据集>_uids.txt            抽中的 1000 个 ChaosNLI uid，按抽样顺序
meta/judges.csv                    评审键 → 模型标识、厂商家族、是否更早一代
meta/integrity.json                逐文件 sha256、行数、uid 数、parse_fail 数、各 variant 行数
scripts/verify.py                  按 meta/integrity.json 复核每个文件
scripts/join_chaosnli.py           把票与 ChaosNLI 的百人标注计数关联起来
src/analyze_panel.py               便携固定面板分析命令
src/verify_paper.py                将实际复算值与保存主表比较
meta/analysis/                    保存校准曲线、参考摘要与manifest
ANALYSIS.zh-CN.md                  离线分析说明及覆盖边界
REPRODUCE.zh-CN.md                 Step 1--N复现指南与总入口
reproduce.py                       完整性检查 → 测试 → 论文主表核验
```

`<数据集>` 取 `mnli_m` / `snli` / `alphanli`。

## 记录格式

基线臂（`votes/`），每行一个 JSON 对象：

| 字段 | 含义 |
|---|---|
| `uid` | ChaosNLI 题目 id，也是关联键 |
| `label` | 该评审给的标签：NLI 两集为 `e` / `n` / `c`，alphaNLI 为 `1` / `2` |
| `parse_fail` | 回答里读不出合法标签时为 `true`，**务必看下面的告示** |

调换臂（`votes_swap/`）多两个字段：`variant`（0 = 基线选项顺序）与 `perm`（实际呈现的排列）。
每 (题, variant) 一行。

模型原始回答、推理轨迹、prompt 和采集流水线内部记账字段**不进发布件**。公开记录只保留
`uid`、论文分析实际使用的最终 `label`、`parse_fail`，以及调换臂的 `variant` 与 `perm`。

## 面板

32 名评审、10 个家族（OpenAI 5、阿里 4、Google 4、Moonshot 4、智谱 4、Anthropic 3、DeepSeek 3、
字节 2、xAI 2、MiniMax 1）。`meta/judges.csv` 中历史 `earlier_generation` 标记原样保留，
不能当作独立核验的后端代际或能力证据。

模型标识按请求字符串原样记录，未独立鉴定后端身份和版本。采集使用单条用户消息、
无系统提示、温度0和受限回答格式；逐字提示词与请求代码不放入本公开仓库。
公开行应理解为归档判断记录，不作为每行都是全新服务调用的证据。

## 题目与抽样

每集 1000 题，从该集全部题目里按百人标注分布的熵三分层等比例抽取（seed 42）。
`items/<数据集>_uids.txt` 按抽样顺序列出；投票文件里的每个 `uid` 都保证在该清单内
（`scripts/verify.py` 会核）。

要拿到人类标签分布，先克隆 ChaosNLI，再按 `uid` 关联：

```bash
git clone https://github.com/easonnie/chaos_nli
python3 scripts/join_chaosnli.py --chaosnli path/to/chaosNLI_v1.0 --dataset mnli_m | head -1
```

## 呈现顺序调换臂

同一批评审在 500 题子集上把选项顺序换掉重答：三标签的两集有三种顺序（`variant` 0/1/2），
alphaNLI 只有两个选项、故两种。排列逐条记录、答案已回映射，因此标签语义可与基线臂对读。baseline与presentation的variant=0
是各自保存的快照，不可静默合并或相互替换。

覆盖并不完整，这也正是我们对这条臂的分析用 **31 / 31 / 29** 名而不是 32 名面板的原因：

| 数据集 | 文件数 | 未进该臂面板的评审 | 原因 |
|---|---|---|---|
| `mnli_m` | 32 | `dsv32` | 只采到 `variant` 0（500 行） |
| `snli` | 32 | `dsv32` | 此集数据齐全，但为三集同一面板而一并剔除 |
| `alphanli` | 31 | `dsv32`、`glm52`、`kimik3` | 无文件；只有 `variant` 0；缺 26 行 |

不完整的文件也照原样发布——想换面板口径的人应该看得见当时有什么。

## 用之前值得读的几条告示

**`parse_fail` 那些格的 label 是占位值，不是判断。** 回答里读不出合法标签（或调用反复失败）时，
流水线仍会给出一个 `label`，取自 `uid:judge_key` 的确定性哈希。这些已标记占位不是真实判断。
新增分析CLI默认剔除任一评审存在占位的整道题；论文历史主表保留占位，精确复现必须显式指定
`--failure-policy paper-retained`。基线臂有 6 格（MNLI-m / SNLI / alphaNLI 为 1 / 0 / 5），调换臂 27 格
（11 / 8 / 8）。

**公开仓库只提供最终打分。** 数据中不包含模型原始回答或推理轨迹；下游分析直接使用
`label`，不存在可供重新解析的公开 raw 文本字段。

**温度 0 不等于确定性。** 同一问题重答不一定给同一个词；本档案未独立识别同提示重复调用的
噪声地板。两臂差异可能包含快照、缓存及服务变化，不能单独解释为选项顺序的因果效应。

**这里没有任何排行榜。** 与百人众数的一致率随数据集变化，同一家的名次跨集会重排。
这是票，不是 leaderboard。

## 完整性

```bash
python3 scripts/verify.py
```

对全部 191 个投票文件核 sha256、行数、uid 数、`parse_fail` 数与各 variant 行数，
并核对没有任何投票文件提到抽样清单之外的题。

## 许可

数据（`votes/`、`votes_swap/`、`items/`、`meta/`）：**CC BY 4.0**，见 `LICENSE`。
旧代码（`scripts/`）：**MIT**，见未修改的 `LICENSE-CODE`。
新增分析代码（`src/`、`tests/`）及文档：**MIT**，见 `src/LICENSE`。
ChaosNLI 不在本仓库内、仍按它自己的 **CC BY-NC 4.0** 条款；把我们的票与 ChaosNLI 关联后得到的
派生数据继承那份条款。

## 引用

用了这些票，请同时引论文与本仓库；BibTeX 条目见 [README.md 的 Citing 一节](README.md#citing)
（论文条目的 arXiv 编号待预印本挂出后补，现登记为空缺，不填占位数字）。
另请引 ChaosNLI——题目与人类标签分布出自它。
