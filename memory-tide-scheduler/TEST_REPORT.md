# Cloudflare 调度验收记录

日期：2026-10-14。固定14:00–16:00观察期已结束：**真实采样8/8、实际漏采0；完整独立日志证据4/8，验收尚未通过，等待补齐4窗口Cloudflare日志。原生GitHub schedule保留。**

## 初期部署记录（历史状态；最新固定实验结果见末节）

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

## 首次周期核验与日志捕获故障

两个原Wrangler tail连接断线并在重连5次后退出，原始文件末尾出现非JSON断线提示；首次周期验收因此未完成，旧基线未当成新检查。完整可解析对象中保留真实14:00的dispatch_accepted日志。新增normalize_worker_logs.py在损坏边界停止提取，记录原文件SHA256、有效JSON对象数及损坏偏移；不修改原始日志，不修造事件，HTTP请求头不进入校验副本。2项回归测试通过。新单一tail为session7997，追加cloudflare-stream-2.jsonl。

14:00窗口运行 [38519715301](https://github.com/kruid1-2/memory-tide-data/actions/runs/38519715301)已完整通过：来源cloudflare-cron，计划14:00:00、实际分发14:00:27.888、GitHub创建14:00:28、job开始14:00:32、实际采集14:00:36、持久化完成14:00:37（均北京时间）；53话题/50排名，原始SHA256 `d479b223edfc850df7ead0e2b7f05851d6d50a6141d495a5b910553b74fa40a9`。

14:15窗口运行38521153022存在成功快照，但缺少Cloudflare console日志，暂不计完整通过。服务端历史日志查询返回HTTP403/code10000，仅是查询权限不足，不是GitHub采集凭据错误；没有扩大授权或生成替代证据。固定实验起止时间仍保持14:00–16:00，原生schedule继续保留。

## 固定14:00–16:00实验结束：数据8/8，独立日志证据4/8，验收尚未通过

检查时间：2026-10-14T18:51:16+08:00。没有移动原实验起点，也没有用后续成功窗口替换缺证窗口。

- 数据层：8份窗口内真实快照全部重新解析原始响应、核对SHA256及GitHub采集/验证/持久化步骤，**8/8成功，实际漏采0**；共418条话题观测、400个正式排名观测。
- 完整端到端独立证据：**4/8**。14:15、15:15、15:30、15:45缺Cloudflare console日志；GitHub来源元数据即使标明cloudflare-cron，也不能替代独立日志。
- 原始采样间隔（秒）：900、900、900、900、909、892、900；最小892、最大909，平均900.143。计划到接收延迟36–45秒、平均37.375秒；计划到持久化完成37–46秒。Worker实际分发延迟27.871–27.896秒（缺日志窗口的值来自保存的输入元数据，不能冒称独立日志已证实）。
- 当前最后成功更新时间：2026-10-14T18:45:39+08:00。此为持续采集状态，实验统计仍严格限原14:00–16:00范围。
- 本机日志订阅再次因keep-alive超时退出，已恢复唯一新订阅session84352追加cloudflare-stream-3.jsonl。新日志不会被用于冒充过去窗口的缺失记录。服务端日志查询权限仍403；未扩大权限、未读取/输出GitHub Secret。
- 需要用户通过Cloudflare控制台补取上述4窗口的真实dispatch_accepted console日志（仅白名单字段，不提供请求头或密钥），否则不能满足原验收条件。**原生GitHub schedule保持开启，不执行移除。**

下表时间均为北京时间，来源均为weibo/official-desktop-hotsearch-v1；事件均为workflow_dispatch，保存的触发来源为cloudflare-cron。HTTP成功本身没有计为采样成功。

| 计划 | Worker分发 | GitHub创建 | Job启动 | 实际接收 | 持久化完成 | 运行 | 话题/排名 | 独立CF日志 |
|---|---|---|---|---|---|---|---:|---|
| 14:00:00 | 14:00:27.888 | 14:00:28 | 14:00:32 | 14:00:36 | 14:00:37 | [38519715301](https://github.com/kruid1-2/memory-tide-data/actions/runs/38519715301) | 53/50 | 已核对 |
| 14:15:00 | 14:15:27.884 | 14:15:28 | 14:15:32 | 14:15:36 | 14:15:37 | [38521153022](https://github.com/kruid1-2/memory-tide-data/actions/runs/38521153022) | 53/50 | 缺证 |
| 14:30:00 | 14:30:27.871 | 14:30:28 | 14:30:32 | 14:30:36 | 14:30:37 | [38522609837](https://github.com/kruid1-2/memory-tide-data/actions/runs/38522609837) | 52/50 | 已核对 |
| 14:45:00 | 14:45:27.893 | 14:45:28 | 14:45:32 | 14:45:36 | 14:45:37 | [38524091438](https://github.com/kruid1-2/memory-tide-data/actions/runs/38524091438) | 51/50 | 已核对 |
| 15:00:00 | 15:00:27.881 | 15:00:28 | 15:00:31 | 15:00:36 | 15:00:37 | [38525594692](https://github.com/kruid1-2/memory-tide-data/actions/runs/38525594692) | 52/50 | 已核对 |
| 15:15:00 | 15:15:27.894 | 15:15:29 | 15:15:33 | 15:15:45 | 15:15:46 | [38527152483](https://github.com/kruid1-2/memory-tide-data/actions/runs/38527152483) | 52/50 | 缺证 |
| 15:30:00 | 15:30:27.896 | 15:30:29 | 15:30:33 | 15:30:37 | 15:30:38 | [38528765651](https://github.com/kruid1-2/memory-tide-data/actions/runs/38528765651) | 52/50 | 缺证 |
| 15:45:00 | 15:45:27.879 | 15:45:29 | 15:45:33 | 15:45:37 | 15:45:39 | [38530425189](https://github.com/kruid1-2/memory-tide-data/actions/runs/38530425189) | 53/50 | 缺证 |

原始响应SHA256及快照位置（均相对于data分支observations/）：

- 38519715301：`snapshots/2026-10-14/140036_38519715301.json`，原始 `raw/2026-10-14/140036_38519715301.json`；SHA256 `d479b223edfc850df7ead0e2b7f05851d6d50a6141d495a5b910553b74fa40a9`。
- 38521153022：`snapshots/2026-10-14/141536_38521153022.json`，原始 `raw/2026-10-14/141536_38521153022.json`；SHA256 `2555f83f22281453b7ed499ab0649b32f3c64abb45737cc9440ccc4fe166413d`。
- 38522609837：`snapshots/2026-10-14/143036_38522609837.json`，原始 `raw/2026-10-14/143036_38522609837.json`；SHA256 `0629165591eaf817faaed3bb6b362e00c16ddc506296c819b570ac957465ed7e`。
- 38524091438：`snapshots/2026-10-14/144536_38524091438.json`，原始 `raw/2026-10-14/144536_38524091438.json`；SHA256 `418c129125e1b4fa30d7bb8ee70d1dfae1f0b93a404c54f84f58ea266345c5e7`。
- 38525594692：`snapshots/2026-10-14/150036_38525594692.json`，原始 `raw/2026-10-14/150036_38525594692.json`；SHA256 `a3280d3051f3ee5a43d1864418a3ed3e9d206b1f459096d351c6460d8ff0c9e2`。
- 38527152483：`snapshots/2026-10-14/151545_38527152483.json`，原始 `raw/2026-10-14/151545_38527152483.json`；SHA256 `9255da87ad90ba812abc6fa5d06928ee42bad36458f946efdb74c967b5149df7`。
- 38528765651：`snapshots/2026-10-14/153037_38528765651.json`，原始 `raw/2026-10-14/153037_38528765651.json`；SHA256 `9d7523339a9a5e6d5c54dfb4bdc64a3c69050d2f91db563bceba891eac161176`。
- 38530425189：`snapshots/2026-10-14/154537_38530425189.json`，原始 `raw/2026-10-14/154537_38530425189.json`；SHA256 `6b93582fd45f610b4ee7237419d9674369a8f7841580f699cc2eb9cc31e97d59`。

机器可读完整数据层结果及缺证标记见 [WINDOW_REPORT.json](WINDOW_REPORT.json)，实际已取得的脱敏日志见 [ACTUAL_TRIGGER_LOGS.jsonl](ACTUAL_TRIGGER_LOGS.jsonl)。这两类证据保持分开，缺证不会改写成通过。

## 2026-10-15 正式切换验收（尚未通过）

保留2026-10-14原实验结论：真实数据8/8、漏采0，但独立Cloudflare日志仅4/8；不把缺证推断为成功。用户已授权必要时另做连续验收。新的独立实验固定为2026-10-15 03:00–05:00 UTC（北京时间11:00–13:00），共8个连续15分钟窗口。通过前保留GitHub原生schedule。通过后以实际推送完成之后的下一个完整UTC刻钟为起点，另外固定4个切换后窗口；全部通过再停止临时检查。

本次核验工具只下载实验时段的GitHub运行元数据，避免历史数量增长导致每次核验扫描全部记录。临时日志订阅使用单实例锁并断线自动重连，每次连接保留独立原始文件，损坏会话不会截断后续连接的证据。Worker采集、解析和存储逻辑未改变。云端持久日志设置仍需控制台读回确认；当前没有凭源码配置宣称它已核实。

## 2026-10-15 新实验8窗口通过，进入正式切换

固定2026-10-15 03:00–05:00 UTC（北京时间11:00–13:00）新实验已于06:17:14 UTC重新完成端到端核验：8/8、422条话题观测/400个排名，漏采0，Cloudflare触发失败0（8个窗口均首次请求接受）。实际采样间隔899、908、892、904、897、901、899秒，均值900秒。原2026-10-14缺证实验保留，不追认其4条缺失日志。

Cloudflare控制台已实际读回：Cron `*/15 * * * *`，DISPATCH_ENABLED=true；Workers日志开启，调用日志开启，保留到仪表板开启，采样100%。本机监督订阅发生过网络重连，属于证据捕获连接问题，未冒称采集失败。

| UTC计划时间 | GitHub运行 | 实际采集北京时间 | 话题/排名 | 采集延迟秒 |
|---|---|---|---|---|
| 2026-10-15T03:00:00Z | [38674013729](https://github.com/kruid1-2/memory-tide-data/actions/runs/38674013729) | 2026-10-15T11:00:57+08:00 | 52/50 | 57 |
| 2026-10-15T03:15:00Z | [38675343359](https://github.com/kruid1-2/memory-tide-data/actions/runs/38675343359) | 2026-10-15T11:15:56+08:00 | 52/50 | 56 |
| 2026-10-15T03:30:00Z | [38676649628](https://github.com/kruid1-2/memory-tide-data/actions/runs/38676649628) | 2026-10-15T11:31:04+08:00 | 53/50 | 64 |
| 2026-10-15T03:45:00Z | [38677945527](https://github.com/kruid1-2/memory-tide-data/actions/runs/38677945527) | 2026-10-15T11:45:56+08:00 | 53/50 | 56 |
| 2026-10-15T04:00:00Z | [38679222629](https://github.com/kruid1-2/memory-tide-data/actions/runs/38679222629) | 2026-10-15T12:01:00+08:00 | 53/50 | 60 |
| 2026-10-15T04:15:00Z | [38680548437](https://github.com/kruid1-2/memory-tide-data/actions/runs/38680548437) | 2026-10-15T12:15:57+08:00 | 53/50 | 57 |
| 2026-10-15T04:30:00Z | [38681852752](https://github.com/kruid1-2/memory-tide-data/actions/runs/38681852752) | 2026-10-15T12:30:58+08:00 | 53/50 | 58 |
| 2026-10-15T04:45:00Z | [38683172185](https://github.com/kruid1-2/memory-tide-data/actions/runs/38683172185) | 2026-10-15T12:45:57+08:00 | 53/50 | 57 |

逐窗计划/分发、GitHub创建/启动/队列、实际采集、持久化完成、原始SHA256和来源见[ACCEPTANCE_20261015.json](ACCEPTANCE_20261015.json)；独立Cloudflare console白名单记录见[ACCEPTANCE_TRIGGER_LOGS.jsonl](ACCEPTANCE_TRIGGER_LOGS.jsonl)。8次均为workflow_dispatch + cloudflare-cron，原生schedule、人工和probe未计入。

本次切换提交仅移除GitHub工作流原生schedule，保留workflow_dispatch、来源输入和固定concurrency，不禁用工作流、不修改采集核心或data历史。切换后4窗口尚待观察，不宣布整个迁移完成。观察起点须在远程切换确认之后固定。

## 2026-10-15 最终验收通过

新固定实验11:00–13:00（北京时间）8/8完整通过；正式切换提交`cfaaec5234b1b375bc94bef5ae1e3012395f581f`已移除原生schedule，保留workflow_dispatch、工作流active和固定concurrency。远程读回与本地工作流字节一致，切换后未出现新的原生schedule事件。

切换后严格固定14:30–15:30的4窗口也已全部通过，212条话题观测/200个排名，漏采0、Cloudflare触发失败0；每窗均由自己的cloudflare-cron分发运行采集，没有借用人工或原生schedule的canonical快照。实际采样间隔896、907、893秒（14分53秒–15分07秒），平均898.667秒；采集延迟62、58、65、58秒。Cloudflare接受请求并非成功标准：已核对真实console日志、GitHub成功步骤、远程原始字节SHA256、重新解析结果及持久化完成时间。

| UTC计划时间 | GitHub运行 | 实际采集北京时间 | 话题/排名 | 采集延迟秒 |
|---|---|---|---|---|
| 2026-10-15T06:30:00Z | [38692857452](https://github.com/kruid1-2/memory-tide-data/actions/runs/38692857452) | 2026-10-15T14:31:02+08:00 | 53/50 | 62 |
| 2026-10-15T06:45:00Z | [38694374639](https://github.com/kruid1-2/memory-tide-data/actions/runs/38694374639) | 2026-10-15T14:45:58+08:00 | 53/50 | 58 |
| 2026-10-15T07:00:00Z | [38695947701](https://github.com/kruid1-2/memory-tide-data/actions/runs/38695947701) | 2026-10-15T15:01:05+08:00 | 53/50 | 65 |
| 2026-10-15T07:15:00Z | [38697568582](https://github.com/kruid1-2/memory-tide-data/actions/runs/38697568582) | 2026-10-15T15:15:58+08:00 | 53/50 | 58 |

最新额外核验：[38727867711](https://github.com/kruid1-2/memory-tide-data/actions/runs/38727867711)，2026-10-15T19:30:58+08:00，53话题/50排名，来源cloudflare-cron，原始SHA256 `fb5e715fd927094fc204d7e6b35f488e320c41c76132a942705fbb80910f7a1c`。最终检查时data分支有126个快照，首次手动和探针记录仍存在，未重置或删除历史。

云端实际配置已读回：Cron `*/15 * * * *`，DISPATCH_ENABLED=true，已验收版本100%流量；Workers日志开启、调用日志开启、保留到仪表板开启、采样100%。临时本机日志监督进程已停止，Cloudflare采集继续运行；验收heartbeat在最终文件发布并读回之后暂停。

### 原实验日志补证及故障保留

2026-10-14原实验最初数据8/8但独立日志4/8，原因是本机tail连接中断。2026-10-15从Cloudflare Dashboard Observability按原UTC06:00–08:00检索，逐条展开实际console详情，提取14:15、15:15、15:30、15:45四条dispatch_accepted白名单字段。没有推断或生成替代事件，未导出请求头或账户元数据。补证后于2026-10-15T06:25:57Z独立重核8/8；原缺证报告和故障原始文件继续保留。此补证不替换新实验或切换后4窗口。

### 证据与长期运行

- [POST_SWITCH_REPORT.json](POST_SWITCH_REPORT.json)：后4窗逐次计划/分发、GH创建/启动/队列、采集、持久化及SHA256。
- [POST_SWITCH_TRIGGER_LOGS.jsonl](POST_SWITCH_TRIGGER_LOGS.jsonl)：后4窗真实console白名单。
- [ORIGINAL_LOG_RECOVERY_20261015.jsonl](ORIGINAL_LOG_RECOVERY_20261015.jsonl)、[ORIGINAL_RECOVERY_REPORT.json](ORIGINAL_RECOVERY_REPORT.json)：原实验后补证据与单独重核。
- [FINAL_VERIFICATION.json](FINAL_VERIFICATION.json)：最终开关、最新采样、间隔及历史保留检查。

系统采集可在本机关闭时继续运行，无需人工每15分钟操作；但GitHub Fine-grained Token将在2026-11-13到期，必须在到期前安全续期并用tools/setup_secrets.py更新Cloudflare Secret，禁止放入聊天、源码或日志。到期、GitHub/Cloudflare故障或微博接口变化仍可能中断，有限验收不保证永久可用。免费Workers日志保留3天，重要故障应在保留期内保存；当前未启用额外付费存储。
