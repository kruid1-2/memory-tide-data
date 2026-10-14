# MEMORY TIDE — GitHub Actions 实时采集

基于已有历史数据工程新增的离线运行采集器：配置为每 15 分钟请求一次微博官方桌面热搜，保存真实响应、规范化快照、相邻观测端点变化及运行状态。本功能不修改前端，也不上传/重建历史 SQLite 数据库。

## 当前状态

已部署到公开仓库 [kruid1-2/memory-tide-data](https://github.com/kruid1-2/memory-tide-data)。截至 2026-10-14 12:34（北京时间），[首次手动执行](https://github.com/kruid1-2/memory-tide-data/actions/runs/38346457723)和 **四次真实 schedule 执行**均通过成功步骤、远程原始响应 SHA256、重新解析快照及永久保存核验。最后成功采集为 **2026-10-14T10:12:26+08:00**；工作流 active、WEIBO_SCHEDULE_ENABLED=true，15 分钟 cron 配置保持开启。有限四次核验任务交付后暂停。

**实际采样严重稀疏：四次之间约 5小时57分、3小时26分、2小时26分，不是连续 15 分钟记录。** 自动触发和保存链路已实证可用，但调度稳定性尚未达标，不能承诺持续每15分钟取得数据。不得补写未发生的采集。完整运行链接、采样条数、来源、SHA256 与诊断见 [LIVE_TEST_REPORT.md](LIVE_TEST_REPORT.md)。

直接查看 [Actions](https://github.com/kruid1-2/memory-tide-data/actions/workflows/collect-weibo.yml)、[最新状态](https://github.com/kruid1-2/memory-tide-data/blob/data/observations/status.json)及[历史快照](https://github.com/kruid1-2/memory-tide-data/tree/data/observations/snapshots)。

## 文件与来源

- `.github/workflows/collect-weibo.yml`：工作流，每小时第 8/23/38/53 分钟（UTC；北京时间分钟相同）触发，间隔 15 分钟，并支持 workflow_dispatch。
- `memory-tide-data/memory_tide/live.py`：请求、解析、追加保存、去重、状态恢复、端点变化及读取校验。
- `memory-tide-data/deployment/restore_data.sh` / `persist_data.sh`：恢复/提交持久化 data 分支；不强制推送。
- `memory-tide-data/deployment/run_summary.py`：Actions 运行摘要和数据查看链接。
- `memory-tide-data/deployment/verify_cloud.py`：只读核对真实 GitHub 触发事件、成功步骤及远程原始数据，不把手动或 skipped 运行计入四次 schedule。
- `memory-tide-data/tests/test_live_collection.py` / `test_workflow_persistence.py`：临时数据算法测试和临时 bare Git 持久化测试。

复用现有 `core.clean_title/topic_id/time_iso/finite_number`，历史导入、数据库和分析程序没有被改写。直接来源 `https://weibo.com/ajax/side/hotSearch`，标识 `weibo/official-desktop-hotsearch-v1`；它与 `bhwa233/weibo-trending-hot-history` 的移动端历史指数分开。不得用两个来源的数值相减。移动接口和桌面网页在本次检查返回访客验证 HTML，因此不作为回退数据来源；官方桌面 JSON 已取得真实数据。

采集无需微博 Cookie 或账号，若官方接口将来需要登录/访问受限，按失败记录处理，不能用旧榜单或其他来源冒充最新快照。原始响应中可能含广告数据；全部响应保留，广告单独标记并排除增长排行。

## 先手动测试，再启用计划

上传工作流、模块、部署脚本与测试到仓库默认分支。最小发布清单见 `deployment/prepare_release.py`；它不含前端、大型数据库、历史压缩包或本地探测数据。

工作流使用默认 `GITHUB_TOKEN` 和 `contents: write`，不用 PAT。代码检出关闭凭据落盘；数据分支 Git 凭据只从运行时环境提供，JSON 和日志不保存令牌。不需要修改账户付费设置。

```sh
gh workflow run collect-weibo.yml --repo OWNER/REPO --ref main
gh run list --repo OWNER/REPO --workflow collect-weibo.yml --event workflow_dispatch
gh run view RUN_ID --repo OWNER/REPO --log

# 确认手动运行、data 分支快照和真实数值读取成功后才执行。
gh variable set WEIBO_SCHEDULE_ENABLED --body true --repo OWNER/REPO

# 暂停计划采集，手动执行仍可用。
gh variable set WEIBO_SCHEDULE_ENABLED --body false --repo OWNER/REPO
```

本仓库已启用该变量；不需要再次开启。active 状态与变量 true 只能确认配置，不能证明 GitHub 内部调度已投递。有限核验 heartbeat 曾每 10 分钟检查并逐次报告 N/4、最后成功采集时间及异常；已达到四次，交付后暂停该核验任务，保留 GitHub 采集开启。复核计划执行证据可以在 memory-tide-data 目录运行 `python3 deployment/verify_cloud.py --repo kruid1-2/memory-tide-data --manual-id 38346457723`，需要已登录的 gh CLI。结果保存到本地 live/cloud_verification.json。

`WEIBO_SCHEDULE_ENABLED` 初始未设置，所以 schedule 的采集 job 跳过；手动 job 正常运行。启用后观察至少四次 `event=schedule`、有采集 job 实际成功且 data 分支保存对应 run_id 的结果；skipped、失败和手动运行都不能计入四次成功验证。示例中的 main 需替换成仓库实际默认分支。

GitHub 计划任务可能延迟或漏跑，运行实际接收时间会写入快照；不回填没执行的时间桶。使用偏移分钟减少整点负载。工作流有全仓固定 concurrency group，正在运行的 job 不被取消；GitHub 同组通常仅保留一个 pending，繁忙时待执行任务也可能被替换，因此不能承诺严格每 15 分钟完整无缺失。参见 [GitHub 计划事件文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) 和 [并发控制文档](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)。

## 永久保存与读取

代码位于默认分支；数据位于独立 `data` 分支，不依赖临时 runner 文件系统，也不提交本地数据库。每次 runner 先恢复最新 data 分支，再采集并提交所有新增文件。`data` 分支是累积档案，不可删除或 force push 回滚。

```text
data 分支/
  observations/
    raw/YYYY-MM-DD/HHMMSS_RUN_ID.json         原始响应字节，不覆盖
    snapshots/YYYY-MM-DD/HHMMSS_RUN_ID.json   完整规范化快照，不覆盖
    trends/YYYY-MM-DD/HHMMSS_RUN_ID.json      当次端点变化，不覆盖
    index/RUN_ID.json                        该工作流运行的提交记录，不覆盖
    attempts/RUN_ID/ATTEMPT.json             成功/失败日志，不覆盖
    errors/RUN_ID/ATTEMPT.bin                失败响应字节，如有
    status.json                             最新尝试状态与最后成功时间
    latest.json                             最后成功快照路径与 SHA256
    latest_trends.json                      最后成功快照对应变化
```

原始 HTTP 响应 SHA256 与快照关联；所有不可变文件先写临时文件、同步、原子发布。重复同一 run_id 不重复请求或写第二份已提交快照。索引写完后指针更新被中断，重跑能从完整索引恢复；重跑旧任务不会回滚最新成功。历史读取以 `index/*.json` 的已提交记录为准，不将中断时未提交的孤立文件当成完整成功快照。

`latest` 和 `status` 是可更新指针，历史文件与失败日志永久追加。若采集失败，错误也提交 data 分支，最后成功更新时间不变，Actions 最后一步显示失败。默认在 `status.last_attempt_status` 和 `status.last_error` 查看失败，`last_success_at` 查看最后真实成功。

若 GitHub 写入失败：非快进推送最多尝试三次，无强制推送；rebase 冲突安全停止。当前新增数据备份到 `weibo-unsaved-RUN_ID-ATTEMPT` artifact，保留 **14 天**。该备份是临时救援，不等于 data 分支永久提交；应在期限前下载、校验、人工合入数据分支后恢复采集。运行摘要的 `Persistence step` 必须为 success 才可视为完成持久化。仓库写入权限/分支保护失败不能伪装成成功。

## 在 GitHub 查看是否成功

1. 打开仓库 **Actions → MEMORY TIDE - Collect Weibo**。看本次触发类型、完成结论、Collect genuine current data 和 Persist snapshots 的结果。
2. 打开单次运行的 **Summary**，核对 Last success (Beijing)、Persistence step，以及 status/latest/trends 链接。
3. 在 **Code** 的分支选择器切到 **data**，打开 `observations/status.json`；成功时 last_success_at 应随真实采集更新。
4. 打开 `observations/index/RUN_ID.json` 找到对应原始响应、快照和变化文件；snapshot.items 里直接读取题目、rank、heat、timestamp、source。
5. 观察四次计划执行时，以 Actions API 的 event=schedule 和对应 data 分支索引一起核对，不只看四个绿色图标。

## 热度与时间语义

快照含 `topic_id/title/rank/heat/timestamp/platform/source/url/quality`。身份沿用已有规范化完整标题 SHA256，不以相似文本合并事件；接收时间是北京时间、秒精度，不能当成微博服务器原始观测时刻。HTTP date/age/cache-control 按返回值保存，不能保证平台缓存绝无滞后。

排名采用 `realpos`；源 `rank` 是包含广告的零基展示序号，不能当正式榜单排名。真实数值 `num=0` 在此直接来源是可观测零，保留 0；缺失/非法数值为 null，和历史档案“上游解析歧义零”不同。固定置顶项无正式排名/热度，分别标记 null。

变化仅比较相同 source 的相邻成功观测；`elapsed_seconds` 用真实接收时间差，`heat_delta`、`heat_pct` 和 `heat_per_hour` 计算端点变化及按小时平均。中间失败或超过 30 分钟间隔标记 gap，不推断全程连续上升，不把热度未知或离榜当 0。排名辅助 `metric_basis=rank_only` 与 `observed_heat_endpoints` 分开，派生值溢出也留 null。

完整排名 1—50 的榜单才可确认缺席为 not_on_list；部分榜单中的缺席是 unknown_partial_snapshot。少于 40 个有效排名、重复排名、HTML/异常响应视为采集失败；不写伪造成功快照。

## 本地运行与验证

Python 3.9+，Linux/macOS，curl、Git；无额外 Python 包。先进入 memory-tide-data：

```sh
python3 -m memory_tide.live collect --root live/observations --run-id local-unique-id
python3 -m memory_tide.live verify --root live/observations
python3 -m unittest discover -s tests -v
bash -n deployment/restore_data.sh deployment/persist_data.sh
```

每次实际新增采集必须有不同 run-id；同一 ID 重跑只用于去重/恢复，不能被计为新的观测。不要将测试 fixture 放进真实数据分支。云上 job 只跑实时边界测试，不重新处理历史 SQLite。

## 故障排查与费用

| 现象 | 检查与处理 |
|---|---|
| 完全没有 event=schedule 运行 | 先核对默认分支中的 cron、workflow active、Actions enabled、仓库变量及全部运行事件；无运行说明尚未进入采集 job。2026-10-13 已执行重新启用和 cron 偏移更新，恢复是否有效必须等真实 schedule 证据，不能用手动运行充数 |
| schedule job skipped | 确认 workflow 在默认分支，变量 WEIBO_SCHEDULE_ENABLED=true |
| 非 JSON/HTTP 403/空榜单 | 读失败 attempt 和 error 原始响应；接口访问限制，保留旧最后成功，不用旧数据填充 |
| data 推送 403 | 检查 Actions 权限和 data 分支保护；不关闭安全规则或创建额外令牌来隐藏故障 |
| Non-fast-forward / rebase 冲突 | 下载 outbox artifact；校验新增原始快照，按时间恢复指针并人工合入，禁止 force push |
| 最后成功更新时间不变 | 同时看 last_attempt_status；任务可能失败、跳过或未被调度 |
| quota / billing 失败 | 看账户 Actions 使用额度和预算；本功能不修改付费设置 |

15 分钟约为每天 96 次任务。公共仓库标准 GitHub-hosted runner 免费；私有仓库消耗账户每月额度，Free 为 2,000 分钟、Pro 为 3,000 分钟，超额是否计费取决付费方式和预算。不能把私人项目自动改公开或未经确认启用额外付费。来源：[GitHub Actions 计费文档](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。

## Cloudflare 调度迁移（2026-10-14）

已新增独立 [memory-tide-scheduler](../memory-tide-scheduler/README.md) 代码、本地测试、共享15分钟窗口去重和8个连续窗口对账脚本。Cloudflare账号授权及Worker首次部署已完成，Secret重新验证后Worker真实探针38518846120已通过（2026-10-14T13:51:03+08:00，52话题/50排名，原始字节与持久化均核对）。Cloudflare分发已开启，固定北京时间14:00–16:00的连续8窗口验收与每10分钟核验已启动，尚未完成。原生schedule保留直至验收通过；现有解析、快照原子保存和data分支不重建。详见调度项目TEST_REPORT.md。
