# Cloudflare 调度验收记录

日期：2026-10-14。阶段：本地实现与测试完成，云端授权/Secret尚待用户操作。**未部署，不是8窗口验收完成。**

- Worker：7项离线测试通过，含GitHub 200/204、固定main、有限重试、超时、权限错误不重试、日志敏感值不泄露、旧窗口不分发、受保护探针。
- Python：新增6项共享窗口去重/失败恢复/来源分类测试，以及3项连续窗口验收测试通过；原32项回归通过。全部仅临时测试数据。
- 官方Wrangler固定4.150.0，npm审计0漏洞；本地dry-run成功，无线上上传。首次npm下载超时后重试成功。日志目录权限问题通过项目内WRANGLER_LOG_PATH解决。
- actionlint校验通过；原生schedule仍保留。
- 核心 live.py/core.py/restore_data.sh/persist_data.sh 不改，历史数据库和前端不动。
- 账号：首次Wrangler OAuth等待授权超时，用户已收到重新登录命令。Fine-grained PAT尚未创建/注入，不使用gh CLI已有Token替代。

| 云端验证项 | 实际结果 |
|---|---|
| Cloudflare部署/UTC Cron注册 | 未执行，等待登录 |
| Secret注入 | 未执行，等待用户隐藏输入 |
| Worker真实API探针 | 未执行 |
| 连续8窗口开始/结束 | 尚未确定 |
| 成功采样窗口 | 未取得真实证据，不记为0次实测或8次通过 |
| 实际采样间隔/漏采/延迟 | 待真实日志与远程快照核对，当前不可计算 |
| 移除GitHub原生schedule | 未执行，保留 |

后续填入Cloudflare真实Cron日志、每个窗口的run URL、原始SHA256、实际采集及保存时间；不得把本地fixture或原来的原生schedule结果当作Cloudflare验收。
