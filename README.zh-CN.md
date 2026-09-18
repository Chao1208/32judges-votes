# 32judges-votes — 同一个 32 家判官面板的逐题投票

（English: [README.md](README.md)。本文件是中文对照版，内容一致。）

**同一批 32 名 LLM 评审**，逐题发布，跨多个语料。32 家是这里的不变量，数据集不是——以后还会加。
目前有四个：

| 数据集 | 任务 | 题数 | 臂 | 面板 | 发布层 |
|---|---|---|---|---|---|
| [`chaosnli-mnli-m`](datasets/chaosnli-mnli-m) | 三选一 NLI（`e`/`n`/`c`） | 1,000 | 基线 + 呈现顺序 | 32 | 逐题投票 |
| [`chaosnli-snli`](datasets/chaosnli-snli) | 三选一 NLI（`e`/`n`/`c`） | 1,000 | 基线 + 呈现顺序 | 32 | 逐题投票 |
| [`chaosnli-alphanli`](datasets/chaosnli-alphanli) | 二选一溯因（`1`/`2`） | 1,000 | 基线 + 呈现顺序 | 32 | 逐题投票 |
| [`civil-comments-1000`](datasets/civil-comments-1000) | 二元毒性（`TOXIC`/`NON-TOXIC`） | 1,000 | 基线 | 32 | 仅分数层 |

ChaosNLI 侧合计 221,474 格判断，Civil Comments 侧另有 32,000 格。
[`datasets/index.json`](datasets/index.json) 是机器可读的注册表，逐文件哈希在各数据集自己的
`manifest.json` 里。

这是论文《How Many Humans Is a Judge Panel Worth?》的数据发布（见[引用](#引用)）。发布它的理由
很直接：这一线研究至今每篇都要自采一遍逐题投票，票便宜用、贵采。

源语料一律**不转发**：ChaosNLI 是 CC BY-NC 4.0，按 `uid` 自行关联；Civil Comments 是 CC0，本仓库
只有不可逆的题目哈希与人类汇总值。离线固定面板分析在 `src/`，说明见
[ANALYSIS.zh-CN.md](ANALYSIS.zh-CN.md)；串联复现用[总入口](REPRODUCE.zh-CN.md)与
`python reproduce.py`，全程离线、**模型/API 调用 0 次**。

## 目录结构

```
datasets/index.json                          注册表：每个数据集一行 ＋ 其 manifest 的哈希
datasets/<数据集>/manifest.json              题数、臂、面板、逐文件 sha256（权威记录）
datasets/<数据集>/README.md                  这个数据集是什么、不是什么
datasets/<数据集>/items/uids.txt             题目清单，按抽样顺序
datasets/<数据集>/votes/baseline/*.jsonl     基线臂，一家判官一个文件、一行一条记录
datasets/<数据集>/votes/swap/*.jsonl         呈现顺序调换臂（采到的部分）
panel/panel-<轮次>.json                      每轮采集的 32 家名单
                                             （判官键 → 模型标识、厂商家族）
reference/                                   保存的校准曲线与论文参考值
schema/                                      投票记录、manifest、注册表的 JSON Schema
scripts/verify.py                            按各数据集 manifest 复核每个已发布文件
scripts/build_manifests.py                   重新生成各 manifest 与注册表
scripts/join_chaosnli.py                     把票与 ChaosNLI 的百人标注计数关联起来
src/                                         便携固定面板分析代码
reproduce.py                                 完整性检查 → 测试 → 论文主表核验
ANALYSIS.zh-CN.md / REPRODUCE.zh-CN.md       分析范围；复现总入口
CHANGELOG.md                                 两次发布之间改了什么
```

加一个数据集 = 在 `datasets/` 下加一个目录、在 `scripts/build_manifests.py` 里加一条，然后跑一次。
别的数据集一个文件都不用动。

`<数据集>` 的分析 CLI 键仍是 `mnli_m` / `snli` / `alphanli`。

## 记录格式

逐题投票的数据集里，每家判官一个 JSONL。基线臂每行一个 JSON 对象：

| 字段 | 含义 |
|---|---|
| `uid` | ChaosNLI 题目 id，也是关联键 |
| `label` | 该评审给的标签：NLI 两集为 `e` / `n` / `c`，alphaNLI 为 `1` / `2` |
| `parse_fail` | 回答里读不出合法标签时为 `true`，**务必看下面的告示** |

调换臂（`votes/swap/`）多两个字段：`variant`（0 = 基线选项顺序）与 `perm`（实际呈现的排列）。
每 (题, variant) 一行。

模型原始回答、推理轨迹、prompt 和采集流水线内部记账字段**不进发布件**。公开记录只保留
`uid`、论文分析实际使用的最终 `label`、`parse_fail`，以及调换臂的 `variant` 与 `perm`。

## 面板

32 家判官，每轮采集的名单钉在 `panel/` 里：

| 轮次 | 文件 | 家族构成 |
|---|---|---|
| ChaosNLI | [`panel/panel-chaosnli.json`](panel/panel-chaosnli.json) | OpenAI 5、阿里 4、Google 4、Moonshot 4、智谱 4、Anthropic 3、DeepSeek 3、字节 2、xAI 2、MiniMax 1 |
| Civil Comments | [`panel/panel-civil-comments-1000.json`](panel/panel-civil-comments-1000.json) | OpenAI 7、智谱 5、阿里 4、Anthropic 4、DeepSeek 3、Moonshot 3、字节 2、xAI 2、Google 1、MiniMax 1 |

**规模相同，名单不同。** 两轮相隔约两周半，中转侧模型别名发生漂移：5 个端点在两条链上都已消失
（404 / 无可用渠道），3 个 Google 模型两条链都不可用；替补按探针之前就登记好的同族候选顺序取。
共 6 家不同，逐家差异与家族增减记在 Civil Comments 那个面板文件的 `differs_from_chaosnli_round` 里。
**因此：本仓库里跨数据集的差异不是语料的受控比较**——任务、人类参照、面板构成三者同时不同。

ChaosNLI 名单中历史 `earlier_generation` 标记原样保留，不能当作独立核验的后端代际或能力证据。

模型标识按请求字符串原样记录，未独立鉴定后端身份和版本。采集使用单条用户消息、
无系统提示、温度0和受限回答格式；逐字提示词与请求代码不放入本公开仓库。
公开行应理解为归档判断记录，不作为每行都是全新服务调用的证据。

## 题目与抽样

各数据集的抽样规则写在自己的 README 里。ChaosNLI 三集：每集 1000 题，从该集全部题目里按百人标注
分布的熵三分层等比例抽取（seed 42）；Civil Comments：只取标注人数 ≥ 50 的题（占 train 的 3.92%），
再按毒性比例五层等额抽取 ⟹ **有争议的题被大幅过采，不能读出任何流行度结论**。
`datasets/<数据集>/items/uids.txt` 按抽样顺序列出；投票文件里的每个 `uid` 都保证在该清单内
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

对每个数据集：先核各 manifest 与 `datasets/index.json` 记录的哈希是否一致，再逐个核已发布文件的
sha256、行数、uid 数、`parse_fail` 数与各 variant 行数，核对没有记录带未声明字段、没有 uid 落在题目
清单之外、在场判官与 `panel/` 钉的 32 家名单一致。`scripts/build_manifests.py --check` 在任一
manifest 过期时报错。
目前覆盖 192 个文件。加 `--dataset <数据集>` 只核一个。

## 许可

数据（`datasets/*/votes/`、`datasets/*/items/`、`panel/`、`reference/`）：**CC BY 4.0**，见 `LICENSE`。
旧代码（`scripts/`）：**MIT**，见未修改的 `LICENSE-CODE`。
新增分析代码（`src/`、`tests/`）及文档：**MIT**，见 `src/LICENSE`。
ChaosNLI 不在本仓库内、仍按它自己的 **CC BY-NC 4.0** 条款；把我们的票与 ChaosNLI 关联后得到的
派生数据继承那份条款。

## 沿革

本仓库最初发布名为 `chaosnli-judge-votes`，加入 Civil Comments 后改名；GitHub 对旧地址永久重定向。
改造前的目录树留在 `v1.0-paper` tag 上。两次发布之间的变化见 [CHANGELOG.md](CHANGELOG.md)。

## 引用

用了这些票，请同时引论文与本仓库；BibTeX 条目见 [README.md 的 Citing 一节](README.md#citing)
（论文条目的 arXiv 编号待预印本挂出后补，现登记为空缺，不填占位数字）。
另请引 ChaosNLI——题目与人类标签分布出自它。
