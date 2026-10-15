# GitHub Actions 实时采集测试结果

核验日期：2026-10-14，北京时间。当前阶段：**首次云端手动运行及四次真实 schedule 执行均核验通过；快照永久保存；15 分钟 cron 配置仍开启，但实际调度存在数小时断档，不能视为连续 15 分钟数据。**

仓库：https://github.com/kruid1-2/memory-tide-data

## 已验证的云上手动执行

[运行 38346457723](https://github.com/kruid1-2/memory-tide-data/actions/runs/38346457723) 的 event=workflow_dispatch，结论 success。采集、原始响应核对和 GitHub 持久化步骤全部 success。

- 实际接收时间：**2026-10-13T12:26:48+08:00**。
- 53 条话题，50 个有效正式排名。
- 原始响应 SHA256：`2696e167bcac17c1390983eb379f5926d9c41eb8cb48dd25ded3b1327369c1c2`。
- 永久保存于 data 分支：`observations/snapshots/2026-10-13/122648_38346457723.json`、对应原始 raw 文件、trends、index 及 attempt。
- 已通过 GitHub API 读回原始响应与清洗快照，按真实响应重新解析，逐字段相同；不是只看绿色图标。
- 主分支初次公开仅 14 个最小文件，已逐文件复核不含密钥、Cookie、个人路径、历史数据库或前端。
- `WEIBO_SCHEDULE_ENABLED=true` 已读回确认；cron 原为每小时 7/22/37/52 分钟，2026-10-13 更新为 8/23/38/53 分钟（UTC），间隔 15 分钟。

当前 schedule 验证数 **4/4**（实际检查时刻 2026-10-14T12:34:03+08:00）。所有计入的运行均为 GitHub API 的真实 event=schedule，采集、原始响应验证和 GitHub 持久化步骤全部 success，已从 data 分支读回原始字节重新解析，逐字段核对清洗快照与 SHA256。手动、跳过、失败运行不计入四次。

## 四次真实计划执行证据

| 运行 | 实际采集时间（北京时间） | 话题数 | 正式排名数 |
|---|---|---:|---:|
| [38412872907](https://github.com/kruid1-2/memory-tide-data/actions/runs/38412872907) | 2026-10-13T22:23:13+08:00 | 52 | 50 |
| [38461983777](https://github.com/kruid1-2/memory-tide-data/actions/runs/38461983777) | 2026-10-14T04:20:12+08:00 | 52 | 50 |
| [38486215891](https://github.com/kruid1-2/memory-tide-data/actions/runs/38486215891) | 2026-10-14T07:46:08+08:00 | 51 | 50 |
| [38499791906](https://github.com/kruid1-2/memory-tide-data/actions/runs/38499791906) | 2026-10-14T10:12:26+08:00 | 52 | 50 |

来源均为 `weibo/official-desktop-hotsearch-v1`，直接请求 `https://weibo.com/ajax/side/hotSearch`，没有 Cookie 或模拟榜单。四次共 **207 条话题观测、200 个正式排名观测**；加上首次手动为 **5 份真实云端快照、260 条话题观测**。

最后成功时间 `last_success_at=2026-10-14T10:12:26+08:00`，最后尝试状态 success。检查时没有失败、跳过、排队或原始响应核验错误。工作流 state=active、仓库变量 WEIBO_SCHEDULE_ENABLED=true 已重新读回。

**质量限制：配置频率不等于实际频率。** 四次实际采样间隔为 5小时56分59秒、3小时25分56秒、2小时26分18秒，没有达到连续 15 分钟采样。GitHub 事件创建时间同样稀疏，故不能把这些断档解释成微博采集慢或 runner 运行耗时。此前重新启用/偏移 cron 后确实收到事件，但没有证据证明操作是恢复原因，内部注册/投递延迟根因仍未确认。缺失时间桶不回填、离榜或缺失不补零；趋势是带真实时间差与 gap 标记的端点比较。

data 分支永久保存路径及 SHA256：

- `snapshots/2026-10-13/222313_38412872907.json`；原始 `raw/2026-10-13/222313_38412872907.json`；SHA256 `3b9e7624b5d3a91a802217161e5e4c9f762d67309cf094f42798311db1d16cb9`。
- `snapshots/2026-10-14/042012_38461983777.json`；原始 `raw/2026-10-14/042012_38461983777.json`；SHA256 `8168ded789c7781f365f9e6c91a10b0890bc87c00dc2140edaacb13f7126cbfc`。
- `snapshots/2026-10-14/074608_38486215891.json`；原始 `raw/2026-10-14/074608_38486215891.json`；SHA256 `ea420ebab37f84c8908842fecca4ee7c207ffc0d29b7b4157239df4e96afc374`。
- `snapshots/2026-10-14/101226_38499791906.json`；原始 `raw/2026-10-14/101226_38499791906.json`；SHA256 `d4588a6416a729a50d668d8043a58112883c6fa4f45dedfe28d21372f9f7ff0a`。

以上路径均相对于 data 分支 `observations/`。`observations/status.json` 提供最新状态，`observations/index/RUN_ID.json` 提供来源和对应文件。有限 heartbeat 核验已达到目标；文档交付后暂停该任务，GitHub 定时采集保持开启。该核验结束不代表调度稳定性已通过。

## 2026-10-13 定时未触发诊断

截至 14:06:55（北京时间），Actions 全部运行列表只有手动运行 38346457723；没有 schedule 的 queued、skipped、failed 或 completed 记录。因此未发生采集步骤失败，也没有计划运行错误日志或新增 data 分支失败记录可以分析。

确认的配置：Public 仓库，未归档、未禁用；默认分支 main；工作流 REST id=382816879、state=active；Actions enabled=true、allowed_actions=all；仓库变量 WEIBO_SCHEDULE_ENABLED 的字面值为 true。默认分支确有合法 schedule 定义，actionlint 校验通过。提交作者和提交者均被 GitHub 识别为 kruid1-2；手动运行已证明云端请求和 contents:write 持久化正常。

仓库变量只在 schedule 事件产生后控制 job 是否跳过，不能解释完全没有 schedule 事件。工作流已被 GitHub 识别，但公开 REST API 的 active 状态不提供内部 cron 注册健康或下一次触发时间。故障目前定位到事件生成/投递环节，具体是内部注册、延迟或丢弃尚无证据确认。GitHub 官方允许计划任务延迟或漏跑，但不能据此把多次未触发直接判为正常。

已执行的恢复尝试：14:03 通过官方 REST 暂时 disable 再 enable，分别读回 disabled_manually 与 active；随后将 cron 从 7/22/37/52 偏移一分钟到 8/23/38/53，仍为每 15 分钟一次，提交默认分支更新。该操作不是已恢复的证明，需要实际 event=schedule 及原始响应核验才能确认。没有创建替代手动运行来冒充 schedule。

刷新前 data 分支提交为 `282c9bac203909e977f7bb84ac03222bbddeddac`。本次部署只更新工作流和文档，不写 data 分支、不重置已有快照，不修改前端或历史 SQLite。诊断原始 API 证据仅保留在本地 `live/schedule_diagnostics_20261013.json`，不上传整个工作目录。

来源：[GitHub schedule 事件文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)、[工作流 REST API](https://docs.github.com/en/rest/actions/workflows)。

## 已完成的检查

- 项目现有历史数据模块可复用；复用 `clean_title/topic_id/time_iso/finite_number`。没有重写历史导入/分析，没有修改两个前端目录。
- `gh api user` 联网确认账号 kruid1-2 有效。本地 Git main 无提交记录、无 remote，没有自动选择或修改现有其他仓库。
- 真实移动接口与桌面榜单网页返回 Sina Visitor System HTML；记录在 live/research。官方桌面 `ajax/side/hotSearch` 返回成功 JSON，选为独立实时来源，不混入历史移动来源。
- 32 项全量测试通过：14 项历史回归、16 项实时解析/变化/幂等/失败/中断恢复、2 项临时 bare Git 持久化测试。人工 fixture 仅在临时目录使用，未写入真实观测；同秒观测的旧运行及失败重播也不会回退最新指针。
- `bash -n` 两个部署脚本通过。
- 官方 actionlint 1.7.12 的发布压缩包已核对官方 SHA256，工作流语法与表达式校验通过；工具只放在临时目录，不安装到系统。
- GitHub 官方 checkout v6 与 upload-artifact v6 的提交 SHA 经 API 核实并固定。
- 独立代码审查复现成功/失败日志写入后中断、不可变文件半写入等恢复问题；已改成原子发布、按提交索引恢复指针、按 attempt 日志恢复失败状态，并加入回归测试。

## 两次真实本地采集

| 项目 | 第一次 | 第二次 |
|---|---|---|
| 接收时间 | 2026-10-13T12:00:47+08:00 | 2026-10-13T12:12:06+08:00 |
| run_id | local-real-20261013-first | local-real-20261013-second |
| 全量话题，包括广告/固定项 | 52 | 53 |
| 有效正式榜单排名 | 50 | 50 |
| 来源 | weibo/official-desktop-hotsearch-v1 | 同一来源 |
| 保存/原始响应核对 | 成功 | 成功，前次未覆盖 |

两次实际接收时间相差 **679 秒**。第二次产生 24 个观测热度上升话题、18 个观测热度下降话题；新增/缺失话题不补零。实际例：`AI视频已经以假乱真了` 的热度 236,177 → 897,552，增长 661,375；`肖战演唱会390到1960` 的热度 567,494 → 835,627，增长 268,133。以上只是观测端点变化，不解释原因，也不是定时调度试验。

原始结果：`live/local_collection_result.json`、`live/local_collection_second.json`、`live/local_verification.json`。原始字节、快照和趋势在 `live/observations/`，SHA256 位于快照/索引。两个索引及原始响应都已读取校验，`snapshots_verified=2`。

## 持久化及失败测试证据

临时 bare Git 仓库模拟两次全新 runner：第一次提交 data 分支；第二次重新恢复分支，追加新观察；旧原始字节不变，远程两个索引都存在；同 run-id 重跑不请求、不新增快照，也不产生新提交。

独立失败试验：HTML 响应不生成成功快照，错误和 last_attempt_status=failed 仍成功写入 data 分支，last_success_at 为 null 或原来的最后成功时间。竞争推送试验在冲突时安全退出，remote 不被强制覆盖，新增 outbox 保留。实际 GitHub 权限与网络条件已由上述首次云上手动运行验证；计划触发仍需独立验证。

工作流先将采集失败记录提交，再在最后步骤让 Actions 显示失败。若推送失败，新增文件 artifact 保留 14 天，需要人工恢复后才算永久保存；不会将 artifact 备份伪装成已提交数据库/分支。

## 云上测试进度

| 必须项 | 当前状态 |
|---|---|
| 确定目标 GitHub 仓库及可见性 | 已确认 kruid1-2/memory-tide-data，Public；创建前检查404 |
| 上传最小发布包到默认分支 | 已完成 |
| 手动 workflow_dispatch 一次 | 38346457723 success |
| 核对远程快照与原始响应 | 已通过 |
| 启用 WEIBO_SCHEDULE_ENABLED=true | 已启用并读回确认 |
| 至少四次 event=schedule 的实际成功并核对保存 | **4/4，真实运行、原始字节和永久保存全部核对；实际采样不连续** |

用户已明确授权公开仓库，目标选择阻塞已解除。公共仓库标准 runner 免费；未修改付费设置。先手动验证远程真实数据和持久化，再开启计划任务。

确定仓库后按 LIVE_README 执行手动验证，再开启 schedule。只统计真正的 schedule 事件及保存成功的 run_id，不把本地、手动、跳过或失败运行算作四次观察结果。没有任何模拟记录冒充远程结果。

## 2026-10-15 正式切换阶段

新固定11:00–13:00实验已完成真实8/8端到端核验，422话题观测/400排名、漏采0、触发失败0、实际间隔892–908秒；云端Cron和100%持久日志已在控制台读回。本次提交移除GitHub原生schedule，保留workflow_dispatch和固定并发锁。切换后4窗口尚待观察，完整迁移验收尚未结束。原10月14日日志缺证结论继续保留。
