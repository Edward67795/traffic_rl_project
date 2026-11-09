<!-- Snapshot of the "ESBMC · Edward" tab of the shared plan doc (rev 20, 2026-11-09).
     The live doc is the source of truth; progress boxes are ticked there, not here.
     Changed since the 11-06 snapshot: E10 rewritten after the TA's proposal feedback
     (LLM-1 bug finding, LLM-2 repair loop, LLM-3 record of LLM use). -->

# ESBMC 计划（Edward）

11/15 前要在 ESBMC 里拿到 G2、T1、C1 三个反例并在 SUMO 里复现；11/29 前完成 v1 修复和所有性质的复验。代码全文在子 tab「ESBMC 代码」。

&#91;embedded content: ESBMC 验证闭环 · 6 个步骤，1 个判断\]

E6 的 5 个反例里有 4 个在 SUMO 里直接复现。G2 那个复现不了，所以走了一次 E7：把 SUMO 的静态程序加进 stub，再用同一组 harness 重跑。

## E0–E2 环境与安装

这三步都是一次性准备，合计约 1 小时。命令全部在 macOS 的 Terminal（zsh）里执行；`#` 后面的中文是注释，复制时一起贴也没关系。

### E0 Mac 环境准备

- [ ] **E0.1 安装 Xcode Command Line Tools**（提供 git 和 C 编译器）

```bash
xcode-select -p || xcode-select --install   # 已安装会打印路径；未安装会弹窗，点「安装」
git --version
```

完成标准：`git --version` 打印出版本号。

- [ ] **E0.2 安装 Homebrew**（ESBMC 和 Python 都用它装）

```bash
brew --version || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# 下面两行只在刚刚新装 Homebrew 时执行
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
brew --version
```

完成标准：`brew --version` 打印版本号，且 `which brew` 是 `/opt/homebrew/bin/brew`。

- [ ] **E0.3 安装 Python 3.12 和 GitHub CLI**

```bash
brew install python@3.12 gh
python3.12 --version     # 预期 Python 3.12.x
gh auth login            # 依次选 GitHub.com → HTTPS → Login with a web browser
gh auth status           # 预期 Logged in to github.com
```

ESBMC 的 Python 前端要求 Python 3.10 以上，macOS 自带的是 3.9，所以单独装 3.12。

- [ ] **E0.4 确认磁盘空间**

```bash
df -h ~                  # Avail 一列至少 8 GB
```

ESBMC 及其依赖大约占 3 GB，大头是 llvm；Python 环境加 SUMO 不到 1 GB。实际占用在最后的「清理」一节用命令实测。

### E1 拉代码、建分支、Python 环境

- [ ] **E1.1 clone 仓库**

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/Edward67795/traffic_rl_project.git
cd traffic_rl_project
git log --oneline -1     # 预期：643ba4d add paper
```

- [ ] **E1.2 建 `verification` 分支并推送，邀请队友**

```bash
git switch -c verification
git push -u origin verification
```

然后在 GitHub 网页：repo → Settings → Collaborators → Add people，填队友的 GitHub 用户名。他接受邀请后才能 push。

- [ ] **E1.3 建 Python 虚拟环境，安装 SUMO 和工具**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install eclipse-sumo==1.28.0 traci==1.28.0 sumolib==1.28.0 gymnasium numpy hypothesis mypy pylint
echo 'export SUMO_HOME="$(python -c "import sumo; print(sumo.SUMO_HOME)")"' >> .venv/bin/activate
deactivate && source .venv/bin/activate     # 让 SUMO_HOME 生效
sumo --version | head -1                    # 预期：Eclipse SUMO sumo 1.28.0
```

`eclipse-sumo` 1.28.0 有 macOS arm64 的预编译包（要求 macOS 15 以上），不用单独装 SUMO。以后每次开新终端，先执行 `cd ~/projects/traffic_rl_project && source .venv/bin/activate`。

- [ ] **E1.4 搭目录骨架并第一次提交**

```bash
mkdir -p verification/docs verification/common \
  verification/esbmc/model verification/esbmc/harnesses verification/esbmc/scripts \
  verification/esbmc/baselines verification/esbmc/results/raw \
  verification/spin/models verification/spin/scripts verification/spin/results
cat >> .gitignore <<'EOF'

# verification workspace
.venv/
.hypothesis/
pan
pan.*
*.trail
_spin_nvr.tmp
EOF
```

接着从 `verification_scaffold.zip`（E3.1 用的同一个包，先下载到 `~/Downloads`）里只取出三个说明文件：`README.md` 写怎么复现全部结果，`CLAUDE.md` 是给 Claude Code 的项目说明（和「总览与约定」里的 AI 协作协议一致），`properties.md` 是性质目录。其余代码（包括上一轮的 `reproduce_v0_findings.py` 和 `param_sweep_maxgreen_fix.py`）等 E3.1 再放。

```bash
unzip -o ~/Downloads/verification_scaffold.zip \
  verification/README.md verification/CLAUDE.md verification/properties.md -d .
```

```bash
printf '@verification/CLAUDE.md\n' > CLAUDE.md   # 根目录一行：Claude Code 在根目录启动时就加载 verification/CLAUDE.md
git status --short    # 只应看到 .gitignore、CLAUDE.md 和 ?? verification/；看到 .venv 就先停下来检查 .gitignore
git add .gitignore CLAUDE.md verification/README.md verification/CLAUDE.md verification/properties.md
git commit -m "common: scaffold verification workspace"
git push
```

原 `.gitignore` 已经忽略 `*.log`、`logs/` 和 `build/`。所以 ESBMC 的原始输出一律存成 `results/raw/*.txt`，否则不会被提交。

- [ ] **E1.5（可选）给 Claude Code 装 ESBMC 插件**

在 repo 目录里启动 `claude`，依次输入：

```text
/plugin marketplace add esbmc/agent-marketplace
/plugin install esbmc-plugin@esbmc-marketplace
```

这是 ESBMC 官方的 Claude Code 插件，带 `/verify`、`/audit` 命令和一份 ESBMC 使用参考。以后把步骤交给 Claude Code 时，它可以直接调用 ESBMC。

### E2 安装 ESBMC

- [ ] **E2.1 用 Homebrew 安装（首选）**

```bash
brew install esbmc
esbmc --version          # 记下版本号，写进 results.csv 的 notes
which esbmc              # 预期 /opt/homebrew/bin/esbmc
```

官方 formula 为 Apple Silicon 提供预编译包，会顺带装上 llvm、boost、bitwuzla 等依赖，并自带 Z3 和 Bitwuzla 两个求解器。

- [ ] **E2.2 Python 前端 hello test**

```bash
mkdir -p /tmp/esbmc-hello && cd /tmp/esbmc-hello
cat > ok.py <<'EOF'
def main() -> None:
    x: int = nondet_int()
    __ESBMC_assume(x > 0 and x < 100)
    assert x + 1 > x

main()
EOF
cat > bad.py <<'EOF'
def main() -> None:
    x: int = nondet_int()
    __ESBMC_assume(x > 0 and x < 100)
    assert x != 42

main()
EOF
PY=~/projects/traffic_rl_project/.venv/bin/python
esbmc ok.py  --python "$PY"    # 预期最后一行：VERIFICATION SUCCESSFUL
esbmc bad.py --python "$PY"    # 预期：VERIFICATION FAILED，反例里 x = 42
cd ~/projects/traffic_rl_project
```

`--python` 指定解析 Python 用的解释器；不写时，ESBMC 用 PATH 里的 `python3`。

- [ ] **E2.3 E2.1 失败时的后备方案（按顺序试）**

| 方案 | 做法 | 什么时候用 |
| --- | --- | --- |
| B 官方 release 包 | `curl -L -o esbmc-macos.zip https://github.com/esbmc/esbmc/releases/latest/download/esbmc-macos.zip`；解压后执行 `xattr -dr com.apple.quarantine <目录>`；用 `otool -L <目录>/bin/esbmc` 查缺哪些 Homebrew 动态库，缺什么 `brew install` 什么 | brew 的预编译包装不上 |
| C 源码编译 | `git clone --depth 1 https://github.com/esbmc/esbmc.git ~/tools/esbmc-src && cd ~/tools/esbmc-src && ./scripts/build.sh -b Release -c 21`，产物在 `release/bin/esbmc` | 需要比 brew 更新的版本 |
| D Docker | 装 OrbStack（`brew install orbstack`），在 Ubuntu 24.04 容器里用 `esbmc-linux-armv8.zip`（静态链接，自带依赖） | 本机怎么都装不上 |

用了 B、C 或 D，把 `esbmc` 的实际路径写进 `verification/CLAUDE.md` 的 Environment 一节。

## E3–E4 Smoke test 与 SUMO 复现

E3 确认你装的 ESBMC 支持模型用到的每一个 Python 特性；E4 在真实 SUMO 里复现 v0 的问题，给 E6 的反例当对照。下面所有脚本都已经在 ESBMC 8.6.0 + SUMO 1.28 上跑通。

### E3 放入代码并跑 smoke test

- [ ] **E3.1 把脚手架放进 repo**

解压我发给你的 `verification_scaffold.zip` 到 repo 根目录（模型、harness、补丁和 run\_esbmc.py 与「ESBMC 代码」子 tab 逐字一致，其余脚本的全文只在 zip 里），然后提交。

```bash
cd ~/projects/traffic_rl_project && source .venv/bin/activate
unzip -o ~/Downloads/verification_scaffold.zip -d .
git switch -c esbmc/e3-scaffold
git add verification
git commit -m "esbmc: add model, traci stub, harnesses and runner scripts"
git push -u origin esbmc/e3-scaffold     # 然后开 PR 合并到 verification
```

- [ ] **E3.2 跑 smoke test**

```bash
python verification/esbmc/scripts/smoke_test.py | tee verification/esbmc/results/raw/smoke_test.txt
```

预期最后一行是 `13 of 13 cases ok`（我这边 11/4 重跑过一遍）。有 5 行预期是 FAIL 或 ERROR：第 4、8 行确认 ESBMC 能抓到错误；第 10–12 行记录已知局限，分别是拼接后列表的元素值不精确（会报假反例）、方法名叫 `set` 会让前端报错、`__ESBMC_cover` 可达时会被计为 failed。如果 brew 装的版本在某行显示 MISMATCH，把那行贴到「总览」的阻塞表。

- [ ] **E3.3 记住这六条 ESBMC-Python 规则**（都是跑通这套代码时踩出来的，也是报告里 ease of use 的素材）

| 现象 | 原因 | 本项目的做法 |
| --- | --- | --- |
| 一个 4 步的 harness，Z3 要算 55 秒以上 | Python 对象被编码成 struct，分支合并时产生整个 struct 的 ite | 默认加 `--tuple-node-flattener`，求解降到 0.03 秒 |
| 内层 `range(self.delta_time)` 被展开到全局 bound | 对象字段里的常数不会被常量传播 | `run_esbmc.py` 用 `--show-loops` 自动算出每个循环的 `--unwindset`；unwinding assertion 保持开启，bound 不够时会报错而不是假 PASS |
| 字符串和 dict 操作让公式涨到 6 GB 以上 | 字符串是 C 字符数组，每次比较都展开 14 次循环 | 构建时把模型里 7 行字符串代码改写成整数编码，由 S0 引理 harness 证明等价 |
| 方法名叫 `set` 时报 `migrate expr failed: constant` | 和内置 `set` 冲突 | 不用 `set` 作方法名 |
| 自己写的 `nondet_in()` 报 `NameError: name 'in'` | `nondet_<类型>` 被当成内建函数 | 辅助函数改名 `choose_int()` |
| `--k-induction` 只剩 base case，结果 UNKNOWN | 循环通过指针写对象字段时，inductive step 被关掉 | 手写一步归纳的 harness（E8.4） |

### E4 在 SUMO 里复现 v0 的问题

- [ ] **E4.1 跑复现脚本**

```bash
python verification/common/reproduce_v0_findings.py . 2>&1 | grep -v -i "warning\|retrying" | tee verification/esbmc/results/raw/sumo_repro_v0.txt
```

预期看到四段输出：

| 段 | 关键行 | 对应问题 |
| --- | --- | --- |
| A | 第 13 步 `phase_duration= 65 ... exceeds max_green`；第 7 步起 SUMO 显示 yellow / EW-green，`current_phase` 仍是 0 | F1、F2 |
| B | `env.current_phase=2, SUMO shows NS-green`，信号出现 NS-green → yellow → NS-green | F3 |
| C | `NS-green → EW-green`，中间没有 yellow | F4 |
| D | `EW-green@t=46[0] → yellow@t=51[online] → EW-green@t=54[online]` | F2 |

- [ ] **E4.2 跑 F5 的参数穷举**

```bash
python verification/esbmc/scripts/param_sweep_maxgreen_fix.py | tee verification/esbmc/results/raw/param_sweep.txt
```

预期：`fix=none` 48 个失败配置，`fix=naive` 24 个，`fix=lookahead` 4 个；最后一行列出的 4 个配置，正好就是 lookahead 失败的那 4 个。

- [ ] **E4.3 提交**

```bash
git add verification/esbmc/results/raw
git commit -m "esbmc: record smoke test and SUMO reproduction of v0 findings"
git push
```

## E5 建模：v0 抽取、traci stub、一致性测试

模型 = 原 `environment.py` 的控制逻辑（逐行保留）+ 一个按秒运行的 SUMO 替身。一致性测试证明：L1 替身和真 SUMO 在每一秒显示的信号都相同（30 组随机动作序列中 0 组不一致）。

- [ ] **E5.1 弄清楚每个文件的作用**

| 文件 | 作用 |
| --- | --- |
| `esbmc/model/env_core_v0.py` | 从 `src/environment.py`（commit `643ba4d`）抽取的控制逻辑，每行注释对应的原行号 |
| `esbmc/model/traci_stub.py` | SUMO/TraCI 替身：三个 TraCI 调用、每秒一次的性质监控、可选的静态程序（L1） |
| `esbmc/model/EXTRACTION.md` | 抽取对照表：原行号 → 模型行 → 改动类型和理由 |
| `esbmc/scripts/run_esbmc.py` | 拼接 stub + 模型 + harness，做整数编码改写，算循环 bound，跑 ESBMC，写 CSV |
| `esbmc/scripts/py_sim.py` | 同一个 harness 在 CPython 里随机跑，是随机测试对照 |
| `esbmc/scripts/conformance_test.py` | 模型对真 SUMO 的逐秒一致性测试 |
| `esbmc/scripts/ce_to_actions.py` | 从 ESBMC 反例里取出动作序列和参数 |
| `common/replay_in_sumo.py` | 把动作序列放回真 SUMO，用同一套监控代码检查性质 |

抽取的边界：只保留读写控制状态（`current_phase`、`phase_duration`、`current_step`、`last_action`）或信号灯的语句。特征、奖励、行人（默认关闭）和 gym/numpy 都删掉，它们不影响控制状态。

- [ ] **E5.2 看一遍整数编码改写**

ESBMC 运行时，`run_esbmc.py` 会把模型里 7 行字符串和 dict 代码换成整数编码（表 `INT_REWRITES`），其余代码不动。改写前后等价由 S0 引理 harness 证明。构建出的完整文件在 `verification/esbmc/build/<id>.py`，可以直接打开看。

```bash
python verification/esbmc/scripts/run_esbmc.py S0-strings-str    # 预期 PASS；我这边两次分别 23 秒和 64 秒，求解时间有波动
```

- [ ] **E5.3 一致性测试：L0 会分叉，L1 不会**

```bash
python verification/esbmc/scripts/conformance_test.py --model v0 --level L0 --runs 30 2>&1 | grep -v -i "warning\|retrying"
python verification/esbmc/scripts/conformance_test.py --model v0 --level L1 --runs 30 2>&1 | grep -v -i "warning\|retrying"
```

预期：`v0/L0: 10 of 30 runs diverge`，第一处分叉在第 43 秒（SUMO 显示 `yyyyrrryyyyrrr`，模型还是绿灯）；`v0/L1: 0 of 30 runs diverge`。L0 的分叉就是发现 F2 的过程，对应课件 F-Soft 那页的 environment refinement。

- [ ] **E5.4 CPython 下的快速自检**

```bash
python verification/esbmc/scripts/py_sim.py h_G2 --version v0 --trials 3000 --seed 7
```

预期：`VIOLATION after 365 trials: AssertionError: G2: observed green longer than max_green`。这一步不依赖 ESBMC，用来确认 harness 本身没写错。

- [ ] **E5.5 提交**

```bash
git add verification/esbmc
git commit -m "esbmc: add conformance test results for L0 and L1 stubs"
git push
```

## E6 v0 性质验证与反例回放

默认参数、L0 替身下，ESBMC 在 16 个决策步内证明 S1、T1、T2、G1、C1 成立，并给出 G2、L1、R1、P1 的反例。放开参数或动作范围后，T1、T2、C1 也有反例。需要回放的 5 个反例里，4 个在真 SUMO 里原样复现；剩下 G2 那个是 L0 环境模型太粗造成的假反例，由 E7 处理。

- [ ] **E6.1 看套件里有什么**

```bash
python verification/esbmc/scripts/run_esbmc.py --list
```

每一项是：ID、性质、harness、模型版本、参数覆盖、ESBMC 参数、预期结果。`@auto` 表示循环 bound 自动计算。

- [ ] **E6.2 跑 v0 的 13 项**

```bash
python verification/esbmc/scripts/run_esbmc.py S1-v0 T1-v0 T1-v0-y0 T2-v0 T2-v0-any G1-v0 G2-v0 \
  L1-v0 C1-v0 C1-v0-any R1-v0 P1-v0 V0-cover-v0
```

预期结果如下。时间来自我这边 2 核 Linux 的实测，M4 应该更快。每一项都会追加到 `results/results.csv`，原始输出在 `results/raw/<ID>.txt`。

| ID | 结果 | 反例步数 | 时间 | 说明 |
| --- | --- | --- | --- | --- |
| S1-v0 | PASS | — | 3.7 s | 只会出现 4 种合法信号 |
| T1-v0 | PASS | — | 3.7 s | 默认参数下换方向都经过黄灯 |
| T1-v0-y0 | FAIL | 4 | 3.5 s | F4：`yellow_time=0` 时 NS 绿直接变 EW 绿 |
| T2-v0 | PASS | — | 4.0 s |  |
| T2-v0-any | FAIL | 16 | 4.4 s | F3：越界动作制造同方向的假黄灯 |
| G1-v0 | PASS | — | 4.3 s |  |
| G2-v0 | FAIL | 11 | 5.2 s | F1：一直保持，司机看到的绿灯超过 60 s |
| L1-v0 | FAIL | 16 | 6.9 s | F1 的另一面：一个方向等了 66 s 以上 |
| C1-v0 | PASS | — | 2.7 s |  |
| C1-v0-any | FAIL | 8 | 2.8 s | F3：`current_phase` 变成 2 |
| R1-v0 | FAIL | — | 2.6 s | `delta_time=0` 时除零 |
| P1-v0 | FAIL | 1 | 2.4 s | `delta_time<=0` 时一步不推进时间，episode 永远不结束 |
| V0-cover-v0 | COVERED | — | 3.2 s | 3 个 cover 都可达，说明 assume 没有把关键行为排除掉 |

反例步数不保证最短，求解器每次可能给出不同的反例（C1-v0-any 我跑过两次，一次 4 步、一次 8 步）。要最短的，就用 `--harness ... --set K=<更小>` 往下调，直到变成 PASS。

S1 还有第二部分：网文件里的四个信号串本身不能让互为冲突的两条 link 同时是 `G`。这是网文件的事实，不用 ESBMC，跑一次脚本就行：

```bash
python verification/esbmc/scripts/check_phase_strings.py
# 预期最后一行：S1 part 2: PASS
# phase 0 有 6 对、phase 1 有 2 对 G/g：都是要让行的左转（g = permissive green），SUMO 里是允许的
```

- [ ] **E6.3 读懂一个反例**

```bash
python verification/esbmc/scripts/ce_to_actions.py verification/esbmc/results/raw/G2-v0.txt
# {"actions": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0], "params": {}}
```

第 2 步请求切换，但 `phase_duration` 只有 5，小于 `min_green`，被拒绝。之后一直保持，到第 11 步时 NS 绿已经亮了 10 秒 warmup + 55 秒 = 65 秒。

- [ ] **E6.4 把反例放回真 SUMO**

```bash
python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/T1-v0-y0.txt --yellow-time 0
python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/T2-v0-any.txt
python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/C1-v0-any.txt
python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/L1-v0.txt
python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/G2-v0.txt
```

脚本会从反例文件里读出它违反的是哪条性质，只在那条性质真的失败时才报 REPRODUCED。

| 反例 | SUMO 里的结果 |
| --- | --- |
| T1-v0-y0 | `T1 REPRODUCED`，t=25 s |
| T2-v0-any | `T2 REPRODUCED`，t=100 s |
| C1-v0-any | `C1 REPRODUCED`，第 8 步 `current_phase=2` |
| L1-v0 | `L1 REPRODUCED`，t=91 s |
| G2-v0 | `G2 NOT reproduced`：前 42 秒 SUMO 的静态程序自己把灯切了，反而保住了 G2。这就是 E7 要做环境细化的原因 |

R1 和 P1 是配置问题，反例里没有动作序列可以回放，由 E8 的参数校验解决。

- [ ] **E6.5 提交并打 tag**

```bash
git add verification/esbmc/results
git commit -m "esbmc: v0 results for S1-P1 with SUMO replays"
git push
# PR 合并后，在 verification 上打 status review 的 tag
git switch verification && git pull && git tag v0-findings && git push origin v0-findings
```

## E7 环境细化：加入 SUMO 静态程序（L1）

替身换成 L1 之后，ESBMC 找到 F2 的 3 个反例，并把 G2 的假反例换成一个 13 步的真反例；4 个反例全部在 SUMO 里复现。这一节就是报告里 environment modeling 那一段的材料。

- [ ] **E7.1 在 L1 下跑 4 项**

```bash
python verification/esbmc/scripts/run_esbmc.py C1-v0-L1 G1-v0-L1 T2-v0-L1 G2-v0-L1
```

| ID | 结果 | 反例步数 | 反例在说什么 |
| --- | --- | --- | --- |
| C1-v0-L1 | FAIL | 7 | 一直保持 0；第 7 步时 SUMO 已经是黄灯，控制器以为还是 NS 绿 |
| G1-v0-L1 | FAIL | 9 | 静态程序给出的 EW 绿只亮了 4 秒，就被控制器的“切换”切掉 |
| T2-v0-L1 | FAIL | 10 | 黄灯之后又是 EW 绿，和黄灯前是同一方向 |
| G2-v0-L1 | FAIL | 13 | 控制器自己的 `phase_duration` 涨到 65 |

- [ ] **E7.2 回放到 SUMO**

```bash
for id in C1-v0-L1 G1-v0-L1 T2-v0-L1 G2-v0-L1; do
  python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/$id.txt 2>&1 | tail -1
done
```

预期四行都是 `... REPRODUCED in SUMO`。

- [ ] **E7.3 把这件事讲清楚（写报告时用）**

1. L0 替身假设“灯只显示控制器设置的状态”。在这个假设下，ESBMC 给出的 G2 反例在 SUMO 里不成立。
2. 一致性测试（E5.3）显示第 43 秒起 L0 和 SUMO 分叉，原因是 `reset()` 从不调用 `_set_phase()`，SUMO 的静态 tlLogic 一直在跑。
3. 把静态程序加进替身（L1）后，一致性测试 0 分叉；ESBMC 找到了 F2 本身的反例，而且 G2 的新反例在 SUMO 里成立。

这就是课件 F-Soft 那页说的 counterexample-guided environment refinement：假反例来自环境模型，并且只有把反例放回真实系统才发现得了。

- [ ] **E7.4 提交**

```bash
git add verification/esbmc/results
git commit -m "esbmc: L1 stub results for F2 (static program) with SUMO replays"
git push
```

## E8 v1 修复、参数化验证、无界证明

v1 的四处修复让全部 9 条性质在 L1 替身下通过；v0 的反例在打了补丁的 SUMO 环境里一个都复现不了。参数化 harness 把“显然的”修法打回来，手写的归纳 harness 对任意步数证明 G2 和 C1。

### E8.1 四处修复

| 编号 | 改什么 | 解决 |
| --- | --- | --- |
| FIX-1 | `_apply_action` 里加 look-ahead：`phase_duration + delta_time > max_green` 时强制切到另一相位 | F1 |
| FIX-2 | 动作不是 0 或 1 就 `raise ValueError` | F3 |
| FIX-3 | 构造函数校验：`delta_time>=1`、`yellow_time>=3`、`0<=min_green<=max_green`、`delta_time<=max_green`（11/6 按 Codex 审查加上），并且首个绿灯和之后的绿灯在 `[min_green, max_green]` 里都有可切换的时刻 | F4、F5、R1、P1 |
| FIX-4 | `reset()` 在 warmup 前调用 `_set_phase(0)`，并把 warmup 的 10 秒计入 `phase_duration` | F2 |

FIX-4 的后半句不能省：只接管灯、不计 warmup，第一个绿灯实际会亮 70 秒。这个问题只有 stub 里“司机看到的绿灯时长”版 G2 抓得到。

- [ ] **E8.2 把修复打进 `src/`（按 D1；选 (b) 就跳过这一步）**

```bash
git switch verification && git pull && git switch -c src/v1-fixes
git apply verification/esbmc/model/v1_fix.patch     # 只改 src/environment.py，约 50 行
git diff --stat                                       # 预期：1 file changed
python verification/esbmc/scripts/conformance_test.py --model v1 --level L1 --runs 30 2>&1 | tail -1
# 预期：v1/L1: 0 of 30 runs diverge from SUMO
git commit -am "src: enforce max_green with look-ahead, validate actions and parameters, take control at reset"
git push -u origin src/v1-fixes                      # PR 描述里 @ 队友，提醒他同步 Promela v1
```

- [ ] **E8.3 跑 v1 的 9 项（L1 替身）**

```bash
python verification/esbmc/scripts/run_esbmc.py S1-v1 T1-v1 T2-v1 G1-v1 G2-v1 L1-v1 C1-v1 R1-v1 P1-v1
```

预期全部 PASS。我这边的耗时是 3–36 秒，最慢的是 L1-v1。

- [ ] **E8.4 F5 实验：参数也交给 ESBMC**

```bash
python verification/esbmc/scripts/run_esbmc.py G2param-v1naive G2param-v1
python verification/esbmc/scripts/ce_to_actions.py verification/esbmc/results/raw/G2param-v1naive.txt
```

`h_G2_param` 让 `delta_time∈[1,20]`、`min_green∈[0,12]`、`max_green∈[5,16]` 都是 nondet（11/6 放宽，原来是 \[1,7\] 和 \[11,16\]）。预期：

- `G2param-v1naive` FAIL。具体参数每次可能不同，我两次分别得到 `d=7, mn=3, mx=12`（1 步）和 `d=7, mn=0, mx=15`（7 步），共同点是 max\_green 不是 delta\_time 的倍数。以第一个为例：第一个绿灯从 10 秒开始，naive 判断 `10 >= 12` 不成立，下一步就是 17 秒。
- `G2param-v1` PASS（我这边 34 秒；放宽范围前是 21 秒）。

naive 版本在默认参数 5/60 下是对的（60 是 5 的倍数），所以只用固定常数的模型会接受它。这是 ESBMC 这半边最有说服力的结果。

反过来也要写进报告：PR #1 的 Codex 自动审查指出，原来的 v1 没有拒绝 `delta_time > max_green`。例如 `delta_time=20, min_green=0, max_green=10`：第一步就切换，切完再跑 20 秒，G2 违反。旧的 harness 抽不到这个组合，因为 `delta_time` 只到 7、`max_green` 至少 11。把范围放宽后，旧 v1 在 7 秒内 FAIL（反例 `d=17, mn=0, mx=16`，1 步）；加上 `delta_time <= max_green` 的检查后 PASS。教训：参数化验证只对你选的参数范围成立。

- [ ] **E8.5 无界证明：手写一步归纳**

```bash
python verification/esbmc/scripts/run_esbmc.py G2ind-v0 G2ind-v1
```

`h_G2_ind` 检查两件事：① `reset()` 之后不变式 Inv 成立；② 从任意满足 Inv 的状态走一步，Inv 仍成立。Inv 是：`0 <= phase_duration <= max_green`，`current_phase` 是 0 或 1，灯显示的是这个相位的绿灯且已经是 online。两条都成立，就证明了任意步数下 G2 和 C1 都成立。

预期：`G2ind-v1` PASS（约 3 秒）；`G2ind-v0` FAIL 在 base case，因为 v0 reset 后灯还不归控制器管（F2）。不用 ESBMC 自带的 `--k-induction`：它在这里会关掉 inductive step（见 E3.3）。

- [ ] **E8.6 v0 的反例在 v1 上不再成立**

在打了补丁的分支上，把 E6/E7 的反例再回放一次：

```bash
for id in G2-v0-L1 L1-v0 C1-v0-L1 T2-v0-L1 C1-v0-any; do
  python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/$id.txt 2>&1 | tail -1
done
```

预期五行都是 `NOT reproduced`。最后一行是 `C1 NOT reproduced in SUMO (other violations: ValueError)`：v1 在第一个越界动作 -1 处抛出 `ValueError: action must be 0 or 1`。另外，`--yellow-time 0` 在构造时就会报 `ValueError: yellow_time must be >= 3`。这六条我在打了补丁的副本上重跑过，输出就是这样。

- [ ] **E8.7 提交并打 tag**

```bash
git add verification/esbmc/results
git commit -m "esbmc: v1 results, parametric G2 (F5) and inductive proof of G2/C1"
git push
# 合并到 verification 后
git switch verification && git pull && git tag v1-verified && git push origin v1-verified
```

## E9–E10 对照组：静态分析、Hypothesis、LLM 工具

静态分析在 `environment.py` 上报了 14 个 mypy 错误和若干 pylint 警告，但 F1–F5 一个都没找到。Hypothesis 用 200 个样例时，只在 10 个种子里的 1 个找到 G2。ESBMC 每次都能找到，并且能证明 v1 已经没有这个问题。

### E9 静态分析（课件要求的 simple static analysis tool）

- [ ] **E9.1 跑 mypy 和 pylint**

```bash
mkdir -p verification/esbmc/results/static
python -m mypy src/environment.py --ignore-missing-imports > verification/esbmc/results/static/mypy.txt
python -m mypy src/environment.py --ignore-missing-imports --strict > verification/esbmc/results/static/mypy_strict.txt
python -m pylint src/environment.py --disable=C0301,C0103 > verification/esbmc/results/static/pylint.txt
tail -1 verification/esbmc/results/static/*.txt
```

在 v0（`main` 分支）上的预期：mypy 默认 14 个错误，`--strict` 28 个；pylint 9.48/10。

- [ ] **E9.2 把告警分类**（填这张表，它就是报告里 static analysis 那一行的数据）

| 告警 | 行 | 类别 | 说明 |
| --- | --- | --- | --- |
| mypy `"None" has no attribute "copy"` | 410 | 误报 | `_get_instant_features()` 总是先把 `prev_queue_counts` 赋值 |
| mypy `reset` 与 `gymnasium.Env.reset` 签名不兼容 | 570 | 真问题，低危 | API 不一致，不影响控制逻辑 |
| mypy implicit Optional（`seed: int = None` 等） | 570 | 风格 | 类型标注写法 |
| mypy `int` 赋给 `None` 类型 | 667 | 风格 | `last_action` 初值是 None |
| pylint W0612 未用变量 `departed` | 699 | 真问题，低危 | 取了不用 |
| pylint W0201 属性定义在 `__init__` 外 | — | 真问题，低危 | `phase_states` 只在 `reset()` 里定义，先 `step()` 会报 AttributeError |
| F1–F5 | — | 漏报 | 静态分析不检查功能正确性（课件 static analysis tools 那页的弱点） |

### 随机测试对照：Hypothesis（FV vs testing）

- [ ] **E9.3 跑同一组性质的 PBT**

```bash
pytest -q verification/esbmc/baselines/test_hypothesis.py                 # v0：部分失败，每次不一样
MODEL=v1 pytest -q verification/esbmc/baselines/test_hypothesis.py        # 预期 5 passed
MODEL=v1naive pytest -q verification/esbmc/baselines/test_hypothesis.py   # 预期 test_G2_parametric 失败
python verification/esbmc/baselines/hypothesis_stats.py --seeds 10 --max-examples 200
```

最后一条在 v0 上跑 10 个种子，统计每个 bug 被找到的次数，写到 `results/hypothesis_stats.csv`。我这边的结果：

| 测试 | 10 个种子里找到 bug 的次数 |
| --- | --- |
| G2（一直保持） | 1 |
| L1（方向饿死） | 1 |
| T2（静态程序） | 4 |
| C1（越界动作） | 10 |
| G2 参数化 | 10 |

G2 需要连续约 11 步不请求切换，随机生成很难碰到；参数化和越界动作的 bug 很浅，每次都能找到。这张表直接放进报告的 FV vs testing 部分。

### E10 LLM 工具（TA 11/9 要求）

TA 对 proposal 的回复：“Lets add one more non-verification tool and some LLM tool use as well.”非验证工具由 E9 覆盖：mypy/pylint 静态分析和 Hypothesis property-based testing。LLM 分三部分：LLM-1 让 LLM 找 bug，填对比表的 LLM 列；LLM-2 让 LLM 修 bug，用 ESBMC 复验；LLM-3 记录项目里已经用到的 LLM。分工按 D2：LLM-1、LLM-2 和 LLM-3 的 ESBMC 部分归 Edward，LLM-3 的 SPIN 部分归队友。

防泄漏规则，LLM-1 和 LLM-2 都适用：

- 被测 LLM 只能看到下面列出的输入，不能接触 repo、CLAUDE.md、本 doc 或任何结果。repo 是公开的，所以要关掉联网搜索。
- 不用 VS Code 里的 Claude Code（CLAUDE.md 里写着 F1–F5），也不用开着 memory 的 claude.ai 普通对话；用无痕对话、关掉 memory 的 ChatGPT 新会话，或 API。
- 每个回答原样存档，并记下日期、模型名和版本。

#### E10.1 LLM-1：让 LLM 找 bug

- [ ] **E10.1a 准备输入（交给 Claude Code）**

在 `verification/esbmc/baselines/llm/find/` 下放两个文件：`input_environment.py`，即 `git show main:src/environment.py` 的原样输出；`input_properties.md`，即 `properties.md` 里 10 条性质的英文描述，去掉 ESBMC、SPIN、v0、v1 这几列，因为 v0 那一列就是答案。

- [ ] **E10.1b 跑 LLM（你手动）**

2–3 个模型（例如 Claude、GPT、Gemini），每个开 3 个新会话，每次贴同一段 prompt 加两个输入文件，回答存成 `find/<model>-run<N>.md`。

```text
Below is the environment class of a reinforcement-learning traffic-signal controller that runs
in the SUMO simulator (environment.py), and the properties it should satisfy (properties.md).
Treat the RL agent as arbitrary: at every decision step it may choose any action.
Default parameters: delta_time=5, yellow_time=3, min_green=10, max_green=60.
For each property, decide whether it can be violated. If it can, give a concrete witness:
the constructor parameters, the action sequence, and the simulated second at which the
violation appears. If it cannot, explain why in one or two sentences.
Answer by reading the code; do not run it.
```

- [ ] **E10.1c 核对每条声称（交给 Claude Code）**

把每个回答里的反例抽成 `find/claims.csv`（模型、第几次、性质、参数、动作序列、声称的时间）。动作序列用 `replay_in_sumo.py` 在真 SUMO 里回放；只涉及参数的（例如 `delta_time=0`）直接在 CPython 里构造 `SumoTrafficEnv` 检查。复现了才算找到，再对应到 F1–F4 和 R1/P1。F5 是修复方法上的问题，v0 上不存在，留给 LLM-2。

| 缺陷 | 模型 A（3 次里找到几次） | 模型 B | Hypothesis（10 个种子） | ESBMC |
| --- | --- | --- | --- | --- |
| F1 max\_green 不生效 |  |  | G2 1/10，L1 1/10 | 找到 |
| F2 静态程序 |  |  | 4/10 | 找到（L1 替身） |
| F3 越界动作 |  |  | 10/10 | 找到 |
| F4 yellow\_time=0 |  |  | 没测 | 找到 |
| R1/P1 参数非法 |  |  | 没测 | 找到 |
| 误报（声称了但复现不了） |  |  | — | 3 个：L0 下 2 个，靠回放识别；Homebrew 前端 bug 1 个 |

#### E10.2 LLM-2：让 LLM 修 bug，ESBMC 当裁判

这就是课件 Agentic Synthesis Loop 那页的第 4 步。每一轮存到 `verification/esbmc/baselines/llm/repair/round<N>/`。

- [ ] **E10.2a 第 1 轮：只给固定参数的反例（你手动）**

把 `env_core_v0.py`、`h_G2.py`、`results/raw/G2-v0.txt` 里的 Violated property 一段和 `ce_to_actions.py` 的输出发给 LLM。防泄漏规则同上，也不要提示 look-ahead。

```text
You are given a traffic-signal controller (env_core_v0.py), a verification harness (h_G2.py),
and a counterexample from the ESBMC bounded model checker showing that property G2
("no green phase lasts longer than max_green seconds") is violated.
Propose the smallest change to env_core_v0.py that makes G2 hold. Return the full modified
file and a two-sentence explanation. Do not change the harness.
```

回答存成 `verification/esbmc/model/env_core_llm1.py`，再让 Claude Code 用 `h_G2`（L1 替身，K=16）和 `h_G2_param` 复验。`run_esbmc.py` 现在只认 v0/v1/v1naive，要先加一个指定模型文件的选项。

- [ ] **E10.2b 后续轮：把参数化反例交回去**

`h_G2_param` FAIL 时，把参数化反例（`d`/`mn`/`mx` 和动作序列）发回同一个会话，要求在所有合法参数下都成立，存成 `env_core_llm2.py`，重复，最多 5 轮。

- [ ] **E10.2c 回归和记录**

最终版本跑 S1、T1、T2、G1、G2、L1、C1（L1 替身），记录：

| 指标 | 记录什么 |
| --- | --- |
| 轮数 | 到 `h_G2_param` PASS 用了几轮 |
| 第一版是不是 naive | 第 1 轮是否用了 `phase_duration >= max_green`，也就是 F5 的写法 |
| 回归 | 最终版本有没有打挂别的性质 |
| 代码变化 | `diff` 行数 |

#### E10.3 LLM-3：记录项目里已经用到的 LLM

| 工具 | 做了什么 | 人做的核对 | 证据 |
| --- | --- | --- | --- |
| Claude（claude.ai 对话） | 写计划，抽取模型，写 harness、stub 和脚本的初版 | 每个结论都在 SUMO 回放或 CPython 里复核；一致性测试检查模型和 SUMO 是否一致 | 本 doc；PR #1 |
| Claude Code（VS Code） | 在 M4 上执行 E1–E12.1 并开 PR；从反例里不可能出现的数值发现 Homebrew ESBMC 的 try bug | Edward 看每个 PR，Codex 自动审查 | PR #3–#11 |
| OpenAI Codex（PR 自动审查） | 审 PR #1 时指出 v1 没有拒绝 `delta_time > max_green`，而我们的参数化 harness 因为范围太窄没抓到 | 放宽范围后 ESBMC 在 7 s 内复现，加上检查后 PASS | PR #1 的审查评论；PR #2 |
| OpenAI Codex（队友） | 写 Promela 模型和 SPIN 脚本 | `check_traces.py` 对照 Python 参考模型 | 队友补：哪些部分是生成的、手改了几处、对照时抓到几次模型错误 |

完成标准：表填完，报告第 3 节加一段 LLM-assisted workflow。

- [ ] **E10.4 提交**

```bash
git add verification/esbmc/baselines/llm verification/esbmc/model/env_core_llm*.py verification/esbmc/results
git commit -m "esbmc: LLM bug finding (LLM-1) and repair loop (LLM-2), E10"
git push
```

## E11–E12 实验数据、报告与 slides

E11 产出对比表里 performance 那一行的数据；E12 把全部结果写进报告的 ESBMC 章节和 slides。英文草稿已经在「报告与展示」tab，里面的 \[TODO\] 用你在 M4 上的实测数填。

### E11 规模实验

- [ ] **E11.1 bound K 的影响**

```bash
pip install matplotlib                                              # 只有画图用得到
python verification/esbmc/scripts/scaling_sweep.py --exp K          # G2-v1、L1-v1、G2-v0-L1，K=4…24
python verification/esbmc/scripts/scaling_sweep.py --plot           # → results/fig_scaling_K.png（报告用的图）
```

结果写进 `results/scaling.csv`，不混进 `results.csv`。我这边整轮约 12 分钟，其中 L1-v1 在 K=24 一项就要 315 秒；先想看个大概就加 `--ks 4 8 12 16`。

&#91;embedded content: results/scaling.csv · E11.1 实测，K = 4…24，每点一次 run\]

G2 每多 4 步大约多 5 秒；L1 要同时跟踪两个方向的等待计数，K 从 16 到 24 时间涨了 7 倍。内存始终在 330 MB 以内。同一轮里的 G2-v0-L1 在 K=4、8、12 都是 PASS，K=16 起才 FAIL，因为反例要 13 步。bound 小于反例长度时，BMC 给出的 PASS 什么也不证明，这是报告 limitations 那一段要写的。

- [ ] **E11.2 参数范围的影响**

```bash
python verification/esbmc/scripts/scaling_sweep.py --exp param      # max_green 的上限 16 / 20 / 24
```

| max\_green 范围 | K | naive 修复 | look-ahead 修复（v1） |
| --- | --- | --- | --- |
| 11…16 | 20 | FAIL，3.4 s | PASS，21.6 s |
| 11…20 | 24 | FAIL，4.2 s | PASS，34.8 s |
| 11…24 | 28 | FAIL，4.1 s | PASS，64.7 s |

delta\_time ∈ \[1,7\]、min\_green ∈ \[0,12\] 不变。找反例的时间几乎不随范围增长；要证明没有反例，时间大约每扩大 4 翻一倍。这张表是 11/6 放宽 `h_G2_param` 之前测的；现在 `D_HI` 默认是 20，重跑 `--exp param` 会更慢，以你的实测为准。

- [ ] **E11.3 求解器对比（只在 Mac 上做）**

```bash
python verification/esbmc/scripts/scaling_sweep.py --exp solver     # 自动测出这个 esbmc 带了哪些求解器
```

brew 装的 ESBMC 带 Z3 和 Bitwuzla（E2.1），脚本在 K=16 下对 G2-v1、L1-v1 各跑一遍。我这边的版本只编进了 Z3，所以这一项没有参考数，以你的结果为准。

- [ ] **E11.4 提交**

```bash
git add verification/esbmc/results/scaling.csv verification/esbmc/results/fig_scaling_K.png verification/esbmc/results/raw
git commit -m "esbmc: scaling experiments (bound, parameter range, solver)"
git push
```

### E12 结果汇总、报告与 slides

- [ ] **E12.1 生成结果总表**

```bash
python verification/esbmc/scripts/results_table.py > verification/esbmc/results/results_table.md
```

同一个 ID 跑过多次时取最后一次，ad-hoc run 不进表。预期 31 行，最后一列全是 `ok`。

- [ ] **E12.2 报告里的图和表**

| 图表 | 来源 |
| --- | --- |
| 验证闭环图 | 本 tab 顶部的示意图 |
| v0/v1 结果总表 | `results_table.md` |
| 反例在 SUMO 里的复现表 | E6.4、E7.2、E8.6 的输出 |
| 时间随 K 的变化 | `fig_scaling_K.png` |
| Hypothesis 检出率 | `results/hypothesis_stats.csv` |

- [ ] **E12.3 写 ESBMC 章节**：在「报告与展示」tab 的英文草稿上改，把 \[TODO\] 换成 M4 的实测数。
- [ ] **E12.4 做自己那几页 slides**：按同一 tab 的 presentation 大纲。
- [ ] **E12.5 最后一次 PR 和 tag**

```bash
git switch verification && git pull
git tag final && git push origin final       # 12/23 前，两人都合并完之后
```

## E13 清理：项目结束后释放 Mac 的磁盘空间

这里清理的是磁盘空间。ESBMC 和 SUMO 只在运行时占内存（RAM），进程结束就释放；如果有卡住的进程，用 `pkill -f esbmc` 或 `pkill -f sumo`。顺序不要反：先确认所有东西都在 GitHub 上，再删。队友的 SPIN 清理写在 SPIN tab。

- [ ] **E13.1 确认全部推送、提交材料已另存**

```bash
cd ~/projects/traffic_rl_project
git status --short                                     # 预期：没有输出
git fetch origin
git log --oneline origin/verification..verification     # 预期：没有输出（没有未推送的提交）
git branch -vv | grep -E "ahead|gone"                  # 预期：没有输出
git push origin --tags                                 # v0-findings、v1-verified 等 tag 也推上去
```

报告 PDF、slides 和提交用的 zip 另存一份到 `~/Documents` 或网盘。完成标准：上面 4 条命令都没有意外输出。

- [ ] **E13.2 先量一下占用**（把输出贴到「总览」的日志，用来和 E13.7 对比）

```bash
df -h ~ | tail -1                                       # 记下 Avail
du -sh .venv verification/esbmc/build .hypothesis 2>/dev/null
du -sh "$(brew --cellar)"/* 2>/dev/null | sort -h | tail -12   # Homebrew 里最大的 12 个包
brew deps esbmc                                         # esbmc 带进来的依赖
du -sh "$(brew --cache)" ~/Library/Caches/pip 2>/dev/null
```

- [ ] **E13.3 删 repo 里的生成物**（venv 里有 SUMO，是大头）

```bash
cd ~/projects/traffic_rl_project
deactivate 2>/dev/null
rm -rf .venv verification/esbmc/build .hypothesis .pytest_cache .mypy_cache
find . -name __pycache__ -type d -prune -exec rm -rf {} +
rm -rf /tmp/esbmc-hello                                 # E2.2 的 hello test
```

- [ ] **E13.4 卸载 ESBMC 和它的依赖**

```bash
brew uninstall esbmc
brew autoremove --dry-run     # 先看会删哪些（llvm、boost、bitwuzla、z3 等）
brew autoremove               # 只删“作为依赖装进来、现在没人用”的包；你主动 brew install 的不会动
brew cleanup --prune=all      # 删下载缓存和旧版本
which esbmc                   # 预期：esbmc not found
```

- [ ] **E13.5 只在用过 E2.3 后备方案时做**

| 用过的方案 | 要删的东西 |
| --- | --- |
| B release 包 | 解压目录和 `esbmc-macos.zip`；`~/.zshrc` 里加过的 `export PATH=...` 那一行 |
| C 源码编译 | `rm -rf ~/tools/esbmc-src`（含构建产物）；用 `brew leaves` 找出编译时主动装的包，确认别的项目不用再 `brew uninstall` |
| D OrbStack | `orb list` 查看建过的 Linux 机器，`orb delete <名字>`；然后 `brew uninstall --zap --cask orbstack`（`--zap` 连应用数据一起删） |

- [ ] **E13.6 可选：Claude Code 插件、Python、gh、整个 repo**

如果做过 E1.5，在 Claude Code 里输入：

```text
/plugin uninstall esbmc-plugin@esbmc-marketplace
/plugin marketplace remove esbmc-marketplace
```

其余的只在别的项目不用时删：

```bash
rm -rf ~/Library/Caches/pip               # pip 下载缓存
gh auth logout
brew uninstall gh python@3.12             # 如果还被别的包依赖，brew 会拒绝并告诉你是哪个
brew autoremove && brew cleanup --prune=all
rm -rf ~/projects/traffic_rl_project      # 只在 E13.1 全部通过后；以后要用再 git clone
```

Xcode Command Line Tools 和 Homebrew 本身建议保留：别的开发工具也靠它们，删掉后 git 也会一起没有。

- [ ] **E13.7 再量一次**

```bash
df -h ~ | tail -1                                         # 和 E13.2 的 Avail 相比，差值就是释放的空间
brew list --formula | grep -iE "esbmc|bitwuzla|z3|boost|llvm"   # 预期：没有输出，除非别的项目在用
```

完成标准：`which esbmc` 找不到，Avail 比 E13.2 多出的空间记在日志里。
