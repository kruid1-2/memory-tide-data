# MEMORY TIDE Cloudflare scheduler

> **当前状态：正式验收与切换完成（2026-10-15）。** 切换前8/8及切换后固定4/4均完整通过，漏采0、触发失败0。GitHub原生schedule已移除，workflow_dispatch和工作流保持启用；Cloudflare Cron每15分钟继续触发。最新额外验证采集：2026-10-15T19:30:58+08:00。详情见调度项目TEST_REPORT.md和FINAL_VERIFICATION.json。原缺证实验与后来补证分别保留。


独立的 Workers Cron 调度器。UTC `*/15 * * * *` 请求既有 GitHub Actions `workflow_dispatch`，ref 固定 main。微博请求、解析、原子快照和 data 分支逻辑继续复用。此项目不包含前端或历史数据库。

## 当前交付状态

代码、本地测试、Cloudflare账号授权、Secret设置、Worker部署及一次真实API探针均已通过。[探针38518846120](https://github.com/kruid1-2/memory-tide-data/actions/runs/38518846120)已核对原始响应、52条话题/50排名及data分支持久化，采集时间为2026-10-14T13:51:03+08:00，来源cloudflare-probe，不计Cron窗口。

**固定北京时间2026-10-14 14:00–16:00观察已结束：数据层8/8成功，漏采0；完整独立日志证据只有4/8，验收未通过。** 实际采样间隔892–909秒，采集延迟36–45秒。14:15、15:15、15:30、15:45缺Cloudflare console日志，等待通过控制台补证；不使用后续样本替代。原生GitHub schedule继续保留，未移除。

Cloudflare分发继续开启，UTC Cron为*/15；源码默认开关false用于防止未授权环境误分发。当前数据层、逐运行SHA256、计划/启动/采集/保存时间及缺证标记见 [TEST_REPORT.md](TEST_REPORT.md)、[WINDOW_REPORT.json](WINDOW_REPORT.json)；已取得的真实脱敏日志见 [ACTUAL_TRIGGER_LOGS.jsonl](ACTUAL_TRIGGER_LOGS.jsonl)。

## 账号与安全设置

1. 在本机本目录执行 `npm ci`、`npm run login`，浏览器完成 Cloudflare 官方 OAuth。账号允许 Workers 部署即可，不启用付费计划。
2. `npm run whoami` 确认账号；多账号时在 Cloudflare 控制台确认目标，再在本地配置 account_id。不要猜测账号。
3. `npm run deploy` 首次部署，保持分发关闭。Cloudflare可能要求先注册 workers.dev 子域，按自己的账号选择；不购买域名。
4. GitHub [Fine-grained PAT 设置](https://github.com/settings/personal-access-tokens/new)：Resource owner=kruid1-2、Only selected repositories=memory-tide-data、Repository permissions **Actions: Read and write**，设置合理到期日。Metadata read 自动存在，不需要 Contents write 或其他仓库权限。
5. 在自己的终端执行 `python3 tools/setup_secrets.py`。隐藏输入新建PAT，直接传给 Wrangler Secret `GITHUB_DISPATCH_TOKEN`；不落盘、不进入命令参数。脚本另生成随机探针凭据，通过 Secret `SCHEDULER_ADMIN_KEY` 注入，本地 `.probe-key` 权限600且忽略上传。**不要把Token发到聊天或粘贴到命令行。** 也可在Cloudflare控制台Worker Settings → Variables and Secrets中选择Secret手动添加；不要创建明文Variable。
6. `npx wrangler deploy --var DISPATCH_ENABLED:true` 开启。每次再次部署需保留此覆盖，否则仓库安全默认值会关闭分发。确认 `npx wrangler secret list` 只显示名称，不读取密钥值。
7. Cloudflare Cron 修改传播可能需最多15分钟；以实际记录为准。日志仅输出字段白名单，禁止将API响应正文、异常message、请求头或任何Token加入日志。

目标 URL 固定 `https://api.github.com/repos/kruid1-2/memory-tide-data/actions/workflows/collect-weibo.yml/dispatches`；请求不跟随重定向。API版本2026-03-10，兼容200/204接受响应。超时10秒、最多3次，2/4秒退避；429/限流按Retry-After（不超过30秒）重试；401/普通403/404/422立即失败，长限流停止并记录。HTTP成功只表示分发接受。

## 一次探针和8个连续窗口

先确认本仓库新版工作流和 `deployment/scheduled_collect.py` 已在 main，仍保留旧schedule。

```sh
# 在自己的终端持续保留真实Cloudflare日志（至少覆盖探针及随后8个窗口）。
npx wrangler tail --format json > reports/cloudflare-live.jsonl
# 另一个终端；替换成自己部署返回的实际URL。
python3 tools/probe.py https://memory-tide-scheduler.YOUR-SUBDOMAIN.workers.dev
```

探针日志 source=cloudflare-probe、GitHub事件workflow_dispatch，只验证真实API路径，**不计入8个Cron窗口**。看GitHub run、成功采集步骤及data分支原始字节，再选择其后的UTC整15分钟作为显式验收起点。

```sh
cd ../memory-tide-data
python3 deployment/normalize_worker_logs.py \
  ../memory-tide-scheduler/reports/cloudflare-live.jsonl \
  ../memory-tide-scheduler/reports/cloudflare-stream-2.jsonl \
  ../memory-tide-scheduler/reports/cloudflare-stream-3.jsonl \
  --out ../memory-tide-scheduler/reports/cloudflare-evidence.jsonl \
  --report live/log_capture_quality.json
python3 deployment/verify_scheduler.py \
  --start 2026-10-14T08:00:00Z --count 8 \
  --logs ../memory-tide-scheduler/reports/cloudflare-evidence.jsonl \
  --out live/cloudflare_windows.json
```

上面的日期只是命令格式示例，必须替换为实际开始观察的未来窗口，不能拿旧样本凑数。报告必须覆盖指定的8个连续窗口；某次失败不得跳过它、拼接散落8次成功来冒充连续性。等待最后窗口结束后核验。缺少真实Cron日志、仅API接受、人工来源、过期或原始响应不一致均不算成功。

报告逐窗口记录：Worker计划与分发时间、GitHub创建/开始时间、实际HTTP响应接收时间、持久化步骤完成时间及分支读回核验；汇总成功/漏采/未到期窗口、实际成功采样间隔与各阶段延迟。Cloudflare控制台Workers Logs提供另一份实际日志查看途径；`tail`若中断，要补齐真实日志，不能自行生成日志文件。

## 去重与历史保护

所有来源共用原工作流固定concurrency组，在恢复最新data分支后检查15分钟窗口。共享依据为真实原始index和追加的 `observations/scheduler/windows/UTC_EPOCH.json`；不会用run-id不同绕过窗口去重。失败不占用窗口，同窗口仍可重试。成功后重试不会请求微博第二次。重复分发写来源记录并指向canonical_run_id，无第二份快照。

Cloudflare输入dispatch_id固定为 `cf-UTC_WINDOW_EPOCH`，重试一致。来源记录在 `observations/scheduler/runs/RUN_ID/ATTEMPT.json`，GitHub event仍为workflow_dispatch。原生schedule和手动来源分别标记，不当成Cloudflare采样。原生schedule的窗口依据runner实际准入时刻（GitHub不公开其精确原定时刻），不能冒称计划时间。过期Cloudflare任务标记expired_window，不用后来的榜单回填；采集跨边界则保留真实原始数据、标记late_collection，验收不计原窗口成功。

## 验收通过后切换

只有探针成功且连续8窗口 `complete=true`、原始响应/快照与持久化全核对之后，才在 `.github/workflows/collect-weibo.yml` 删除 `on.schedule`，保留 `workflow_dispatch` 和固定concurrency，并正常推送。Cloudflare仍每15分钟分发。不删除data分支任何历史文件；不在验收前禁用原生schedule。新版8窗口脚本与旧 `verify_cloud.py` 分开，旧脚本只审计历史原生schedule。

## 故障排查与限制

- missing_secret/401/403：检查Secret名称、PAT到期、选中仓库和Actions write；不输出Token。可执行隐藏输入脚本轮换。
- dispatch_failed：看白名单HTTP状态与重试次数，API接受不代表runner启动。
- expired_window/漏采：排查GitHub排队和concurrency pending替换；Cloudflare不能消除GitHub runner延迟，仍需按报告评估实际采样间隔。
- duplicate_window：同窗口其他来源已采样，读canonical_run_id；不视为新增采样。
- push失败：沿用原outbox artifact救援，不force push或回滚旧数据。
- Cloudflare没有日志：看Cron注册、传播、分发开关及Workers Logs；不能把没有报错当成功。
- 停止Cloudflare分发：`npx wrangler deploy --var DISPATCH_ENABLED:false`；不重置历史数据。

本次仅使用现有Workers能力，不开通付费服务；如果账号配额或产品要求付费，应停止并提示用户，不擅自升级。Cron触发稳定性最终依赖端到端实测。

## 验证

`npm test`、`npm run check`、`python3 -m unittest discover -s test -p test_probe.py -v`；在memory-tide-data内运行 `python3 -m unittest discover -s tests -v`；工作流用actionlint校验。测试fixture只在临时目录，不写真实data分支。

官方参考：[Cron](https://developers.cloudflare.com/workers/configuration/cron-triggers/)、[Secrets](https://developers.cloudflare.com/workers/configuration/secrets/)、[Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)、[GitHub dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)。

日志捕获故障：两个旧tail进程已断线退出，原日志保留。新增normalize_worker_logs.py仅提取完整真实console对象，遇到损坏/截断立即停止该文件并显式报告偏移和SHA256；不修补事件。新的单一tail追加cloudflare-stream-2.jsonl。验收读取去重白名单副本cloudflare-evidence.jsonl，缺失日志的窗口仍不能通过。服务端历史日志只读查询返回403时，不擅自扩大权限或凭空补证。

## 2026-10-15 正式切换验收（尚未通过）

保留2026-10-14原实验结论：真实数据8/8、漏采0，但独立Cloudflare日志仅4/8；不把缺证推断为成功。用户已授权必要时另做连续验收。新的独立实验固定为2026-10-15 03:00–05:00 UTC（北京时间11:00–13:00），共8个连续15分钟窗口。通过前保留GitHub原生schedule。通过后以实际推送完成之后的下一个完整UTC刻钟为起点，另外固定4个切换后窗口；全部通过再停止临时检查。

本次核验工具只下载实验时段的GitHub运行元数据，避免历史数量增长导致每次核验扫描全部记录。临时日志订阅使用单实例锁并断线自动重连，每次连接保留独立原始文件，损坏会话不会截断后续连接的证据。Worker采集、解析和存储逻辑未改变。云端持久日志设置仍需控制台读回确认；当前没有凭源码配置宣称它已核实。

临时验收日志订阅（需要已完成Wrangler登录）：

```sh
python3 tools/capture_logs.py
```

原始会话位于`reports/acceptance-capture/tail-*.jsonl`，连接退出记录位于`connections.jsonl`。该目录整体忽略，禁止上传原始请求头。使用数据项目的`normalize_worker_logs.py`提取console白名单事件，公开报告只包含脱敏事件。这个临时订阅依赖本机在线，不能取代云端Workers Logs。Cloudflare Logs保留期按计划为Free 3天、Paid 7天，应在保留期内导出必要故障证据；见[官方Workers Logs文档](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)。

## 2026-10-15 正式切换阶段

新固定11:00–13:00实验已完成真实8/8端到端核验，422话题观测/400排名、漏采0、触发失败0、实际间隔892–908秒；云端Cron和100%持久日志已在控制台读回。本次提交移除GitHub原生schedule，保留workflow_dispatch和固定并发锁。切换后4窗口尚待观察，完整迁移验收尚未结束。原10月14日日志缺证结论继续保留。

## 长期运维与查看状态

- GitHub Actions中的运行名称包含`cloudflare-cron`和窗口ID；事件为workflow_dispatch，人工运行名称为manual。
- data分支的`observations/status.json`提供最后成功时间和失败状态；原始响应、snapshots、index及scheduler元数据均追加保留。
- Cloudflare控制台：Worker → 设置 → 触发事件核对Cron；可观察性中Workers日志/保留到仪表板/100%采样已实际确认。
- GitHub Token于2026-11-13到期，提前安全续期并运行`python3 tools/setup_secrets.py`隐藏输入更新。不要把Token发给任何人或写入仓库。
- 临时验收日志订阅已结束；云端采集不依赖本机。本次通过是实际观察结果，不代表外部服务永不延迟或故障。
