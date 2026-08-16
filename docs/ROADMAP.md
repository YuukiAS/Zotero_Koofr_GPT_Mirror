# Roadmap

这个项目的目标不是一次性把所有自动化都做完，而是按风险从低到高逐步建立一条稳定链路：

```text
Zotero 本地数据
→ 可读镜像
→ Google Drive
→ ChatGPT 可检索
→ 定时自动运行
→ 最后才考虑删除同步和高级能力
```

核心原则是：**先验证“能正确读、能正确整理、GPT 真能用”，再做全自动和删除。**

---

## Phase 0：设计冻结

目标：先把系统边界说清楚，避免实现过程中不断换方向。

当前已经确定：

- Zotero 是唯一事实来源；
- Koofr 继续只作为 Zotero WebDAV 附件后端；
- 工位 Windows 是长期运行节点；
- 不从 Koofr WebDAV 直接抓 `.zip/.prop`；
- 不直接读取 `zotero.sqlite`；
- 使用 Zotero Local API 获取 metadata 和 attachment；
- 本地生成一份人类可读的 PDF 镜像；
- 使用 rclone 上传 Google Drive；
- ChatGPT 通过 Google Drive 连接/同步能力检索；
- 第一阶段只允许单向复制，不允许远端删除；
- 当前不引入 MCP、Tunnel、Cloudflare 或公网服务。

完成标准：README、Roadmap、TODO 对架构没有互相冲突的描述。

状态：**完成**。

---

## Phase 1：最小 Zotero 导出原型

目标：证明我们可以稳定地从本机 Zotero 得到“论文记录 → 正确 PDF”。

实现内容：

1. 建立 Python 项目骨架；
2. 检查 Zotero Local API 是否可用；
3. 读取少量普通 bibliographic item；
4. 获取标题、作者、年份、DOI、URL、abstract、tags、collections；
5. 获取 PDF attachment；
6. 获取并验证本地 PDF 路径；
7. 对未下载附件进行明确标记；
8. 不修改 Zotero。

这一阶段先不要全库导出，也不要碰 Google Drive。

测试样本建议人工挑 5~10 条，至少覆盖：

- 普通 journal article + 单 PDF；
- 标题含特殊字符；
- 中文或其他 Unicode 标题；
- 缺年份；
- 无 PDF；
- PDF 尚未下载；
- 一个 item 有多个 attachment。

完成标准：

- 每个测试 item 都能稳定找到正确 attachment；
- Local API 不可用时程序明确失败；
- 不会把 API 失败误判为“库为空”。

建议版本：`0.1.0`

---

## Phase 2：建立人类可读镜像

目标：把 Zotero 内部结构变成人和 GPT 都容易理解的文件结构。

实现内容：

1. 设计稳定的文件名规范；
2. 清理 Windows 非法字符；
3. 处理超长标题；
4. 处理 Unicode 正规化；
5. 使用 Zotero item key 解决碰撞；
6. 按年份放入 `Papers/<year>/`；
7. 为每篇论文生成 `.md` sidecar；
8. 生成 `_Index/library.csv`；
9. 生成 `_Index/manifest.json`；
10. 生成 `_Status/last-sync.json`。

需要明确多个 PDF attachment 的语义。第一版可以采用“主 PDF + 其他 PDF 后缀”的方式，但不能静默覆盖。

完成标准：

- 人打开镜像目录，不需要 Zotero 知识也能找到论文；
- 同名论文不会互相覆盖；
- collection 和 tag 不通过复制 PDF 来表达；
- sidecar 中的 metadata 足够支持 ChatGPT 搜索；
- 镜像目录可以安全删除后重新完整生成。

建议版本：`0.2.0`

---

## Phase 3：增量导出与安全状态

目标：从“每次全量重建”变成适合每 15 分钟运行的稳定工具。

实现内容：

1. 保存上次成功 manifest；
2. 根据 item key / attachment key 判断稳定对象；
3. metadata 不变时跳过 `.md` 重写；
4. PDF 没变化时不重复复制；
5. 新增 item 增量加入；
6. 修改 metadata 时正确重命名和更新；
7. 删除先记录 tombstone，不立即传播到 Google Drive；
8. 统计本轮新增、修改、缺失、错误数量；
9. 加入异常暴跌保护。

关键安全约束：

```text
Local API 不可用
OR item 数量异常
OR exporter fatal error
OR manifest 未完成
=> 本轮不得进入上传/删除阶段
```

完成标准：

- 连续运行两次，无变化时第二次基本不产生文件变更；
- 新增一篇论文只影响对应文件和索引；
- 单个附件暂时未下载不会被当作 Zotero 删除；
- 异常情况下不会清空镜像。

建议版本：`0.3.0`

---

## Phase 4：Google Drive 上传

目标：把已经验证正确的本地镜像可靠地放进 Google Drive。

实现内容：

1. 安装 rclone；
2. 配置 `gdrive:` remote；
3. 目标固定为 `gdrive:"Zotero GPT"`；
4. 第一阶段只使用 `rclone copy`；
5. 写 `scripts/sync.ps1`；
6. exporter 成功后才允许执行 rclone；
7. 保存 rclone 运行结果；
8. 网络失败时保持下次可重试。

此阶段不启用远端删除。

完成标准：

- 首次可以上传 5~10 篇测试论文；
- 第二次运行不重复上传未变化的大文件；
- 新增论文能增量进入 Google Drive；
- rclone OAuth token 不进入仓库；
- Google Drive 中的结构与本地镜像一致。

建议版本：`0.4.0`

---

## Phase 5：ChatGPT 实际检索验收

目标：确认这个方案不是“技术上同步成功”，而是真的比 MCP 更省事、更好用。

在 Google Drive 侧仅放测试样本，完成以下真实问题：

1. “找标题包含 XXX 的论文”；
2. “找作者 XXX 的论文”；
3. “找 tag 是 federated learning 的论文”；
4. “找属于某个 Zotero collection 的论文”；
5. “打开这篇论文并总结 Section 3”；
6. “比较这三篇论文的方法”；
7. “按 abstract 找与某研究问题相关的论文”。

重点观察：

- Google Drive / ChatGPT 的索引延迟；
- PDF 全文是否稳定可读；
- `.md` sidecar 是否被正常索引；
- `library.csv` 是否有帮助；
- filename 是否过长；
- collection/tag 的文本格式是否需要优化；
- 同一论文是否出现重复搜索结果。

决策门：

如果这一阶段体验已经满足主要需求，就继续当前架构；只有出现无法解决的 Zotero 结构化检索需求，才重新评估 MCP。

建议版本：`0.5.0`

---

## Phase 6：Windows 无人值守运行

目标：工位机开着时，不需要人工点任何按钮。

实现内容：

1. `scripts/install-task.ps1`；
2. 登录后自动运行一次；
3. 默认每 15 分钟运行一次；
4. 防止同一任务重叠执行；
5. Zotero 未启动时快速失败并记录状态；
6. rclone 网络失败时保留下一轮重试能力；
7. 日志轮转，避免无限增长；
8. 提供 `status` 或简单诊断命令。

需要实测 Windows 锁屏状态下：

- Zotero 是否继续运行；
- Local API 是否可访问；
- Task Scheduler 是否继续触发；
- rclone 是否能继续上传。

完成标准：

连续运行至少一周，无需人工干预完成新增论文同步。

建议版本：`0.6.0`

---

## Phase 7：受保护的删除同步

目标：只有在前面长期稳定后，才让 Zotero 删除真正传播到 Google Drive。

这一阶段不是必须完成的 MVP。

候选设计：

1. Zotero 中删除 item 后先写 tombstone；
2. 保留一个宽限期，例如 7~30 天；
3. 每次运行检查删除数量占比；
4. 删除数量异常时停止；
5. `rclone sync --dry-run` 先输出计划；
6. 通过安全规则才执行实际删除；
7. 可以选择永远保持 Google Drive 为 append/update-only archive。

最终需要人工决定：

- 是否真的需要 Google Drive 与 Zotero 严格一致；
- 还是宁愿让 Drive 多保留一些历史 PDF，换取更高安全性。

建议版本：`0.7.0`

---

## Phase 8：可选增强

只有基础链路已经稳定且确实有需求时再做。

候选功能：

- 更好的主 PDF / supplementary PDF 分类；
- Zotero Notes / annotations 导出；
- BibTeX citation key 写入 sidecar；
- 按 collection/tag 生成虚拟索引页，而不是复制 PDF；
- 一个 `library.jsonl` 供机器检索；
- 单篇论文重新导出命令；
- collection 子集导出；
- HTML 状态页；
- Windows 通知或失败告警；
- 远端备份保留策略。

明确不因为“技术上能做”就加入功能。

---

# 版本路线概览

| 版本 | 目标 |
|---|---|
| `0.1.0` | Zotero Local API → 正确 item / attachment |
| `0.2.0` | 生成人类可读本地镜像 |
| `0.3.0` | 增量导出与安全 manifest |
| `0.4.0` | rclone copy → Google Drive |
| `0.5.0` | ChatGPT 实际检索验收 |
| `0.6.0` | Windows Task Scheduler 无人值守 |
| `0.7.0` | 可选：受保护删除同步 |

当前开发入口：[`../TODO.md`](../TODO.md)。
