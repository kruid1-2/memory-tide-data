# GitHub Actions 实时采集测试结果

日期：2026-10-13，北京时间。当前阶段：**本地实现与验证完成；用户已授权公开仓库 kruid1-2/memory-tide-data；仓库已创建，云上手动执行及四次计划执行尚未开始**。定时采集尚未启用。

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

独立失败试验：HTML 响应不生成成功快照，错误和 last_attempt_status=failed 仍成功写入 data 分支，last_success_at 为 null 或原来的最后成功时间。竞争推送试验在冲突时安全退出，remote 不被强制覆盖，新增 outbox 保留。实际 GitHub 权限与网络条件尚待云上手动运行验证，不能以本地 Git 测试代替。

工作流先将采集失败记录提交，再在最后步骤让 Actions 显示失败。若推送失败，新增文件 artifact 保留 14 天，需要人工恢复后才算永久保存；不会将 artifact 备份伪装成已提交数据库/分支。

## 尚未完成的云上测试

| 必须项 | 当前状态 |
|---|---|
| 确定目标 GitHub 仓库及可见性 | 已确认 kruid1-2/memory-tide-data，Public；创建前检查404 |
| 上传最小发布包到默认分支 | 未执行 |
| 手动 workflow_dispatch 一次 | 未执行 |
| 核对远程快照与原始响应 | 未执行 |
| 启用 WEIBO_SCHEDULE_ENABLED=true | 未执行 |
| 至少四次 event=schedule 的实际成功并核对保存 | **0/4，未开始** |

用户已明确授权公开仓库，目标选择阻塞已解除。公共仓库标准 runner 免费；未修改付费设置。先手动验证远程真实数据和持久化，再开启计划任务。

确定仓库后按 LIVE_README 执行手动验证，再开启 schedule。只统计真正的 schedule 事件及保存成功的 run_id，不把本地、手动、跳过或失败运行算作四次观察结果。没有任何模拟记录冒充远程结果。
