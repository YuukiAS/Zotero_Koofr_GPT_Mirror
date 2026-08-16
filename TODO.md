# TODO

这里放当前真正要做的事情。原则是：**只做下一阶段需要的，不提前把项目做复杂。**

完整分阶段规划见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。所有 Zotero、Koofr、Google Drive、ChatGPT 的人工配置说明集中在 [`README.md`](README.md)，不要再拆成多份重复文档。

---

## 当前目标：完成 `0.1.0` 最小 Zotero 导出原型

这一阶段只回答一个问题：

> 能不能稳定地从工位 Windows 上运行中的 Zotero 读取真实论文 metadata，并找到对应的本地 PDF？

暂时不要上传 Google Drive，不要创建定时任务，也不要实现删除同步。

### P0：项目骨架

- [ ] 建立 Python 3.11+ 项目结构。
- [ ] 创建 `pyproject.toml`。
- [ ] 创建 `src/zotero_gpt_mirror/` package。
- [ ] 创建最小 CLI 入口。
- [ ] 创建 `.gitignore`，至少排除：
  - [ ] `.venv/`
  - [ ] `__pycache__/`
  - [ ] `config.toml`
  - [ ] 本地 mirror 目录
  - [ ] 日志
  - [ ] 临时测试 PDF
- [ ] 创建 `config.example.toml`。
- [ ] 配置读取集中在一个地方，不要散落环境变量和多个配置文件。

### P0：Zotero Local API 探测

- [ ] 实现 `zotero status` 或等价诊断命令。
- [ ] 默认探测 `http://127.0.0.1:23119/api/`。
- [ ] Local API 可用时输出明确状态。
- [ ] Zotero 未启动时给出人能理解的错误。
- [ ] Local API 被禁用时给出明确提示。
- [ ] 网络/JSON/协议异常不能被解释成“文献库为空”。
- [ ] 任何探测都必须只读。

### P0：读取文献 item

- [ ] 列出少量 bibliographic items。
- [ ] 读取并规范化：
  - [ ] Zotero item key
  - [ ] item type
  - [ ] title
  - [ ] creators / authors
  - [ ] date / year
  - [ ] DOI
  - [ ] URL
  - [ ] abstract
  - [ ] tags
  - [ ] collection keys
- [ ] 把 collection key 转为可读 collection 名称。
- [ ] 不假设所有 item 都是 journal article。
- [ ] 对缺失字段使用明确空值，不伪造内容。

### P0：读取 PDF attachment

- [ ] 获取每个 item 的 child attachments。
- [ ] 区分 PDF 与非 PDF attachment。
- [ ] 找到 PDF 的本地文件位置。
- [ ] 验证文件真实存在且可读。
- [ ] PDF 尚未下载时标记 `missing_local_attachment`。
- [ ] item 没有 PDF 时标记 `no_pdf_attachment`。
- [ ] 一个 item 有多个 PDF 时全部发现，不能静默只取第一个。
- [ ] 不修改 attachment，不触碰 Koofr。

### P0：测试样本

人工在 Zotero 中挑 5~10 篇，至少覆盖：

- [ ] 普通英文论文 + 单 PDF。
- [ ] 中文或其他 Unicode 标题。
- [ ] 标题含 `:`、`?`、`/` 等 Windows 非法文件名字符。
- [ ] 超长标题。
- [ ] 缺年份。
- [ ] 没有 PDF 的 item。
- [ ] PDF 记录存在但本地尚未下载。
- [ ] 一个 item 有多个 PDF / supplementary attachment。
- [ ] 同一 item 属于多个 collection。
- [ ] 含多个 tags。

### `0.1.0` 验收

- [ ] 对测试样本，metadata 与 Zotero UI 一致。
- [ ] 每个 PDF attachment 能映射到正确 item。
- [ ] 本地不存在的 PDF 不会造成崩溃或误删除。
- [ ] Zotero 不可用时程序失败关闭。
- [ ] 没有任何 Zotero / Koofr 写操作。
- [ ] 添加基础单元测试。
- [ ] README 中实际命令与实现一致。
- [ ] 打 `v0.1.0` tag 前完成一次真实工位机验收。

---

## 下一目标：`0.2.0` 人类可读镜像

`0.1.0` 验收通过后再开始。

### 命名与目录

- [ ] 实现 Windows 文件名清理。
- [ ] Unicode 正规化。
- [ ] 限制文件名长度，保留 item key 后缀。
- [ ] 缺作者时采用合理 fallback。
- [ ] 缺标题时采用合理 fallback。
- [ ] 缺年份放入 `Unknown Year/`。
- [ ] 默认格式：`<FirstAuthor> et al - <Title> [<ItemKey>].pdf`。
- [ ] 设计多个 PDF attachment 的后缀规则。
- [ ] 同名对象不能互相覆盖。

### Sidecar metadata

- [ ] 每个 bibliographic item 生成 `.md`。
- [ ] 包含 title、authors、year、DOI、URL。
- [ ] 包含 Zotero item key。
- [ ] 包含所有 collection 名称。
- [ ] 包含所有 tags。
- [ ] 包含 abstract。
- [ ] 多 attachment 时列出 attachment 信息。
- [ ] 文本格式首先考虑 ChatGPT / Google Drive 的可检索性，而不是视觉花哨。

### Index / Manifest

- [ ] 生成 `_Index/library.csv`。
- [ ] 生成 `_Index/manifest.json`。
- [ ] 生成 `_Status/last-sync.json`。
- [ ] 默认不要把本机绝对源路径暴露到准备上传的公共索引字段。
- [ ] 保留足够的本地诊断信息用于排错。

### `0.2.0` 验收

- [ ] 删除整个测试 mirror 后可从 Zotero 完整重建。
- [ ] 人不打开 Zotero 也能通过目录找到论文。
- [ ] 同一论文只保存一份主镜像，不按 collection 重复复制。
- [ ] `.md` 能表达 collection / tag 关系。
- [ ] 5~10 篇真实样本全部通过。

---

## 后续：`0.3.0` 增量与安全

- [ ] 保存上次成功 manifest。
- [ ] 第二次无变化运行时不重复复制 PDF。
- [ ] metadata 改变时只更新必要文件。
- [ ] 新增论文增量加入。
- [ ] 重命名行为可预测。
- [ ] 删除先记 tombstone，不立即删除远端。
- [ ] 加入 `minimum_expected_items`。
- [ ] 加入相对历史 item 数量异常暴跌检查。
- [ ] fatal error 时禁止进入上传阶段。
- [ ] 防止两个 exporter 实例同时运行。

---

## 后续：`0.4.0` Google Drive

- [ ] 在工位 Windows 安装 rclone。
- [ ] `rclone config` 登录 Google Drive。
- [ ] remote 名称统一使用 `gdrive`，除非实际环境已有冲突。
- [ ] Google Drive 目标目录统一为 `Zotero GPT`。
- [ ] rclone token 只由 rclone 保存，不进入 repo。
- [ ] 创建 `scripts/sync.ps1`。
- [ ] exporter 成功后才运行 rclone。
- [ ] 第一阶段使用 `rclone copy`。
- [ ] 网络失败时下一次运行可以自然重试。
- [ ] 记录上传成功/失败状态。
- [ ] 实测第二次同步不会重新上传所有未变化 PDF。

---

## 后续：`0.5.0` ChatGPT 验收

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
- [ ] 判断 `library.csv` 是否真正有用；无用则不要为了形式保留。

### MCP 决策门

只有下面情况真实出现，才重新评估 Zotero MCP：

- [ ] Google Drive 无法稳定读取 PDF；
- [ ] tag / collection 通过 sidecar 无法满足检索；
- [ ] 必须直接读取 Zotero annotation / note；
- [ ] 必须获取/操作 BibTeX citation key；
- [ ] 必须执行 Zotero 写操作。

否则继续保持当前简单架构。

---

## 后续：`0.6.0` Windows 自动运行

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

## 暂不做

除非前面阶段证明有必要，否则不要提前实现：

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
- [ ] Google Drive → Zotero 回写。

这些不是“以后一定要做”，只是当前明确不需要。

---

## 实现过程中需要人工决定的少数问题

Codex 不应自行拍板以下产品语义；遇到时应停下来询问：

- [ ] 多个 PDF attachment 时，哪个算主 PDF？
- [ ] supplementary material 是否也上传 Google Drive？
- [ ] Zotero note / annotation 是否需要导出？
- [ ] Google Drive 最终是否允许传播删除？
- [ ] 如果允许删除，宽限期多长？
- [ ] `library.csv` 是否保留 abstract 全文，还是只保留检索字段？
- [ ] 文件名最大长度采用多少字符最合适？

其他工程细节在不改变上述语义的前提下可以直接实现。
