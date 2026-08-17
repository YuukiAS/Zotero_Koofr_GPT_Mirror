# TODO

这里放当前真正要做的事情。原则是：**只做下一阶段需要的，不提前把项目做复杂。**

完整分阶段规划见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。所有 Zotero、Koofr、Google Drive、ChatGPT 的人工配置说明集中在 [`README.md`](README.md)，不要再拆成多份重复文档。

---

## `0.1.0`：离线镜像生成基础设施

状态：**已实现，使用 fixture 自动测试验证；尚未使用真实 Zotero library 端到端验证。**

- [x] 建立 Python 3.11+ 项目结构。
- [x] 创建 `pyproject.toml`。
- [x] 创建 `src/zotero_gpt_mirror/` package。
- [x] 创建 CLI：`export`、`export --dry-run`、`validate`。
- [x] 创建 `.gitignore`，排除 `.venv/`、`__pycache__/`、`config.toml`、本地 mirror、日志等。
- [x] 创建 `config.example.toml`。
- [x] 配置读取集中在 `config.toml` / CLI 参数。
- [x] 定义标准化文献模型和 PDF attachment 模型。
- [x] 让 exporter 与 source 解耦。
- [x] 创建 fixture source。
- [x] fixture 覆盖普通单作者、多作者、缺 DOI、缺 abstract、缺年份、多 collections、多 tags、Windows 非法字符、极长标题、Unicode/中文标题、同名/近似同名、多个 attachment 但只有一个 PDF。
- [x] 使用仓库内 dummy PDF，不加入真实版权论文。
- [x] 实现 Windows filename sanitizer。
- [x] 保留 item key 作为稳定身份标识。
- [x] 生成 `Papers/<year>/...pdf`。
- [x] 缺年份放入 `Unknown-Year/`。
- [x] 生成同名 `.md` metadata sidecar。
- [x] 生成 `_Index/library.csv`。
- [x] 生成 `_Index/manifest.json`。
- [x] 实现增量导出：新增、skip、metadata 变化、PDF 变化、输出缺失恢复、stale 标记。
- [x] 实现 dry-run，不写磁盘。
- [x] 拒绝危险 `output_dir`。
- [x] 原始 PDF 只读，只复制。
- [x] source scan 失败时不破坏旧 manifest。
- [x] 保留 `zotero-local` source adapter 骨架和友好不可用错误。
- [x] 添加 pytest 自动测试。
- [x] README / ROADMAP / TODO 与当前实现同步。

### `0.1.0` 未验证

- [ ] 尚未安装 Zotero，因此真实 Zotero Local API 尚未进行端到端验证。
- [ ] 尚未验证真实 Zotero collections/tags/attachments 解析。
- [ ] 尚未在 Windows PowerShell 中实际运行测试命令。
- [ ] 尚未连接 Google Drive。
- [ ] 尚未配置 rclone。
- [ ] 尚未创建 Windows Task Scheduler 定时任务。

---

## 下一目标：`0.2.0` 真实 Zotero Local API 集成与验收

- [ ] 在工位 Windows 安装并运行 Zotero。
- [ ] 确认 Zotero Local API 可访问：`http://127.0.0.1:23119/api/`。
- [ ] 读取真实 bibliographic items。
- [ ] 解析 title、authors、year、DOI、URL、abstract、tags、collections、item key。
- [ ] 获取 child attachments。
- [ ] 区分 PDF 与非 PDF attachment。
- [ ] 获取真实本地 PDF 路径并验证可读。
- [ ] PDF 尚未下载时标记 `missing_local_attachment`。
- [ ] item 没有 PDF 时标记 `no_pdf_attachment`。
- [ ] 一个 item 有多个 PDF 时停止并询问产品规则，不能静默只取第一个。
- [ ] 不修改 Zotero，不触碰 Koofr。
- [ ] 用 5~10 篇真实样本验收 metadata 与 Zotero UI 一致。

---

## 后续：`0.3.0` Google Drive / rclone copy

- [ ] 在工位 Windows 安装 rclone。
- [ ] `rclone config` 登录 Google Drive。
- [ ] remote 名称统一使用 `gdrive`，除非实际环境已有冲突。
- [ ] Google Drive 目标目录统一为 `Zotero GPT`。
- [ ] rclone token 只由 rclone 保存，不进入 repo。
- [ ] 创建 `scripts/sync.ps1`。
- [ ] exporter 成功后才运行 rclone。
- [ ] 第一阶段使用 `rclone copy`，不启用远端删除。
- [ ] 网络失败时下一次运行可以自然重试。
- [ ] 实测第二次同步不会重新上传所有未变化 PDF。

---

## 后续：`0.4.0` Windows 自动运行

- [ ] 创建 `scripts/install-task.ps1`。
- [ ] 登录时运行一次。
- [ ] 默认每 15 分钟运行一次。
- [ ] 任务禁止重叠。
- [ ] 测试 Windows 锁屏时是否继续运行。
- [ ] 测试 Zotero 锁屏时 Local API 是否继续可用。
- [ ] 测试网络短暂中断后的恢复。
- [ ] 控制日志大小。
- [ ] 提供简单状态诊断。
- [ ] 连续运行至少一周。

---

## 后续：ChatGPT 检索验收

- [ ] 在 ChatGPT 连接 Google Drive。
- [ ] 确认 `Zotero GPT/` 可以被当前账号搜索/读取。
- [ ] 精确标题搜索。
- [ ] 作者搜索。
- [ ] tag 搜索。
- [ ] collection 搜索。
- [ ] DOI 搜索。
- [ ] PDF 全文读取。
- [ ] 指定章节总结。
- [ ] 多论文比较。
- [ ] 记录从 Google Drive 上传到 ChatGPT 可检索的大致延迟。
- [ ] 根据实测调整 `.md` sidecar 格式。

### MCP 决策门

只有下面情况真实出现，才重新评估 Zotero MCP：

- [ ] Google Drive 无法稳定读取 PDF；
- [ ] tag / collection 通过 sidecar 无法满足检索；
- [ ] 必须直接读取 Zotero annotation / note；
- [ ] 必须获取/操作 BibTeX citation key；
- [ ] 必须执行 Zotero 写操作。

否则继续保持当前简单架构。

---

## 暂不做

- [ ] `rclone sync` 远端删除。
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
- [ ] Google Drive -> Zotero 回写。
