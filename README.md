# Zotero Koofr GPT Mirror

把 **Zotero 里的论文 PDF 自动整理成正常人能看懂的目录，定期同步到 Google Drive，再让 ChatGPT 直接检索和阅读**。

这个项目不是另一个 Zotero，也不会替换 Koofr。它只做一件事：在现有 Zotero + Koofr 工作流之外，生成一份专门给人和 AI 使用的“只读镜像”。

## 为什么要做这个项目

当前文献工作流是：

```text
Zotero
  ├─ 文献元数据：由 Zotero 自己同步
  └─ PDF 附件：通过 Koofr WebDAV 同步
```

这套方案对 Zotero 本身很好，但不适合直接交给 ChatGPT：

- Koofr WebDAV 中保存的是 Zotero 自己的同步结构，不是一个按论文题目整理好的 PDF 文件夹；
- Zotero 本地 `storage` 目录虽然有正常 PDF，但目录名通常是随机的 attachment key；
- 直接把 `storage` 整个复制到 Google Drive，人看起来很乱，ChatGPT 搜索时也缺少 collection、tag、DOI 等上下文；
- 为了“让 GPT 读论文”单独维护一个公网 MCP、Tunnel 和认证服务，成本偏高。

因此，本项目采用更简单的思路：**让工位电脑上的 Zotero 负责把 Koofr 中的附件正常下载回来，本项目只读取 Zotero 已经准备好的本地数据，重新整理后镜像到 Google Drive。**

## 最终效果

日常使用时，理想流程是：

```text
1. 在任意设备上把论文加入 Zotero
                ↓
2. Zotero 按原来的方式同步元数据和 Koofr PDF
                ↓
3. 工位 Windows 上的 Zotero 自动同步并下载附件
                ↓
4. 本项目定期读取 Zotero Local API
                ↓
5. 生成可读 PDF + metadata.md + 全库索引
                ↓
6. rclone 增量上传到 Google Drive
                ↓
7. ChatGPT 的 Google Drive 连接器索引这些文件
                ↓
8. 可以直接问：
   “找我 Zotero 里关于 federated learning 的论文”
   “读一下这篇 PDF 的 Section 3”
   “比较这三篇论文的方法”
```

正常使用后，不需要手工上传 PDF，也不需要每次启动一个 MCP。

---

# 设计原则

## 1. Zotero 永远是唯一事实来源

本项目只读 Zotero，不反向修改 Zotero，也不直接修改 Koofr。

如果标题、作者、标签、collection 或附件发生变化，下一次镜像时重新从 Zotero 获取。

## 2. Koofr 继续只负责 Zotero 的附件同步

项目不直接登录 Koofr，也不保存 Koofr 用户名或密码。

Koofr 的职责仍然是：

```text
Zotero Desktop ↔ Koofr WebDAV ↔ 其他 Zotero 设备
```

只要工位机 Zotero 已经把 PDF 下载到本地，本项目就不需要理解 Koofr 内部的 `.zip` / `.prop` 同步格式。

## 3. 不直接读取 `zotero.sqlite`

优先使用 Zotero 官方 Local API 获取：

- 论文题目；
- 作者；
- 年份；
- DOI / URL；
- abstract；
- tags；
- collections；
- item key；
- PDF attachment 与本地文件路径。

这样尽量避免依赖 Zotero 内部数据库结构。

## 4. Google Drive 中的目录首先要“人能看懂”

不会把 Zotero 的随机 storage key 当作目录结构直接上传。

建议最终目录：

```text
Zotero GPT/
├─ Papers/
│  ├─ 2026/
│  │  ├─ Smith et al - Federated Bayesian Learning [A8K3F2P1].pdf
│  │  ├─ Smith et al - Federated Bayesian Learning [A8K3F2P1].md
│  │  ├─ Wang et al - Heavy-Tailed Sampling [R92KT5D3].pdf
│  │  └─ Wang et al - Heavy-Tailed Sampling [R92KT5D3].md
│  ├─ 2025/
│  └─ Unknown Year/
│
├─ _Index/
│  ├─ library.csv
│  └─ manifest.json
│
└─ _Status/
   └─ last-sync.json
```

PDF 文件名中的 Zotero item key 用于避免同名论文碰撞，并提供稳定标识；人平时仍然主要看到作者、标题和年份。

## 5. 不按 Zotero Collection 复制多份 PDF

同一篇论文可能同时属于多个 collection，例如：

```text
Federated Learning
Cardiac Imaging
Bayesian Computation
```

如果按 collection 建真实目录，就会在 Google Drive 出现三份相同 PDF，并让 ChatGPT 搜索出重复结果。

因此每个 PDF 原则上只保存一份，collection 和 tag 写入旁边的 metadata 文件。

一个 sidecar 文件大致如下：

```markdown
# Federated Bayesian Learning

- Authors: Alice Smith; Bob Wang
- Year: 2026
- DOI: 10.xxxx/xxxx
- Zotero Item Key: A8K3F2P1
- Collections: Federated Learning; Cardiac Imaging
- Tags: federated learning; Bayesian; CMR

## Abstract

...
```

这样既方便人查看，也能让 ChatGPT 在不解析 Zotero 数据库的情况下检索 collection、tag、DOI 和 abstract。

---

# 整体架构

```text
                         ┌──────────────────────┐
                         │      Zotero Cloud    │
                         │      metadata        │
                         └──────────┬───────────┘
                                    │
                                    │ Zotero 自己同步
                                    │
┌──────────────────┐      ┌────────▼─────────┐
│   Koofr WebDAV   │◀────▶│ Zotero Desktop   │
│   PDF attachments│      │ 工位 Windows     │
└──────────────────┘      └────────┬─────────┘
                                    │
                                    │ Zotero Local API
                                    ▼
                           ┌──────────────────┐
                           │ exporter.py      │
                           │ 只读整理镜像      │
                           └────────┬─────────┘
                                    │
                                    ▼
                           C:\ZoteroGPTMirror
                                    │
                                    │ rclone
                                    ▼
                           ┌──────────────────┐
                           │   Google Drive   │
                           │   Zotero GPT/    │
                           └────────┬─────────┘
                                    │
                                    │ Google Drive connection / sync
                                    ▼
                           ┌──────────────────┐
                           │     ChatGPT      │
                           └──────────────────┘
```

---

# 一次性配置：所有需要手工设置的东西都在这里

项目尽量不把配置拆散到多个文档。以后真正实现时，运行参数也应尽量集中到一个 `config.toml` 中；账号凭据则继续由对应软件自己保存，不写进仓库。

## A. Zotero

### A1. Koofr WebDAV 保持现状

如果 Zotero 已经通过 Koofr 正常同步 PDF，**这里不需要改任何东西**。

本项目不会读取：

- Koofr 主密码；
- Koofr application password；
- WebDAV URL；
- WebDAV 中的 Zotero 文件。

这些仍然只存在 Zotero 自己的同步设置中。

### A2. 确保工位机自动下载 PDF

工位 Windows 上的 Zotero 应设置为同步附件并把需要的 PDF 下载到本地。

项目只处理已经存在于本机的附件。如果某篇论文在 Zotero 里有记录、但 PDF 尚未下载，本次运行应记录为 `missing_local_attachment`，而不是把它当作真正删除。

### A3. 开启 Zotero Local API

Zotero 需要允许本机其他程序通过 Local API 读取数据。

默认接口通常位于：

```text
http://127.0.0.1:23119/api/
```

项目启动时必须先检查 Local API 是否可用。如果不可用，应直接停止本轮导出，不允许继续执行可能造成删除的同步。

### A4. 不需要 Zotero API Key

第一阶段直接读取本机 Zotero Local API，因此不需要额外创建 Zotero Web API key。

---

## B. 本地镜像

默认建议：

```text
C:\ZoteroGPTMirror
```

这个目录是**生成物**，不是人工维护目录。

不要手工往里面放论文，也不要把它提交到 Git。

预计以后统一配置文件：

```toml
[zotero]
local_api = "http://127.0.0.1:23119/api"

[mirror]
root = "C:\\ZoteroGPTMirror"
organize_by = "year"
write_metadata_markdown = true
write_library_csv = true

[google_drive]
rclone_remote = "gdrive"
remote_path = "Zotero GPT"

[safety]
minimum_expected_items = 100
allow_remote_delete = false
```

上面的数值只是示例。第一次部署时应根据实际文献库数量设置安全阈值。

---

## C. Python

项目计划使用 Python 3.11+。

Python 只负责：

1. 调 Zotero Local API；
2. 建立 item → attachment 映射；
3. 规范化 Windows 文件名；
4. 把本地 PDF 复制到镜像目录；
5. 写 `.md` sidecar；
6. 写 `library.csv` 与 `manifest.json`；
7. 输出本轮状态。

Python **不负责 Google OAuth，也不直接调用 Google Drive API**。

---

## D. Google Drive / rclone

Google Drive 上传由 `rclone` 负责。

第一次只需要：

```powershell
rclone config
```

创建一个 Google Drive remote，例如：

```text
gdrive:
```

目标目录统一为：

```text
gdrive:"Zotero GPT"
```

rclone 自己保存 Google OAuth token。这个 token 不应复制进本仓库，也不应写进 `config.toml`。

### 第一阶段为什么默认用 `copy`

最开始使用：

```powershell
rclone copy "C:\ZoteroGPTMirror" "gdrive:Zotero GPT"
```

`copy` 只新增或更新，不会因为本地异常而删除 Google Drive 中已经存在的文件。

等完整镜像经过一段时间验证后，才考虑切换为：

```powershell
rclone sync "C:\ZoteroGPTMirror" "gdrive:Zotero GPT"
```

正式启用 `sync` 前必须具备完整的安全检查，见后文。

---

## E. ChatGPT

Google Drive 中出现 `Zotero GPT/` 后，在 ChatGPT 中连接自己的 Google Drive，并开启当前账号可用的同步/索引能力。

目标是让 ChatGPT 能够直接检索：

- PDF 文件名；
- PDF 全文；
- metadata `.md`；
- `library.csv` 中的标题、作者、tag、collection、DOI 等字段。

第一次完整同步后，应做一组人工验收：

```text
1. 按准确标题找一篇论文
2. 按作者找论文
3. 按 Zotero tag 找论文
4. 按 Zotero collection 找论文
5. 打开并总结指定 PDF
6. 对比两到三篇 PDF
```

如果 ChatGPT 对 `.md` sidecar 的检索效果不理想，再调整 metadata 格式，而不是立刻引入 MCP。

---

## F. Windows 定时任务

长期运行放在工位 Windows，不依赖 WSL。

预计入口脚本：

```text
sync.ps1
```

逻辑：

```text
检查 Zotero Local API
        ↓
运行 exporter
        ↓
验证 manifest 和安全阈值
        ↓
成功才运行 rclone
        ↓
记录状态
```

Windows Task Scheduler 建议：

```text
用户登录时运行一次
+
每 15 分钟运行一次
```

最终间隔可以根据 Zotero 和 ChatGPT 的实际索引延迟调整。没必要追求秒级实时。

---

# 文件命名规则

目标是同时满足三个要求：

1. 人能认出来；
2. Windows / Google Drive 能接受；
3. 同名论文不会碰撞。

建议：

```text
<FirstAuthor> et al - <Title> [<ZoteroItemKey>].pdf
```

例子：

```text
Betancourt et al - A Conceptual Introduction to Hamiltonian Monte Carlo [AB12CD34].pdf
```

需要处理：

- Windows 禁止字符：`< > : " / \\ | ? *`；
- 标题过长；
- 空标题；
- Unicode 正规化；
- 同一 item 多个 PDF；
- supplement / accepted manuscript / publisher version；
- 同作者同标题；
- 年份缺失。

不能只依赖标题作为唯一标识。

---

# `library.csv` 应该包含什么

至少：

```text
item_key
attachment_key
title
authors
year
doi
url
collections
tags
abstract
source_pdf_path
mirror_pdf_path
status
```

`source_pdf_path` 只用于本机排错。如果我们确认 Google Drive / ChatGPT 没必要看到本地绝对路径，上传版本可以去掉该字段，避免泄露本机目录结构。

---

# `manifest.json` 是干什么的

它不是给人搜索论文用的，而是给同步程序判断“这次导出是不是正常”。

应记录类似：

```json
{
  "generated_at": "2026-08-16T17:00:00+08:00",
  "items_seen": 1800,
  "pdfs_exported": 1642,
  "missing_local_attachments": 23,
  "errors": 0
}
```

以后只有满足安全条件，才允许执行带删除能力的远端 `rclone sync`。

---

# 安全策略

这是项目最重要的工程约束之一。

## 默认只读 Zotero

任何版本都不应该：

- 修改 Zotero item；
- 删除 Zotero attachment；
- 修改 Koofr；
- 把 Google Drive 的变化反向同步回 Zotero。

数据方向始终是：

```text
Zotero → Mirror → Google Drive
```

## Zotero 不可用时必须失败关闭

如果 Local API 不通：

```text
STOP
```

不能把“读取失败”解释成“Zotero 当前有 0 篇论文”。

## 第一阶段禁止远端删除

初始版本只允许 `rclone copy`。

## 启用 `rclone sync` 前的条件

至少要求：

- Local API 正常；
- item 数量超过最低阈值；
- 本轮 item 数量相对历史没有异常暴跌；
- manifest 成功写出；
- exporter 没有 fatal error；
- 本地镜像完整生成；
- dry-run 通过。

建议正式删除前先执行：

```powershell
rclone sync ... --dry-run
```

并保留最近一次成功 manifest。

---

# 增量同步策略

第一版可以先正确，再优化速度。

理想状态下，不应该每 15 分钟重新复制全部 PDF。

后续 exporter 会根据稳定标识和文件状态判断：

```text
没变化        → 不重新复制
metadata 变化 → 只更新 .md / index
PDF 变化      → 更新 PDF
新增论文      → 新建 PDF / md
Zotero 删除   → 先记录 tombstone；安全策略允许后再删除镜像
```

Google Drive 上传继续交给 rclone 做增量比较。

---

# 不做什么

当前项目明确不做：

- 自建 Zotero MCP；
- 自建 Koofr MCP；
- 公网 API 服务；
- OpenAI Secure MCP Tunnel；
- Cloudflare Tunnel；
- Zotero 写入；
- Koofr WebDAV 解包器；
- 双向 Google Drive 同步；
- 把 Google Drive 当作 Zotero 的正式附件后端。

如果未来确实需要 Zotero annotation、BibTeX key、collection 操作等结构化能力，再单独评估 MCP，不提前增加复杂度。

---

# 预期仓库结构

当前仓库先冻结设计，随后按阶段实现：

```text
.
├─ README.md
├─ TODO.md
├─ docs/
│  └─ ROADMAP.md
├─ src/
│  └─ zotero_gpt_mirror/
│     ├─ zotero.py
│     ├─ exporter.py
│     ├─ naming.py
│     ├─ manifest.py
│     └─ cli.py
├─ scripts/
│  ├─ sync.ps1
│  └─ install-task.ps1
├─ tests/
├─ config.example.toml
├─ pyproject.toml
└─ .gitignore
```

运行配置尽量集中在 `config.toml`；人工配置 Zotero、Koofr、rclone、Google Drive、ChatGPT 的步骤则集中保留在本 README，避免文档散落。

---

# 第一次上线时的验收标准

第一版不追求功能多，只要真正稳定完成以下闭环：

```text
Zotero 中选 5~10 篇真实论文
        ↓
Local API 正确取得 metadata + attachment
        ↓
生成可读目录、PDF、md、csv、manifest
        ↓
rclone copy 到 Google Drive
        ↓
ChatGPT 能找到并读取这些论文
        ↓
新增 1 篇论文后，无人工干预地进入 Google Drive
```

只有这个闭环通过，才开始做全库、删除同步和更复杂的增量逻辑。

开发顺序见 [`docs/ROADMAP.md`](docs/ROADMAP.md)，当前具体任务见 [`TODO.md`](TODO.md)。
