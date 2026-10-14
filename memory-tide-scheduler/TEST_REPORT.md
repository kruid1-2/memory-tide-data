# Cloudflare 调度验收记录

日期：2026-10-14。阶段：Cloudflare授权/Secret/分发开启及真实Worker API探针核验均通过。**固定北京时间14:00–16:00的8窗口验收已启动核验机制，结果尚未完成；原生GitHub schedule仍保留。**

- Worker：7项离线测试通过，含GitHub 200/204、固定main、有限重试、超时、权限错误不重试、日志敏感值不泄露、旧窗口不分发、受保护探针。
- Python：新增6项共享窗口去重/失败恢复/来源分类测试，以及3项连续窗口验收测试通过；原32项回归通过。全部仅临时测试数据。
- 官方Wrangler固定4.150.0，npm审计0漏洞；本地dry-run成功；随后已完成首次真实线上上传。首次npm下载超时后重试成功。日志目录权限问题通过项目内WRANGLER_LOG_PATH解决。
- actionlint校验通过；原生schedule仍保留。
- 核心 live.py/core.py/restore_data.sh/persist_data.sh 不改，历史数据库和前端不动。
- 账号：首次Wrangler OAuth等待授权超时后，用户已在浏览器完成授权；Wrangler whoami已确认会话可用。Secret列表为空，Fine-grained PAT尚未注入，不使用gh CLI已有Token替代。

| 云端验证项 | 实际结果 |
|---|---|
| Cloudflare部署/UTC Cron注册 | 已完成；版本b37be104-b76b-4e3b-8b65-baf7c4f5d250，cron=*/15 * * * *，DISPATCH_ENABLED=false |
| Secret注入 | 已完成；仅查验名称，未读取明文；重新输入后实际GitHub请求成功 |
| Worker真实API探针 | 38518846120，原始字节/快照/持久化均核对通过 |
| 连续8窗口开始/结束 | 固定2026-10-14T06:00:00Z至08:00:00Z（北京时间14:00–16:00） |
| 成功采样窗口 | 基线0/8，8窗口均未到期，尚无漏采；probe不计入 |
| 实际采样间隔/漏采/延迟 | 待真实日志与远程快照核对，当前不可计算 |
| 移除GitHub原生schedule | 未执行，保留 |

后续填入Cloudflare真实Cron日志、每个窗口的run URL、原始SHA256、实际采集及保存时间；不得把本地fixture或原来的原生schedule结果当作Cloudflare验收。

## 新入口 GitHub 云端兼容性验证（独立于Cloudflare验收）

[运行38515048705](https://github.com/kruid1-2/memory-tide-data/actions/runs/38515048705)于2026-10-14T13:08:40+08:00接收真实榜单，53条话题、50个排名，采集/验证/持久化全部success。data分支原始响应重新解析与快照逐字段相同，SHA256 `2531c6055447f1028f329b2f4cd3c62939fc394165157f21f332586fb54ccfed`。

该运行 event=workflow_dispatch、trigger_source=manual，来源记录已保存 `observations/scheduler/runs/38515048705/1.json`；窗口记录 `observations/scheduler/windows/1791954000.json`。**只是新版入口兼容性验证，不是Worker API探针，不计入Cloudflare连续8窗口。** 快照路径 `observations/snapshots/2026-10-14/130840_38515048705.json`。原有data历史继续保留。

## Cloudflare首次真实部署（2026-10-14）

部署前检查同名Worker不存在（Cloudflare code10007），随后官方Wrangler成功上传并注册Cron。部署创建时间2026-10-14T05:13:48.865Z（北京时间13:13:48），版本 `b37be104-b76b-4e3b-8b65-baf7c4f5d250`，流量100%。Secret列表读回为 `[]`，分发开关false。

系统curl正常TLS校验：公开根路径返回404，未授权POST /probe返回401。此项只证明服务已部署及访问控制有效，不是GitHub分发成功。原Python探针在本机遇到CA信任错误，已改用系统curl，密钥通过stdin提供，不在参数、文件或日志中传递；2项回归测试通过，未禁用证书验证。

实际服务URL和私有部署检查细节仅保留本地 `reports/deployment.json`，不公开账号邮箱/账号ID。下一步需用户通过隐藏输入设置Fine-grained PAT Secret，然后才开启分发、验证Worker API路径并观察8个连续窗口。

## Secret设置后的真实探针与失败诊断（2026-10-14）

两个Secret名称（GITHUB_DISPATCH_TOKEN、SCHEDULER_ADMIN_KEY）已从Cloudflare读回；值没有读取或输出。本地探针凭据权限600。

- 首次开启后的真实探针在收到HTTP响应前失败。13:30窗口的真实Cron也按三次有限重试失败，不能记为成功窗口。日志只保存受控分类，未输出异常原文或Token。
- 增加白名单分类后定位为运行时选项不兼容；只把redirect:error改为redirect:manual并对所有3xx拒绝，不跨站转发Authorization。新版实际请求已取得GitHub HTTP401，证明原选项错误已消除，但凭据未被GitHub接受。Token无首尾空白，复制是否完整或凭据是否有效尚未确认，不将其误报为仓库权限故障。
- 已增加上传前GitHub身份检查：自己的终端隐藏输入，凭据只经stdin传给系统curl，响应正文丢弃；只有HTTP200才更新Cloudflare Secret，错误仅输出HTTP码。不会读取聊天或剪贴板。
- 当前Cloudflare分发暂时关闭（Cron保留），避免持续401；GitHub原生schedule仍开启。8连续窗口验收尚未开始，等待用户重新隐藏输入有效凭据。真实初步日志位于本地reports/cloudflare-live.jsonl，白名单提取位于reports/preliminary_logs.json，不公开账号信息或请求头。
- Worker现有9项测试、探针2项回归测试通过；原Python41项此前通过。

## 真实Worker探针通过与固定8窗口启动

重新在用户终端隐藏输入并验证/注入凭据后，新版部署 `972899b2-b0d4-4772-a537-da63ddf92d59` 的非敏感绑定已读回 `DISPATCH_ENABLED=true`，Cron仍为 `*/15 * * * *`。部署刚完成时一次探针仍读到旧版disabled，后续实际请求成功；不把旧版disabled请求当成功。

- Cloudflare实际分发：2026-10-14T05:50:53.354Z（北京时间13:50:53.354）。
- Worker日志：dispatch_accepted，GitHub HTTP200，run_id=38518846120；来源cloudflare-probe。
- [GitHub真实探针38518846120](https://github.com/kruid1-2/memory-tide-data/actions/runs/38518846120)：workflow_dispatch，创建2026-10-14T05:50:54Z，关键采集、验证、持久化步骤全部success。
- 实际采集：2026-10-14T13:51:03+08:00，52条话题、50个排名，原始响应SHA256 `c4c4e8e05748fc01aa45785396d63cba0c773c5c171ef57d4df514e7cde9eaf2`，远程重解析与快照逐字段一致。
- data永久快照：`observations/snapshots/2026-10-14/135103_38518846120.json`；来源记录：`observations/scheduler/runs/38518846120/1.json`；直接来源weibo/official-desktop-hotsearch-v1。
- **probe不计入8个真实Cron窗口**。固定06:00、06:15、06:30、06:45、07:00、07:15、07:30、07:45 UTC，完整观察至08:00 UTC。若任一窗口失败/缺失，原报告保留，不能偷偷改开始时间来凑满8次。
- 基线报告检查于05:53:35Z：成功0、漏采0、待到期8，complete=false。只有最后窗口结束且全部核验才通过。验收脚本已增加2项时长边界测试（总11项scheduler测试通过），避免最后一个样本刚到就提前结束观察。
- 当前实际日志的白名单副本见 [ACTUAL_TRIGGER_LOGS.jsonl](ACTUAL_TRIGGER_LOGS.jsonl)，包含初步真实失败与成功probe，不包含请求头或凭据。后续更新真实Cron日志与每个窗口的完整证据。
- 已启用本聊天的ACTIVE heartbeat `memory-tide`（Cloudflare连续8窗口验收），每10分钟读取真实日志及远程快照报告结果。Wrangler tail仍为实际运行的本机长进程；若机器休眠或日志断开，核验必须标记缺证并修复，不能伪造。

原生schedule仅在8个固定窗口全部核对成功、完整观察时段结束且文档交付后移除。
