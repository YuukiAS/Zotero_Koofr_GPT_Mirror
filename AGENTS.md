# AGENTS.md

本仓库当前主要用途已经从“继续开发功能”转为“稳定维护一条手动更新链路”。除非用户明确要求开发新功能，否则不要主动扩展范围。

## 当前固定架构

```text
Windows
└─ Zotero Desktop + Koofr WebDAV

WSL
├─ ~/code/Zotero_Koofr_GPT_Mirror
├─ ~/ZoteroGPTMirror
└─ rclone -> gdrive:Zotero
```

关键边界：

- Zotero 和 Koofr 保持在 Windows，不迁移到 WSL。
- repo、Python exporter、mirror、rclone 保持在 WSL。
- 本项目不读取 Koofr 密码，不直接访问 Koofr WebDAV，不读 `zotero.sqlite`。
- Google Drive 只做单向发布，继续使用 `rclone copy`，不要改成 `rclone sync`，不要自动删除远端文件。
- `_Index/manifest.json` 只留在本地，不上传 Google Drive。

## 用户说“更新 Zotero / 同步论文 / 把新论文传上去”时

这类请求默认是一次**日常手动同步任务**，不是开发任务。除非同步暴露真实 bug，否则不要改代码、不要升级版本、不要改 README/TODO/ROADMAP，也不要产生 Git commit。

优先在当前 WSL repo 中运行现有同步入口：

```bash
python -m zotero_gpt_mirror sync \
  --source zotero-local \
  --output-dir ~/ZoteroGPTMirror
```

如果项目已有可用虚拟环境，优先使用该环境中的 Python，不要重复创建环境或重新安装依赖。

同步顺序保持现有语义：

1. 从 Windows Zotero Local API 读取真实 library；
2. 更新 `~/ZoteroGPTMirror`；
3. exporter 成功后才执行 `rclone copy`；
4. 发布到 `gdrive:Zotero`；
5. 网络或 Zotero 暂时不可用时，本次失败即可，不要绕过安全边界；下一次可以自然重试。

## 必须向用户报告“新增了几篇论文”

“论文数”按 **bibliographic item** 计算，而不是按上传文件数计算。

例如一篇新论文包含：

- 1 个 item-level `.md`
- 1 个主 PDF
- 2 个 supplement PDF

仍然只能报告为：

> 新增 1 篇论文，新增 3 个 PDF attachment。

不能把 4 个上传文件说成 4 篇论文。

每次日常同步结束，至少区分并报告：

- 新增 bibliographic items：多少篇；
- 新增 PDF attachments：多少个；
- 已有论文 metadata/PDF 被更新：多少篇（如有）；
- `missing_local_attachment`：多少个（如有）；
- Google Drive 实际传输：多少个文件、多少数据；
- 如果没有新论文，明确说“本次新增论文 0 篇”。

如果当前 CLI 已直接给出 item-level `add/update/skip` 统计，优先使用这些结果。若输出不足以可靠区分“新论文”和“新文件”，应比较同步前后的 item key 集合（例如本地 `_Index/library.csv` / manifest 中的 bibliographic item identity），不要用 rclone 的 transferred file count 代替论文数。

如用户需要，可额外列出本次新增论文的：

- 标题；
- 年份；
- Zotero item key；
- PDF attachment 数量。

默认不要把全部 900+ 条 skip 项打印出来。

## 多 PDF 语义

一个 Zotero bibliographic item 可以对应任意数量 PDF attachment。

- 主文 + Supplement A + Supplement B 仍是一篇论文；
- supplement、appendix、supporting information 等不单独计为新论文；
- 无法高置信度确定 primary 时维持现有 `ambiguous_primary` 语义，不要静默猜测；
- 多 PDF 本身不是错误。

## Git 行为

日常“更新 Zotero”默认只运行同步，不修改 repo，因此：

- 不需要 commit；
- 不需要 push；
- 不要为了留下“同步记录”修改版本号或文档。

只有确实修复代码、测试或文档时才进入正常 Git 工作流。修改前先检查 working tree，避免覆盖用户已有改动。

## 异常处理

如果 Zotero Local API 不可用：

- 先确认 Windows Zotero 是否正在运行；
- 使用当前已经验证的 Windows interop transport；
- 不要回退到直接访问 Koofr。

如果有 `missing_local_attachment`：

- 说明哪些 bibliographic item 的 PDF 尚未下载到 Windows 本地；
- 不要把这些 item 误报成已成功上传 PDF；
- 不要因此删除 Google Drive 上已有内容。

如果 rclone 失败：

- 保留本地 mirror；
- 明确报告 Google Drive 本次未完整更新；
- 不做远端删除或其他补偿性破坏操作。

## 当前不主动做

除非用户明确重新开启这些目标，否则不要主动实现：

- 自动定时更新；
- Windows Task Scheduler；
- `rclone sync` / 远端删除；
- Zotero MCP；
- Koofr API/WebDAV client；
- Google Drive API；
- OCR / vector database / 全文索引服务；
- 双向同步或 Zotero 写操作。
