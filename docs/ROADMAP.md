# Roadmap

项目长期拓扑保持不变：

```text
Windows Zotero + Koofr
-> WSL exporter
-> ~/ZoteroGPTMirror
-> WSL rclone
-> Google Drive/Zotero
```

本项目不直接访问 Koofr，不读取 `zotero.sqlite`，不做 Zotero 写操作。

---

## Phase 0：设计冻结

状态：**完成**。

- Zotero 是唯一事实来源；
- Koofr 只作为 Zotero WebDAV 附件后端；
- Zotero Desktop 运行在 Windows；
- exporter、mirror、rclone 运行在 WSL；
- 使用 Zotero Local API 获取 metadata 和 attachment；
- 本地生成人类可读 PDF mirror；
- 后续用 WSL rclone 上传 Google Drive；
- 不引入 MCP、Tunnel、Cloudflare、公网服务或数据库。

---

## Phase 1：离线镜像生成基础设施

状态：**完成，版本 `0.1.0`。**

目标：没有 Zotero、没有 Google Drive 时，也能完整开发、测试和验证镜像生成逻辑。

已完成：

1. Python 项目骨架和 CLI；
2. fixture/demo 数据源；
3. 标准化文献模型；
4. source 与 exporter 解耦；
5. Windows-safe 文件命名；
6. PDF + `.md` sidecar；
7. `_Index/library.csv`；
8. `_Index/manifest.json`；
9. 增量导出和 dry-run；
10. 危险输出目录保护；
11. 自动测试覆盖核心语义。

---

## Phase 2：WSL 读取 Windows Zotero Local API

目标版本：`0.2.0`

目标：真实证明 WSL 可以从 Windows Zotero Local API 读取 library，并把 Windows 本地 PDF 复制到 `~/ZoteroGPTMirror`。

状态：**完成。**

已实现并验证：

1. `DirectHttpTransport`：WSL 直接访问 `http://127.0.0.1:23119/api/`；
2. `WindowsInteropTransport`：通过 `cmd.exe /c curl.exe` 调 Windows localhost；
3. `AutoTransport`：先 direct，再 interop；
4. `ZoteroLocalSource`：读取 top-level bibliographic items；
5. creator、year、tag、collection hierarchy 解析；
6. child attachment 扫描；
7. attachment file URL 获取；
8. `file://` URL decode；
9. `wslpath` 转换 Windows path -> WSL path；
10. validate scan summary；
11. missing/no/multiple PDF 分类；
12. 匿名 Zotero JSON fixture 测试。

真实验收结果：

- direct WSL localhost 当前不可达；
- Windows interop transport 可用；
- `validate --source zotero-local` 已读取真实 library；
- `export --source zotero-local --output-dir ~/ZoteroGPTMirror` 已生成 WSL mirror；
- 第二次 export 已验证增量 skip；
- multi-PDF 已作为正式一对多产品语义支持，不再作为错误。

---

## Phase 3：WSL rclone -> Google Drive

状态：**完成，版本 `0.3.0`。**

已增加：

```text
rclone copy ~/ZoteroGPTMirror gdrive:Zotero
```

目标：

1. 使用 WSL 中已有 rclone；
2. 确认 `gdrive:` remote；
3. 上传目标固定为 Google Drive 根目录下已有的 `Zotero` 文件夹，即 `gdrive:Zotero`；
4. exporter 成功后才运行 rclone；
5. 第一阶段只用 `rclone copy`；
6. 不启用远端删除；
7. 默认只上传 `Papers/**` 和 `_Index/library.csv`，不上传 `_Index/manifest.json`；
8. rclone token 不进入 repo；
9. smoke test 通过 ChatGPT Google Drive connector 验收后，继续全库上传和第二次增量验证。

真实验收结果：

- `gdrive:` remote 已可用；
- Google Drive 根目录下唯一 `Zotero` 文件夹已确认；
- smoke test 上传 3 个真实 bibliographic items 和 `_Index/library.csv`；
- ChatGPT Google Drive connector smoke test 已通过；
- 全库发布到 `gdrive:Zotero`：984 PDF、968 Markdown、1 CSV；
- `_Index/manifest.json` 未上传；
- 第二次相同 `rclone copy` 显示没有需要传输的文件。

---

## Phase 4：Windows Task Scheduler 启动 WSL

后续方向：

```text
Windows Task Scheduler
-> wsl.exe ...
-> WSL sync command
-> exporter
-> rclone
```

本阶段不实现。

需要实测：

- Windows 锁屏时 Zotero 是否继续运行；
- Local API 是否继续可访问；
- Task Scheduler 是否继续触发；
- WSL rclone 是否能继续上传；
- 任务是否禁止重叠；
- 日志是否可控。

---

## Phase 5：ChatGPT 检索验收

目标：确认 Google Drive 中的 PDF、`.md` sidecar、`library.csv` 真的能被 ChatGPT 有效检索。

验收问题：

1. 按准确标题找论文；
2. 按作者找论文；
3. 按 tag 找论文；
4. 按 collection 找论文；
5. 按 DOI 找论文；
6. 打开并总结指定 PDF；
7. 比较多篇 PDF。

如果 Google Drive + sidecar 已满足需求，继续保持简单架构；只有出现明确结构化能力缺口，才重新评估 MCP。

---

## 暂不做

- Koofr API / WebDAV client；
- Zotero Web API key；
- Zotero MCP；
- OpenAI Secure MCP Tunnel；
- Cloudflare Tunnel；
- Google Drive API；
- Docker；
- database；
- vector search；
- PDF OCR / 全文提取；
- Zotero 写操作；
- 双向同步；
- 删除同步。
