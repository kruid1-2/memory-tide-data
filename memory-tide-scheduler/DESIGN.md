# Cloudflare 调度设计与执行计划

用户目标：Cloudflare UTC */15 * * * * 调用既有 Actions workflow_dispatch(main)，保留历史数据和原生 schedule，直至连续8窗口端到端实测通过。

- 独立 Worker：Fine-grained PAT 从 GITHUB_DISPATCH_TOKEN Secret 读取，仓库仅限 memory-tide-data，Actions write。固定目标 URL/ref 防止凭据发送到其他位置。
- GitHub API版本2026-03-10；接受200（含run id）或204，不把接受分发当采样成功。超时10秒，最多3次；401/403权限错误/404/422不盲重试。日志仅白名单字段，不输出响应正文、异常message或Token。
- 输入 trigger_source（cloudflare-cron/cloudflare-probe/manual）、scheduled_at、dispatched_at、dispatch_id。Cron的dispatch_id由UTC窗口稳定派生；所有重试相同。探针单独标识，不计8窗口。受保护HTTP探针需要独立随机Secret，默认所有其他HTTP请求404。
- 不改 live.py/core.py。增加 Python 外层：从data分支已有真实index及窗口记录去重，使用现有固定concurrency串行写。成功才占用窗口；失败留错误、同窗口可重试。窗口按UTC整15分钟，Cloudflare旧窗口过期不晚采、不补数据，原生schedule与人工均遵守同窗口限制。
- 保留run-id原始文件命名与原子保存。附加observations/scheduler/runs/RUN_ID/ATTEMPT.json与windows记录关联来源、计划时间、GitHub创建/启动、采集完成。持久化完成由GitHub步骤completed_at并读回data分支证明。
- 对账必须明确8个连续窗口，逐窗口需要Cloudflare真实Cron日志、workflow_dispatch来源元数据、成功步骤、原始响应重新解析一致、采样位于该窗口内。重试/重复分发不增加采样数，人工probe不计数。
- 稳定性不保证：Cloudflare改善事件生成仍可能受GitHub队列影响，过期运行要标记漏采。验收失败不移除原生schedule。

实施顺序：先失败测试（Worker错误/重试/保密与Python跨来源去重/过期/失败恢复），再实现；跑旧回归；Wrangler本地构建；最小文件审查/推送；登录与Secret就绪后部署；探针验真；日志+8窗口报告；全部成功才移除原生schedule。

授权阻塞：本机暂无Cloudflare会话，用户已确认有账号、可浏览器登录。不得将现有gh CLI凭据转为Worker Secret代替指定Fine-grained PAT。
