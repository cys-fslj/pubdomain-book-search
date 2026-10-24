# 公版书元数据搜索 MVP

FastAPI + SQLite 的公版书元数据检索服务。只存**书名、作者、来源名称、来源 URL** 四个字段，不存任何正文，不做榜单、推荐、站内阅读、书源导入或正文缓存。代码中不内置任何非公版站点的解析规则。

## 数据源

| 来源 | 取数方式 | 卡片跳转目标 |
|---|---|---|
| luoxuhai/chinese-novel | 仅读取仓库内各书目的 `info.json`（书名 `name`、作者 `author.name`） | 该书在 GitHub 仓库中的目录页 |
| Gutendex API | `https://gutendex.com/books?copyright=false`（固定只取美国公版书），分页全量 | 该书在 Project Gutenberg 的页面 `https://www.gutenberg.org/ebooks/{id}` |

chinese-novel 的 `info.json` 路径通过 GitHub Trees API 发现，内容依次尝试 fastly/gcore/cdn 三个 jsDelivr CDN 节点、最后回退 raw.githubusercontent（均为同一仓库的文件，不改变数据源）。

## 目录结构

```
app.py             FastAPI 服务（/api/search、首页）
db.py              SQLite 初始化、写入、统计
ingest.py          采集脚本（两个来源，按 source_url 去重 upsert）
static/index.html  前端：搜索框 + 结果卡片
requirements.txt
books.db           采集生成的 SQLite 数据库（运行时产生）
```

## 运行

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python ingest.py          # 全量采集（Gutendex 约 7 万条，需几分钟）
.venv\Scripts\python ingest.py --max-pages 10   # 仅采集前 10 页（320 条），快速试跑
.venv\Scripts\python ingest.py --skip-gutendex  # 仅采集 chinese-novel
.venv\Scripts\python app.py             # 打开 http://127.0.0.1:8000
```

`ingest.py` 可重复运行，重复采集按来源 URL 去重更新，不会产生重复记录。

## API

```
GET /api/search?q=红楼梦&limit=50
```

- `q`：书名或作者子串（必填，1–100 字符）
- `limit`：返回条数上限（默认 50，最大 200）
- 排序：书名精确命中 → 书名前缀命中 → 其余，再按书名排序
- 响应：`{"query": ..., "total": ..., "results": [{title, author, source_name, source_url}]}`

## 说明与限制

- **字段**：仅 `title / author / source_name / source_url`，SQLite 索引覆盖书名与作者检索。
- **前端**：仅搜索结果卡片，卡片显示来源名称，点击以新标签页标准跳转至来源站点。
- **Gutendex 连通性**：`gutendex.com` 在某些网络环境（如部分国内网络）不可达。此时 `ingest.py` 会跳过该源并明确报错（退出码 1），chinese-novel 部分照常入库；换网络环境后重跑 `ingest.py` 即可补齐。
- **正文**：所有流程均不读取、不存储书籍正文。
