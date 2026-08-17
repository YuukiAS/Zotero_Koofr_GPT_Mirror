# Roadmap

这个项目按风险从低到高逐步建立链路：

```text
fixture 验证镜像生成
-> 真实 Zotero Local API
-> Google Drive / rclone copy
-> Windows 自动运行
-> ChatGPT 检索验收
-> 最后才评估删除同步和高级能力
```

核心原则是：**先验证“能正确读、能正确整理、GPT 真能用”，再做全自动和删除。**

---

## Phase 0：设计冻结

状态：**完成**。

已经确定：

- Zotero 是唯一事实来源；
- Koofr 继续只作为 Zotero WebDAV 附件后端；
- 工位 Windows 是长期运行节点；
- 不从 Koofr WebDAV 直接抓 `.zip/.prop`；
- 不直接读取 `zotero.sqlite`；
- 优先使用 Zotero Local API 获取 metadata 和 attachment；
- 本地生成一份人类可读的 PDF 镜像；
- 后续使用 rclone 上传 Google Drive；
- ChatGPT 通过 Google Drive 连接/同步能力检索；
- 初始阶段只允许单向复制，不允许远端删除；
- 当前不引入 MCP、Tunnel、Cloudflare 或公网服务。

---

## Phase 1：离线镜像生成基础设施

状态：**完成，版本 `0.1.0`。**

目标：没有 Zotero、没有 Google Drive 时，也能完整开发、测试和验证镜像生成逻辑。

实现内容：

1. Python 项目骨架和 CLI；
2. fixture/demo 数据源；
3. 标准化文献模型；
4. source 与 exporter 解耦；
5. Windows-safe 文件命名；
6. 按年份输出 `Papers/<year>/`；
7. 每篇 PDF 生成同名 `.md` sidecar；
8. 生成 `_Index/library.csv`；
9. 生成 `_Index/manifest.json`；
10. 增量导出和 dry-run；
11. 危险输出目录保护；
12. Zotero Local API adapter 骨架和友好不可用错误；
13. 自动测试覆盖核心语义。

完成标准：

- fixture export 能完整生成镜像；
- 第二次无变化运行能 skip；
- dry-run 不写磁盘；
- 同名论文不覆盖；
- collection/tag 不通过复制 PDF 表达；
- source scan 失败不破坏旧 manifest；
- 真实 Zotero 未安装时不阻塞 fixture 开发。

尚未验证：

- 真实 Zotero Local API 端到端读取；
- Windows PowerShell 实机命令；
- Google Drive / rclone / ChatGPT。

---

## Phase 2：真实 Zotero Local API 集成

建议版本：`0.2.0`

目标：证明可以稳定地从工位 Windows 上运行中的 Zotero 得到“论文记录 -> 正确 PDF”。

实现内容：

1. 检查 Zotero Local API 是否可用；
2. 读取真实 bibliographic items；
3. 获取标题、作者、年份、DOI、URL、abstract、tags、collections；
4. 获取 PDF attachment；
5. 获取并验证本地 PDF 路径；
6. 对未下载附件进行明确标记；
7. 对无 PDF item 明确标记；
8. 遇到多个 PDF attachment 时先停止并确定产品规则；
9. 不修改 Zotero，不触碰 Koofr。

完成标准：

- 5~10 篇真实样本 metadata 与 Zotero UI 一致；
- 每个 PDF attachment 能映射到正确 item；
- 本地不存在的 PDF 不会造成崩溃或误删除；
- Zotero 不可用时程序失败关闭；
- 没有任何 Zotero / Koofr 写操作。

---

## Phase 3：Google Drive / rclone copy

建议版本：`0.3.0`

目标：把已经验证正确的本地镜像可靠地放进 Google Drive。

实现内容：

1. 在工位 Windows 安装 rclone；
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

---

## Phase 4：Windows 无人值守运行

建议版本：`0.4.0`

目标：工位机开着时，不需要人工点任何按钮。

实现内容：

1. `scripts/install-task.ps1`；
2. 登录后自动运行一次；
3. 默认每 15 分钟运行一次；
4. 防止同一任务重叠执行；
5. Zotero 未启动时快速失败并记录状态；
6. rclone 网络失败时保留下一轮重试能力；
7. 日志轮转，避免无限增长；
8. 提供简单状态诊断。

需要实测 Windows 锁屏状态下：

- Zotero 是否继续运行；
- Local API 是否可访问；
- Task Scheduler 是否继续触发；
- rclone 是否能继续上传。

完成标准：

连续运行至少一周，无需人工干预完成新增论文同步。

---

## Phase 5：ChatGPT 实际检索验收

目标：确认这个方案不是“技术上同步成功”，而是真的能被 ChatGPT 使用。

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

---

## Phase 6：受保护的删除同步

这一阶段不是必须完成的 MVP。

只有前面长期稳定后，才评估是否让 Zotero 删除传播到 Google Drive。

候选设计：

1. Zotero 中删除 item 后先写 tombstone；
2. 保留宽限期；
3. 每次运行检查删除数量占比；
4. 删除数量异常时停止；
5. `rclone sync --dry-run` 先输出计划；
6. 通过安全规则才执行实际删除。

最终需要人工决定：

- 是否真的需要 Google Drive 与 Zotero 严格一致；
- 还是宁愿让 Drive 多保留一些历史 PDF，换取更高安全性。
