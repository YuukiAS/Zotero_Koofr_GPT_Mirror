# TODO

这里放当前真正要做的事情。原则是：**只做下一阶段需要的，不提前把项目做复杂。**

完整分阶段规划见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。所有 Zotero、Koofr、Google Drive、ChatGPT 的人工配置说明集中在 [`README.md`](README.md)，不要再拆成多份重复文档。

---

## `0.1.0`：离线镜像生成基础设施

状态：**完成。**

- [x] fixture source。
- [x] 标准化文献模型和 PDF attachment 模型。
- [x] exporter 与 source 解耦。
- [x] Windows-safe 文件名。
- [x] PDF + Markdown sidecar。
- [x] `_Index/library.csv`。
- [x] `_Index/manifest.json`。
- [x] 增量导出。
- [x] dry-run。
- [x] stale 标记。
- [x] source failure 安全保护。
- [x] pytest 自动测试。

---

## `0.2.0`：WSL 读取 Windows Zotero Local API

状态：**完成。已通过 Windows interop transport 真实 scan/export 到 `~/ZoteroGPTMirror`。**

### 已完成

- [x] 保持部署拓扑：Windows Zotero + Koofr，WSL exporter + mirror。
- [x] 默认 mirror 改为 `~/ZoteroGPTMirror`。
- [x] 保留 config 覆盖 output directory。
- [x] 实现 `LocalApiTransport` 边界。
- [x] 实现 `DirectHttpTransport`。
- [x] 实现 `WindowsInteropTransport`，从 WSL 调用 Windows `curl.exe`。
- [x] 实现 `auto` transport：先 direct，再 Windows interop。
- [x] 请求设置 `Zotero-API-Version: 3`。
- [x] 不使用 Zotero Web API key。
- [x] 不访问 `api.zotero.org`。
- [x] 实现真实 `ZoteroLocalSource` parser。
- [x] 只读取 bibliographic top-level items，跳过 attachment/note/annotation。
- [x] 解析 item key、item type、title、authors、year、DOI、URL、abstract、tags、collections。
- [x] 兼容 `firstName + lastName` 和 single-field creator。
- [x] 只把 `creatorType == author` 作为 authors。
- [x] 从复杂 Zotero date 中稳定提取四位年份。
- [x] 建立 collection key -> collection path 缓存。
- [x] 支持嵌套 collection 输出 `Parent / Child`。
- [x] tags 去重、去空、稳定排序、保留 Unicode。
- [x] 获取 child attachments。
- [x] 区分 PDF 与 HTML snapshot / 非 PDF attachment。
- [x] 通过 attachment file URL 获取 Windows 本地 file URL。
- [x] 实现 `file://` URL decode。
- [x] 使用 `wslpath` 转换 Windows path -> WSL path。
- [x] 转换后由 exporter 验证 `Path.exists()` / `Path.is_file()`。
- [x] `validate` 先扫描并输出 summary，不直接复制全部 PDF。
- [x] 区分 `no_pdf_attachment` 与 `missing_local_attachment`。
- [x] 多 PDF attachment 不静默取第一个，报告 attachment 信息。
- [x] 新增匿名 Zotero JSON shape 测试。
- [x] 新增 path conversion、direct transport、Windows interop transport 测试。
- [x] 现有 fixture tests 继续通过。
- [x] 已参考 EchoSelect，确认应通过 Windows `cmd.exe /c ...` 路径做 interop。
- [x] 当前 Codex shell 缺省 `WSL_INTEROP` 为空。
- [x] 已定位可用 interop socket：`/run/WSL/2422275_interop`。
- [x] 通过有效 `WSL_INTEROP` 后，Windows `powershell.exe` 可运行。
- [x] 通过有效 `WSL_INTEROP` 后，Windows `curl.exe` 可运行。
- [x] WSL direct `http://127.0.0.1:23119/api/` 当前不可达，最终采用 Windows interop transport。
- [x] Windows interop 访问 Zotero Local API 成功。
- [x] 真实 scan：989 bibliographic items，953 one-PDF items，15 multi-PDF items，984 exportable PDF attachments，21 no PDF items，2 missing local PDF attachments，3 ambiguous primary items，106 collections，170 tags。
- [x] 真实 export 到 `~/ZoteroGPTMirror`。
- [x] 真实 mirror：984 PDF、968 item-level Markdown、`library.csv`、`manifest.json`。
- [x] manifest 抽样验证：source path 和 output path 都存在。
- [x] 第二次真实 export：`skip: 968`，没有重复制未变化 PDF。

---

## `0.3.0`：WSL rclone -> Google Drive

状态：**完成。已通过 smoke test、全库 `rclone copy` 和第二次增量同步验证。**

- [x] 在 WSL 使用现有 rclone。
- [x] 确认 `gdrive:` remote 已存在。
- [x] 目标目录统一为 `gdrive:Zotero`。
- [x] rclone token 只由 rclone 保存，不进入 repo。
- [x] exporter 成功后才运行 rclone。
- [x] 第一阶段使用 `rclone copy`，不启用远端删除。
- [x] 默认排除 `_Index/manifest.json`，只发布 `Papers/**` 和 `_Index/library.csv`。
- [x] 网络失败时下一次运行可以自然重试。
- [x] 重新授权当前失效的 `gdrive:` OAuth token。
- [x] 只读确认 Google Drive 根目录唯一 `Zotero` 文件夹。
- [x] dry-run 统计上传计划，确认目标不是 `Zotero/ZoteroGPTMirror`。
- [x] 上传 3 个真实 item 做 smoke test。
- [x] 等待 ChatGPT Google Drive connector 验收 smoke test。
- [x] 全库上传：984 PDF、968 Markdown、1 CSV。
- [x] 实测第二次同步不会重新上传所有未变化 PDF。

---

## 后续：Windows Task Scheduler 启动 WSL

- [ ] 后续设计 `wsl.exe ...` 调用 WSL sync command。
- [ ] 登录时运行一次。
- [ ] 默认每 15 分钟运行一次。
- [ ] 任务禁止重叠。
- [ ] 测试 Windows 锁屏时是否继续运行。
- [ ] 测试 Zotero 锁屏时 Local API 是否继续可用。
- [ ] 测试网络短暂中断后的恢复。
- [ ] 控制日志大小。
- [ ] 连续运行至少一周。

---

## 暂不做

- [ ] Google Drive API。
- [ ] Koofr API / WebDAV 直接读取。
- [ ] Zotero Web API key 模式。
- [ ] Zotero MCP。
- [ ] OpenAI Secure MCP Tunnel。
- [ ] Cloudflare Tunnel。
- [ ] 公网服务。
- [ ] Web UI。
- [ ] 数据库。
- [ ] Docker。
- [ ] WSL 服务。
- [ ] 双向同步。
- [ ] PDF OCR / 全文提取。
- [ ] Vector database。
- [ ] Zotero 写操作。
