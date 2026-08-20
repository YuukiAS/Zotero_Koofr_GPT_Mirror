# Zotero Koofr GPT Mirror

把 Windows Zotero 中的论文 metadata 和本地 PDF，整理成 WSL 里的 **人能看懂、ChatGPT 以后也容易检索** 的只读镜像。

当前架构固定为：

```text
Windows:
Zotero Desktop + Koofr WebDAV

WSL:
Python exporter + ~/ZoteroGPTMirror + rclone
```

本项目不会直接访问 Koofr，不读取 Koofr 密码，不修改 Zotero WebDAV 设置，也不直接读取 `zotero.sqlite`。Zotero 负责把 PDF 下载到 Windows；WSL exporter 通过 Zotero Local API 找到附件，再通过 Windows/WSL 文件互操作只读复制 PDF。

当前版本：`0.2.0`

已通过 Windows interop transport 真实读取 Windows Zotero Local API，并导出到 WSL `~/ZoteroGPTMirror`。当前机器上 direct WSL localhost 不通，因此实际使用的是 Windows interop bridge。

---

## 当前能做什么

- `fixture` source：没有 Zotero 时仍可完整测试镜像生成。
- `zotero-local` source：读取 Zotero Local API v3，解析 bibliographic items、collections、tags、creators、child attachments 和 attachment file URL。
- transport：优先 direct WSL localhost；失败时可用 Windows interop `cmd.exe /c curl.exe` 作为桥。
- path bridge：把 Zotero 返回的 `file:///C:/...` URL 解码成 Windows path，再用 `wslpath` 转为 WSL path。
- mirror：导出 PDF、同名 `.md` sidecar、`_Index/library.csv`、`_Index/manifest.json`。
- 增量：新增、PDF 变化、metadata 变化、skip、stale、缺失输出恢复。
- scan/validate：真实导出前先统计 library 状态，不需要马上复制全部 PDF。
- multi-PDF：一个 bibliographic item 可以包含任意数量 PDF attachment；metadata/index 中仍只算一篇文献。

---

## WSL 快速测试 fixture

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python -m zotero_gpt_mirror validate --source fixture --output-dir ~/ZoteroGPTMirror
python -m zotero_gpt_mirror export --source fixture --output-dir ~/ZoteroGPTMirror
```

第二次运行应主要显示 `skip`：

```bash
python -m zotero_gpt_mirror export --source fixture --output-dir ~/ZoteroGPTMirror
```

dry-run 不写文件：

```bash
python -m zotero_gpt_mirror export --source fixture --output-dir ~/ZoteroGPTMirror --dry-run
```

---

## 真实 Zotero scan

先确认 WSL 环境：

```bash
which wslpath
curl -sS http://127.0.0.1:23119/api/
curl.exe --version
powershell.exe -NoProfile -Command '$PSVersionTable.PSVersion'
```

如果 direct localhost 可用：

```bash
python -m zotero_gpt_mirror validate \
  --source zotero-local \
  --zotero-transport direct \
  --output-dir ~/ZoteroGPTMirror
```

如果 direct localhost 不通，但 Windows `cmd.exe /c curl.exe` 可用：

```bash
python -m zotero_gpt_mirror validate \
  --source zotero-local \
  --zotero-transport windows-interop \
  --output-dir ~/ZoteroGPTMirror
```

默认 `auto` 会先试 direct，再按 EchoSelect 同类方式尝试 Windows interop：

```bash
python -m zotero_gpt_mirror validate --source zotero-local --output-dir ~/ZoteroGPTMirror
```

validate 会输出：

```text
Bibliographic items: ...
Items with one PDF: ...
Items with multiple PDFs: ...
PDF attachments exportable: ...
No PDF attachment: ...
Missing local PDF attachments: ...
Ambiguous primary items: ...
Exact duplicate PDFs suppressed: ...
Collections: ...
Tags: ...
```

如果 WSL shell 的 `WSL_INTEROP` 为空，程序会尝试从 `/run/WSL/*_interop` 自动选择可用 socket，再按 EchoSelect 同类方式调用 `cmd.exe /d /c curl.exe`。

如果 Zotero 返回 `403`，请在 Zotero 设置中启用：

```text
Allow other applications on this computer to communicate with Zotero
```

---

## 真实导出

scan 数量合理后再导出：

```bash
python -m zotero_gpt_mirror export \
  --source zotero-local \
  --output-dir ~/ZoteroGPTMirror
```

输出结构：

```text
~/ZoteroGPTMirror/
├─ Papers/
│  ├─ 2026/
│  └─ Unknown-Year/
└─ _Index/
   ├─ library.csv
   └─ manifest.json
```

Windows 里查看 WSL mirror 时，可以用：

```text
\\wsl.localhost\<distro>\home\<user>\ZoteroGPTMirror
```

---

## Metadata sidecar

每篇 bibliographic item 会生成一个 item-level `.md`，所有 PDF attachment 都列在同一份 metadata 里：

```markdown
# Federated Bayesian Learning

Authors: Alice Smith; Bob Wang
Year: 2026
DOI: 10.xxxx/xxxx
URL: https://example.test/paper
Zotero Item Key: AB12CD34

## Collections

- Research / Federated Learning

## Tags

- Bayesian
- federated learning

## Abstract

...

## PDF Attachments

- Primary
  - Title: Full Text PDF
  - File: `Smith et al - Paper [AB12CD34].pdf`
  - Zotero Attachment Key: AAAA1111

- Supplement
  - Title: Supplement A
  - File: `Smith et al - Paper [AB12CD34] -- Supplement A [BBBB2222].pdf`
  - Zotero Attachment Key: BBBB2222
```

缺失字段会自然省略或标记 `Unknown`，不会输出 `null` / `None`。

---

## 增量与安全

- 原始 Windows Zotero PDF 永远只读，只复制到 WSL mirror。
- 不自动删除 mirror 中的旧输出；消失的 item 只在 manifest 中标记 `stale`。
- PDF 未下载时标记 `missing_local_attachment`，不访问 Koofr。
- item 没有 PDF 时标记 `no_pdf_attachment`。
- 多个 PDF attachment 会全部导出已在本地可用且非重复的 PDF；无法高置信度确定 primary 时记录 `ambiguous`，但不阻塞导出。
- 拒绝危险输出目录，例如 filesystem root、`C:\`、`C:\Users`、项目源码目录。
- source scan 失败时保留旧 manifest，不写“空库成功”。
- 本地 API 请求不使用 Zotero Web API key，也不访问 `api.zotero.org`。

---

## 配置

仓库提供 `config.example.toml`：

```toml
[mirror]
output_dir = "~/ZoteroGPTMirror"

[export]
source = "fixture"
copy_pdf = true
write_metadata = true
write_index = true

[zotero]
local_api = "http://127.0.0.1:23119/api/"
transport = "auto"
```

真实本地配置文件命名为 `config.toml`，不要提交。当前版本不需要 Google token、Koofr password 或 Zotero API key。

---

## 暂不做

当前版本明确不做：

- Google Drive API；
- rclone remote 配置或上传；
- Windows Task Scheduler；
- Koofr API 或 WebDAV client；
- Zotero MCP；
- Tunnel / cloudflared；
- Docker；
- database；
- vector search；
- PDF OCR 或全文提取；
- Zotero 写操作。

下一阶段只应增加 WSL rclone copy：

```text
rclone copy ~/ZoteroGPTMirror gdrive:"Zotero GPT"
```

开发顺序见 [`docs/ROADMAP.md`](docs/ROADMAP.md)，当前具体任务见 [`TODO.md`](TODO.md)。
