# Zotero Koofr GPT Mirror

把 Zotero 风格的论文 metadata 和本地 PDF 整理成一份 **人能看懂、ChatGPT 以后也容易检索** 的本地镜像。

这个项目不是另一个 Zotero，也不会替换 Koofr。它只做一件事：从 Zotero 这类事实来源读出论文信息和本地 PDF，生成一份只读镜像，后续再交给 Google Drive / ChatGPT 使用。

当前版本：`0.1.0`

`0.1.0` 已经可以在 **没有安装 Zotero、没有连接 Google Drive** 的电脑上开发、测试和验证。它使用仓库内的 fixture/demo 数据模拟 Zotero item 和 PDF attachment。

尚未完成真实 Zotero library 的端到端验证，也没有接入 Koofr、Google Drive、rclone 或 Windows Task Scheduler。

---

## 当前能做什么

现在可以把 fixture 中的 Zotero 风格输入：

- item key
- title
- authors
- year
- DOI
- abstract
- collections
- tags
- PDF attachment

导出成类似：

```text
ZoteroGPTMirror/
├─ Papers/
│  ├─ 2026/
│  │  ├─ Smith et al - Federated Bayesian Learning [MULTI02].pdf
│  │  └─ Smith et al - Federated Bayesian Learning [MULTI02].md
│  └─ Unknown-Year/
└─ _Index/
   ├─ library.csv
   └─ manifest.json
```

同一篇论文只保存一份 PDF，不按 collection 复制多份。Collection 和 tag 会写进旁边的 `.md` metadata sidecar 和 `_Index/library.csv`。

---

## Windows 快速测试

在 PowerShell 中运行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m zotero_gpt_mirror export --source fixture --output-dir C:\ZoteroGPTMirror
```

第二次运行应该主要显示 skip：

```powershell
python -m zotero_gpt_mirror export --source fixture --output-dir C:\ZoteroGPTMirror
```

dry-run 不会写任何文件：

```powershell
python -m zotero_gpt_mirror export --source fixture --output-dir C:\ZoteroGPTMirror --dry-run
```

也可以使用 console script：

```powershell
zotero-gpt-mirror export --source fixture --output-dir C:\ZoteroGPTMirror
```

---

## 输出内容

每篇 PDF 会生成一个同名 `.md`：

```markdown
# Federated Bayesian Learning

Authors: Alice Smith; Bob Wang; Carla Jones
Year: 2026
DOI: 10.1000/multi
Zotero Item Key: MULTI02

## Collections

- Federated Learning
- Medical Imaging

## Tags

- Bayesian
- federated learning
- likelihood

## Abstract

A fixture abstract for a multi-author paper.
```

`_Index/library.csv` 是给人和简单工具看的全库索引，包含标题、作者、年份、DOI、collections、tags、PDF 相对路径和 metadata 相对路径。

`_Index/manifest.json` 是给程序做增量和安全检查用的状态文件，记录 item key、attachment key、源 PDF 路径、输出相对路径、源文件大小、源文件修改时间和 metadata fingerprint。

---

## 增量与安全

导出器不会每次重复制全部 PDF：

- 新增论文：复制 PDF，写 `.md`、index、manifest。
- PDF 未变化且 metadata 未变化：skip。
- metadata 变化：只更新 `.md`、index、manifest。
- PDF 变化：重新复制 PDF。
- 输出文件被人为删除：自动恢复。
- 输入中某篇论文消失：manifest 标记 `stale`，但不删除旧输出。

安全边界：

- 不修改、移动、重命名或删除原始 PDF。
- 不自动删除镜像中的旧文件。
- 拒绝危险输出目录，例如 `C:\`、`C:\Users`、项目源码目录。
- source scan 失败时保留旧 manifest，不写“空库成功”。
- `config.toml`、本地 mirror、虚拟环境、日志不会提交到 Git。

---

## 配置

仓库提供 `config.example.toml`：

```toml
[mirror]
output_dir = "C:/ZoteroGPTMirror"

[export]
source = "fixture"
copy_pdf = true
write_metadata = true
write_index = true

[zotero]
local_api = "http://127.0.0.1:23119/api/"
```

真实本地配置文件命名为 `config.toml`，不要提交。当前版本不需要 Google token、Koofr password 或 Zotero API key。

---

## Zotero Local API 状态

项目已经保留 `zotero-local` 数据源边界，但 `0.1.0` 不声称真实 Zotero 已经集成完成。

如果 Zotero 没有安装或没有运行：

```powershell
zotero-gpt-mirror export --source zotero-local
```

会得到类似提示：

```text
Zotero Local API is not available at http://127.0.0.1:23119/api/

This is expected if Zotero is not installed or not running.
Use `--source fixture` to test the exporter without Zotero.
```

下一阶段安装 Zotero 后，要做的是：开启 Zotero Local API，读取真实 bibliographic items，解析 collections/tags/attachments，把 Zotero API 返回值转换成本项目的内部模型，并用 5~10 篇真实样本验收。

---

## 不做什么

当前版本明确不做：

- Koofr WebDAV client 或 Koofr API；
- Google Drive API；
- rclone 配置或上传；
- ChatGPT Google Drive connector 配置；
- Zotero MCP；
- OpenAI MCP Tunnel / Cloudflare Tunnel；
- Docker、WSL daemon、Windows Service；
- Windows Task Scheduler；
- Zotero 自动安装或配置修改；
- annotations、citation、BibTeX；
- OCR、PDF text extraction、embedding、vector database。

开发顺序见 [`docs/ROADMAP.md`](docs/ROADMAP.md)，当前具体任务见 [`TODO.md`](TODO.md)。
