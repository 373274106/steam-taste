# Steam Taste Lens / Playprint — 交接文档

> 给新对话用：把这份 + `steam-game-advisor-project.md` 一起读，能完整接手项目。
>
> **当前状态**：已上线，端到端可访问。已完成 Phase 4（PPMI + SVD 自训练 tag embedding，生产已用）
> 和 Phase 4+（基于 InfoNCE 训练的 dual encoder + 三路检索消融），并经过 Playprint 品牌重塑
> （retro-arcade × editorial 视觉系统）和 Result 页 3-Act 改版。当前焦点：portfolio writeup + README。
>
> **公开品牌**：Playprint（前端标题、页面文案）。代码库内部仍称 Steam Taste Lens（仓库名、Python 包名）。

---

## 1. 项目一句话

Steam 玩家品味透镜：基于 TF-IDF 标签相似度的多层推荐引擎，提供 Steam 官方不具备的可解释推荐、跨维度相似度查询、和反向消费洞察（Library Regret）。**做 Steam 不愿意做的事**。

详细定位 / 多层架构设计见 [steam-game-advisor-project.md](steam-game-advisor-project.md)。

---

## 2. 关键 URL

| 类型 | URL |
|---|---|
| **前端（生产）** | https://steam-taste.vercel.app |
| **后端（生产）** | https://steam-taste.onrender.com |
| **后端健康检查** | https://steam-taste.onrender.com/api/health |
| **后端 API 文档（Swagger）** | https://steam-taste.onrender.com/docs |
| **GitHub 仓库** | https://github.com/373274106/steam-taste |
| **本地工作目录** | `e:\study\project` |

### 测试入口
- Demo 模式：直接点 https://steam-taste.vercel.app 上的 demo 按钮，不需要登录
- 真用户：贴 SteamID `76561198098881759`（HexQuarter，1095 款游戏的真实测试账号）

---

## 3. 技术栈 / 服务

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 + FastAPI + Uvicorn |
| 算法依赖 | numpy + scipy.sparse + scikit-learn（含 HDBSCAN）|
| Phase 4+ 训练 | PyTorch（**只在离线训练脚本里**，生产 runtime 不依赖 torch）|
| 数据存储 | SQLite (`data/corpus.db`) + sparse npz (`data/tfidf.npz`) + dense npy (`data/tag_embedding.npy` / `game_embedding.npy`) |
| Steam 集成 | Steam Web API + Steam Store API + SteamSpy + Steam OpenID 2.0 |
| 前端 | React 18 + Vite 6 + TypeScript + Tailwind v4 + react-router-dom v6 |
| 前端部署 | Vercel（GitHub 自动 push 部署）|
| 后端部署 | Render free tier（512MB RAM，**15 分钟无访问休眠 + 30s 冷启动**）|

**关键决定**：不用 sentence-transformers / torch / 任何 ML 框架。Phase 0 实验证实 tag-based 比 transformer 嵌入高 30%，stack 简化到 < 200MB 镜像。

---

## 4. 账户 / Secrets / Env

### 本地（`.env` 文件，不进 git）
```
STEAM_API_KEY=xxx  (32 位 hex, 用户自己的 Steam Web API key)
```

### Vercel 环境变量
```
VITE_API_BASE = https://steam-taste.onrender.com
```

### Render 环境变量
```
STEAM_API_KEY = 同 .env
FRONTEND_BASE = https://steam-taste.vercel.app   (无尾斜杠！代码已 normalize 但还是别加)
BACKEND_BASE  = https://steam-taste.onrender.com
```

### Steam API Key 来源
- https://steamcommunity.com/dev/apikey
- ⚠️ **旧 key 曾在对话中泄露 → 已 revoke → 重新生成的新 key 才是生效中**

---

## 5. 项目文件结构

```
e:\study\project\
├── steam-game-advisor-project.md   # 项目设计文档（多层架构详解）
├── HANDOFF.md                       # 本文件
├── .env.example                     # env 模板（实际 .env 不进 git）
├── .gitignore
├── requirements.txt                 # 后端 Python 依赖（Render 用）
├── runtime.txt                      # Python 3.11.10
│
├── backend/                         # FastAPI 后端
│   ├── main.py                      # 13 个 endpoint + CORS + lifespan
│   ├── taste_engine.py              # 核心引擎：TF-IDF + taste vector + recommend
│   ├── regret_detector.py           # HDBSCAN 聚类 + pure/mixed regret 分类
│   ├── steam_client.py              # Steam Web API + SteamID 解析
│   ├── auth.py                      # Steam OpenID 2.0 登录
│   ├── config.py                    # env var 读取 + 自动 strip 尾斜杠
│   ├── cache.py                     # 简易 TTL+LRU 缓存
│   └── demo.py                      # 26 款游戏的 demo 用户库
│
├── frontend/                        # React + Vite + TS
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── vercel.json                  # SPA 路由重写（关键！）
│   ├── index.html
│   └── src/
│       ├── main.tsx                 # 入口 + BrowserRouter
│       ├── App.tsx                  # 路由：/ → Home, /result → Result
│       ├── index.css                # Tailwind + Playprint 主题 CSS 变量（Pixelify/Hanken/Mono 三字体 + amber palette）
│       ├── vite-env.d.ts            # Vite import.meta.env 类型声明
│       ├── lib/
│       │   ├── api.ts               # 后端 API 客户端（fetch wrapper）
│       │   └── types.ts             # 所有 API 响应的 TS 类型
│       ├── pages/
│       │   ├── Home.tsx             # 落地页：OpenID + URL paste + Demo 三档
│       │   └── Result.tsx           # 3-Act shell + 状态管理（Act I/II/III）
│       └── components/
│           ├── Masthead.tsx           # 全局页头（Playprint · ISS. <id> · NEW ENTRY）
│           ├── TasteProfileTab.tsx    # Act I：hero quote + tag affinity + clusters
│           ├── TagRadar.tsx           # Act I 用：自实现 SVG 雷达图（无图表库）
│           ├── RecommendationsTab.tsx # Act II：Discover New + Play What You Own
│           ├── RegretTab.tsx          # Act III：Mixed / Pure / Sleeping 三 sub-tab
│           ├── LoadingState.tsx       # 4 步 staged 进度
│           └── ErrorState.tsx         # 智能错误诊断（私密资料/找不到/网络）
│
├── scripts/                         # 一次性 / 离线脚本
│   ├── phase1_fetch_corpus.py       # 抓 SteamSpy top N 款游戏（默认 5 页 ~5k；当前用 --pages 15 ~14.3k）
│   ├── phase1_build_index.py        # 构建 TF-IDF 矩阵
│   ├── phase1_health_check.py       # 抽样验证 nearest neighbor
│   ├── phase2_test_engine.py        # 离线测试 demo 用户
│   ├── phase2b_test_real_user.py    # 测试真实 SteamID 端到端
│   ├── phase3_test_regret.py        # 测试 regret 检测
│   ├── phase4_build_tag_embedding.py # PPMI + SVD，产出 data/tag_embedding.npy
│   ├── phase4_health_check.py       # tag 同义词 + 邻居人眼判断（生成 meta.json）
│   ├── phase4plus_train.py          # InfoNCE 训练 dual encoder（PyTorch，离线）
│   ├── phase4plus_compare.py        # 三路检索消融：TF-IDF / PPMI / trained
│   ├── build_tag_i18n.py            # 拉 Steam 官方 populartags 两套语言 → data/tag_i18n.json
│   ├── embedding_probe.py           # Phase 0：transformer 嵌入实验
│   ├── embedding_compare.py         # Phase 0：6 种方法对比（验证 tag-based 优势）
│   ├── embedding_diagnose.py        # Phase 0：邻居诊断
│   ├── itad_match_probe.py          # Phase 0 早期探针（已废弃）
│   └── screenshot_*.py              # Playwright 截图脚本（Home / Result 状态图）
│
└── data/                            # 已 commit 进 git (~45 MB 总量)
    ├── corpus.db                    # 14270 款游戏元数据 + tags (29 MB)
    ├── tfidf.npz                    # 14270 × 445 sparse TF-IDF 矩阵
    ├── tag_vocab.json
    ├── appid_order.json
    ├── inverted_index.json
    ├── tag_embedding.npy            # Phase 4：445 × 50 PPMI + SVD
    ├── tag_embedding_meta.json      # 配置 + 同义词探针结果
    ├── tag_i18n.json                # en → zh tag 名字映射（Steam 官方 populartags 翻译）
    ├── game_embedding.npy           # Phase 4+：14270 × 256 trained dual encoder
    ├── game_embedding_meta.json     # 训练超参 + 消融结果（trained -7.9pp vs TF-IDF）
    └── game_embedding_train_log.json
```

---

## 6. Git 历史

```
8eb11ee  Add EN / 中 language toggle with bilingual UI + regret diagnoses
95a8792  Add release_year recency bias + fresh_fit recommendation mode
eb764d4  Vary regret diagnoses: template pool + domain-aware branches
90e5299  Add README and bring HANDOFF + project plan up to current state
246bab9  Fix rec attribution: closed-form decomposition + closest-fit slot
577a476  Refine Result typography + add tag-affinity radar
8560c44  Redesign Act II (Recommendations) + Act III (Library Regret)
e82b234  Redesign Result shell + Act I (Taste) + Loading + Error states
c56c894  Rebrand to Playprint + redesign Home (retro-arcade x editorial)
d7cfe8b  Add Phase 4 self-trained embeddings + three-way retrieval ablation
5a5f50e  Add HANDOFF.md for cross-session continuity
96d3331  Add vercel.json SPA rewrite so deep links (/result) serve index.html
5b530c0  Strip trailing slash from FRONTEND_BASE/BACKEND_BASE env vars
e8b660a  Add vite-env.d.ts for import.meta.env types (Vercel build fix)
1128a7f  Add deploy artifacts for Render (backend) deploy
2a02890  Bundle the 12MB corpus into the repo so deploys don't need to re-fetch.
aa3d4e1  Polish: mobile responsive + smart error states + demo card + fade-in
2b81e64  Polish: staged loading, match % rescale, cluster thumbnails
12b4e72  Initial commit: Steam Taste Lens v0.1
```

- Remote：`origin = https://github.com/373274106/steam-taste.git`
- Branch：`main`（GitHub 默认）
- 每次 `git push` 自动触发 Vercel + Render 重新部署

---

## 7. 已完成（高层）

### Phase 0：算法验证
- 实验对比 6 种 game-similarity 方法
- **tag Jaccard 85% merged hit rate**（在 180 款密度簇验证集）
- transformer 嵌入只有 55%——描述文本污染信号
- 决策：tag-based 主路径，砍掉 transformer 依赖

### Phase 1：Corpus + TF-IDF 基线
- 抓 SteamSpy top 5000 款元数据 + 标签（初始版本；现已扩到 14270 款，见 Phase 4++ §7）
- 构建 tag 倒排索引 + sparse TF-IDF 矩阵
- 健康检查：随机 10 款游戏的邻居人眼判断合理

### Phase 2：User Taste Vector
- playtime-weighted taste vector（tag 空间）
- recommend(best_fit / hidden_gem / stretch) 三种模式
- **Play What You Own**：推荐已拥有但没玩的游戏（项目核心差异点）
- 质量过滤（min reviews 50 + min positive ratio 65%）+ 软质量加成

### Phase 3：HDBSCAN Library Regret
- 用户库聚类（cosine on L2-normalized = euclidean）
- **Pure regret vs Mixed regret 分类**：
  - Pure：簇里全是低 playtime → "类型不适合你"
  - Mixed：簇里有高 playtime 真爱 + 一堆 0h → "找到真爱了别再囤"
- 严重度排序（count / median_hours），默认只显示 Top 10
- Sleeping games 列表（< 30min playtime）
- Software 类型自动过滤（type=game 不够，要按 dominant tags 兜底）

### Phase 4：自训练 Tag Co-occurrence Embedding（PPMI + SVD）
- 从 corpus 构建 tag-tag 共现矩阵 → PPMI 归一化 → numpy SVD 降到 50 维
- 验证：`Rogue-like` ↔ `Rogue-lite` ≈ 0.99（同义词自动合并）；`Deckbuilding` ↔ `Card Battler` ≈ 0.98
- 生产已用：`/api/game/similar?method=ppmi`，比 TF-IDF 基线 **+3.4pp merged hit rate**（83.2 → 86.6，**15k 语料**）
- 数据落地：`data/tag_embedding.npy` (445×50) + meta.json
- 关键文件：`scripts/phase4_build_tag_embedding.py`，运行时入口 `TasteEngine.tag_neighbors()` / `.game_dense_vec()`

### Phase 4+：Trained Dual-Encoder（InfoNCE）+ 三路检索消融
- PyTorch 训练 MLP encoder（input_dim → 512 → 256，dropout 0.2 + L2 norm），InfoNCE in-batch negatives，cosine LR + early stop（监控 probe_merged）
- 正样本：共享 ≥2 个 high-IDF tag 的游戏对（**14k 语料下 91 万对**，5k 时 10.6 万对）；Phase 0 probe 集 75 款 held out 评估（84 个相关 appid 全部从训练对中剔除）
- 输入：默认 449 维 = 445 维 TF-IDF + 4 维 aux features（`review_ratio`, `review_count_log`, `owners_log`, `year_norm`，z-score 归一）。这 4 维信号 **baseline 拿不到**——是 Path A 实验留下的能力。`--no-aux` 旗标可关掉做对照
- **消融结果（15k 语料 + aux features，**当前生产embedding**）**：

  | 方法 | Merged hit-rate | vs TF-IDF |
  |---|---|---|
  | TF-IDF baseline | 83.2% | — |
  | PPMI+SVD (Phase 4) | **86.6%** | **+3.4pp** |
  | Trained dual encoder (aux on) | 75.5% | **-7.7pp** |
  | Trained dual encoder (aux off) | 75.3% | -7.9pp |

- **两个连续 ablation 都没翻盘**：
  - 5k → 15k 数据扩 3×：trained encoder 从 -2.1pp 退到 -7.9pp（更多 pair 引入更多弱样本）
  - 加 review/year/owners 辅助特征：merged 只动 +0.2pp（best_epoch 从 1 → 3 是唯一健康信号）
- **真正的洞察**：bottleneck 不在 input 信息量，**而在 supervision objective 本身**。正样本对仍然是"共享 ≥2 个 high-IDF tag"——TF-IDF cosine 直接编码这个。给模型 baseline 看不到的信号（review / year）也跑不过 baseline，**因为目标函数定义了 ceiling**。要破，得换 supervision 信号（路径 B 蒸馏 Steam "More Like This"；或 behavioral co-ownership 数据）
- Per-cluster 细节（aux on vs TF-IDF）：narrative +5.7pp（叙事游戏 year/review 是真信号）；action_rpg -27.1pp（aux 反而带噪音）；其他互见
- **portfolio 故事**：两个干净的负结果证伪"tag-only supervision 下能赢 baseline"。比"跑了个 transformer 然后说赢了"更扎实
- 数据落地：`data/game_embedding.npy` (14270×256) + meta.json（包含 `aux_dim` / `aux_features` 字段）+ train_log.json
- 关键文件：`scripts/phase4plus_train.py`（含 `load_aux_features()` + `--no-aux` 对照旗标）+ `phase4plus_compare.py`

### Phase 4++：语料扩展 5k → 15k（本轮）
- `phase1_fetch_corpus.py --pages 15` 拉了 14840 个 appid，**14270 ok / 570 errored**（绝大多数 SteamSpy 对下架游戏返空）
- 对 corpus 大小敏感的所有 artifact 都重建：TF-IDF (14270 × 445)、tag_vocab (437→445)、PPMI tag embedding (445×50)、game embedding (14270×256)、tag_i18n（90.6% 覆盖保持）
- 副产品：3 个 phase 脚本加 `sys.stdout.reconfigure(encoding="utf-8")`——Windows 默认 GBK 控制台遇到 `®` 等字符会崩，长 fetch 不可接受
- corpus.db 体积 10.8 MB → 28.9 MB；data/ 总量 ~45 MB（git 仍可接受）
- **未来翻盘出路**（已记 §10）：~~(A) 加 review / owners / release_year 作辅助 input 特征~~ ←**已试，没翻盘**；(B) 蒸馏 Steam "More Like This" 列表；(C) 残差混合模型；(D) Masked-tag 预训练

### Phase 6：端到端 Web 产品
- FastAPI 后端 13 个 endpoint + Steam OpenID + TTL 缓存
- React 前端 + Tailwind v4 + 4 个 tab
- Vercel + Render 自动部署
- 测试通过 HexQuarter 真实 1095 款库 → 62 簇 + 45 regret patterns + 311 sleeping games

### Phase 6.5：Playprint 品牌重塑 + Result 3-Act 改版
- 品牌 rename "Steam Taste Lens" → **Playprint**（前端可见层；仓库/Python 内部名保留）
- 视觉系统：retro-arcade × editorial（Pixelify Sans 顶层 hero / Hanken Grotesk 编辑型 body / JetBrains Mono 元信息），amber on near-black palette
- 双层排印：Pixelify 只用在顶层 hero + 大数字 scoreboard；中层 section/sub-tab 全部 Hanken `tracking-tight + weight 600`
- Result 页改为 **3-Act 叙事结构**：Act I 你的 taste · Act II 你会爱的游戏 · Act III 安静被淘汰的
- Act I 新增 `TagRadar.tsx`：纯 SVG 自实现雷达图（无图表库依赖），与 top-12 ranked list 并列
- Act II 卡片：cover 列加宽到 320px，Steam header 460:215 原比例不裁切
- 全套智能 LoadingState + ErrorState（4 步进度 + 私密资料/找不到/网络 三类诊断）

### Phase 6.6：推荐归因修正（closed-form + closest-fit slot）
- 旧 `explain()` 用 `overlap × log(1+hours)`，时长项压倒一切 → 高时长宽 tag 游戏（如 MHW 353h）霸占所有推荐的归因
- 重写为闭式分解：`contribution(g) = log(1+hours_g) × cosine(g, cand)`——即推荐 cosine 的精确单游戏分摊
- 新增第二槽 `closest_match`：纯 cosine 不带时长权重，挑出库里 tag profile **最定向匹配**候选的小时长游戏；与 drivers 去重 + 0.30 相似度下限
- 前端在 "BECAUSE OF" 行下新增 "↳ CLOSEST FIT" 二级行，仅在与 drivers 不同时出现
- 副作用：干掉了每候选 N 次 SQLite tag 查询（原 HANDOFF 标注的"大库 explain SQL 风暴"性能问题随之消失）

---

## 8. 关键技术决定 / Gotchas

### 8.1 SteamID 精度问题（重要）
SteamID64 是 17 位（~7.6×10¹⁶）> JavaScript `Number.MAX_SAFE_INTEGER` (9×10¹⁵)。
**后端 JSON 响应里 steam_id 必须用 string**，否则前端 JSON.parse 时精度丢失（最后一位数字会变），导致拉到别人的库。
TypeScript 类型也是 `steam_id: string`。

### 8.2 CORS 尾斜杠
浏览器 Origin header 永远不带尾斜杠。`FRONTEND_BASE=https://x.vercel.app/` 会让 CORS 拒绝。`backend/config.py` 自动 `.rstrip("/")`，但配 env 时还是别加。

### 8.3 SPA 路由 + Vercel
React Router 在客户端跳转。外部跳转（OpenID 回调、直接访问 /result）需要 `frontend/vercel.json` rewrites 把所有路径指向 index.html。

### 8.4 Vite 构建需要 vite-env.d.ts
本地 dev 服务器隐式注入 `import.meta.env` 类型，但 `tsc -b` 不会。必须有 `src/vite-env.d.ts`。

### 8.5 Render 冷启动
Free tier 15 分钟无访问休眠，下次第一个请求 ~30s 冷启动。Demo 时按下"分析"转圈半分钟是正常的。

### 8.6 Software 不是 Game
Valve 把 Wallpaper Engine / Lossless Scaling 标 `type=game`，导致 HDBSCAN 把它们当成游戏簇推为 regret。`regret_detector.py` 通过 dominant tags 二次过滤（含 Utilities/Software 等就跳过）。

### 8.7 Match % 重映射
后端 cosine sim 一般 0.4-0.7。直接 ×100 显示 40-70% 看着低，不让用户信任。`_match_pct()` 用 sqrt 重映射：0.5→71%, 0.7→84%, 0.8→89%。

### 8.8 OpenID 行为
Steam OpenID 返回**浏览器当前登录的 Steam 账号**，不是用户输入的 SteamID。所以测试时 OpenID 路径和 URL paste 路径会得到不同结果是预期的，不是 bug。

---

## 9. 本地开发

### 启动后端
```powershell
cd e:\study\project
py -m uvicorn backend.main:app --reload --port 8000
```
访问 http://localhost:8000/docs 看 Swagger。

### 启动前端
```powershell
cd e:\study\project\frontend
npm run dev
```
访问 http://localhost:5173。

### 重新构建 corpus（只在需要更新时跑）
```powershell
py scripts/phase1_fetch_corpus.py          # ~2 小时
py scripts/phase1_build_index.py           # ~10 秒
py scripts/phase1_health_check.py          # ~1 秒
```

### 离线端到端测试（不需要前端）
```powershell
py scripts/phase2_test_engine.py                                # demo 用户
py scripts/phase2b_test_real_user.py 76561198098881759 --out o.txt  # 真用户
py scripts/phase3_test_regret.py                                # regret 报告
```

### 部署流程
```powershell
git add -A
git commit -m "your message"
git push                                   # 自动触发 Vercel + Render 重新部署
```

---

## 10. 待优化（按优先级）

> **最近一次重排：2026-06-04 晚**。

### Scoreboard

**剩下没做的（按 ROI 排序）：**
1. **Phase 4+ 翻盘出路**：~~(A 加 review/owners/year)~~ 已试无效 → 剩 B 蒸馏 Steam "More Like This" / C 残差混合 / D Masked-tag 预训练。**真正的卡点是 supervision objective 本身**（详 §7 Phase 4+）
2. **Phase 5: Bayesian + multi-query**（数天）—— 让 "multi-query similarity" 从规划变成上线
3. LLM 文案润色 / 协同过滤 / 价格分析（都是 nice-to-have，不做也无伤）

**已 demote：** Render 冷启动修复 —— 后端用付费档，冷启动不严重，不再列 P1。

**自上次同步以来已完成（4 个里程碑）：**
- ✅ **Path A: 加 review/year/owners 辅助特征**（**本轮**）：merged 75.3% → 75.5%（+0.2pp，落 CI 内）。结论：bottleneck 不在输入，在 supervision objective（详 §7）
- ✅ 语料 5k → 15k（commit `9f14e57`）：14270 ok 游戏、445 tag。PPMI 重建后 +3.4pp（旧 +2.4pp）；trained encoder 反而 -7.9pp（旧 -2.1pp）
- ✅ Tag i18n（commit `905f2af`）：Steam 官方 populartags 端点的 en + schinese 按 tagid join，403/445 ≈ 90.6% 覆盖
- ✅ 品味金句 22 archetype × 2 变体 × en/zh（commit `327915f`）

**已完成（自上次同步以来 6 个 commit）：**
- ✅ 品味金句 i18n + archetype 扩到 22 个 × 2 变体（**本轮**）
- ✅ ErrorState 补 i18n（commit `72b9c91`）
- ✅ Regret 文案多样化（commit `eb764d4`）
- ✅ release_year 偏置 + fresh_fit mode（commit `95a8792`）
- ✅ 中英双语 i18n（commit `8eb11ee`）
- ✅ HANDOFF 同步（commit `1a55f22`）

**更早完成：** README + 简历段落 (`90e5299`) · 闭式归因 + closest_match (`246bab9`) · 雷达图 + 排印改版 (`577a476`) · Playprint rebrand (`c56c894`) · Phase 4 自训练 embedding (`d7cfe8b`)

---

### 优先级 1 — 已完成
- ✅ **README.md**（commit `90e5299`，含三路检索消融表 + 闭式归因故事 + 截图）
- ✅ **简历段落初稿**（已写进 `steam-game-advisor-project.md` §12 中英双版）

### 优先级 2 — 用户体验底线

1. ~~**修 Render 冷启动**~~ — 后端用付费档，冷启动不严重，**demote 出 scoreboard**。
   - 如果某天迁回 free tier：uptimerobot 心跳（5 分钟）+ 前端 Home 静默预热可以恢复方案

2. ✅ ~~**Regret 文案多样化**~~（commit `eb764d4`）
   - Mixed 4 变体（single_anchor_deep / high_untouched_ratio / saturation / classic）+ Pure 9 domain 模板（survival_craft / grand_strategy / souls_like / roguelite / horror / jrpg / cozy / simulation / shmup）+ 3 quantitative fallbacks
   - 每模板有 `zh` + `en` 平行字段，[regret_detector.py:_build_diagnosis(cluster, lang)](backend/regret_detector.py)，i18n 用

3. ✅ ~~**release_year 偏置 + fresh_fit mode**~~（commit `95a8792`）
   - [taste_engine.py:_parse_year()](backend/taste_engine.py) regex，corpus 14230/14270 命中 99.7%（5k 版本时 4967/4985）
   - 公式 `recency = 1 / (1 + age/5)`，参考年份取 corpus 最新年（自动跟刷数据走）
   - `recommend(mode="fresh_fit")` 应用 `sims *= 1 + 0.30 * recency`，叠加在 quality boost 之上
   - 前端 [RecommendationsTab](frontend/src/components/RecommendationsTab.tsx) 加 best fit / fresh fit pill toggle，切换轻量级 refetch 不重跑 pipeline

### 优先级 3 — 国际化

4. ✅ ~~**中英文切换（i18n）**~~（commit `8eb11ee`）
   - `react-i18next` + `i18next-browser-languagedetector`，locale JSON 在 [src/locales](frontend/src/locales)
   - Masthead 顶栏 `EN / 中` pill 切换器，localStorage 持久化（key=`playprint.lang`）
   - 后端 `regret_endpoint(steamid, lang)` → `detect_regret(..., lang)` → `_build_diagnosis(cluster, lang)`
   - 切换语言时 [Result.tsx](frontend/src/pages/Result.tsx) 自动 refetch regret（前端 t() 直接生效，后端 prose 必须 refetch）
   - ✅ ~~ErrorState 未翻译~~ —— 已补，4 类 diagnosis（privacy / notFound / network / unknown）全部 i18n，diagnose() 改返 `kind` 让渲染层切换 body 模板
   - ✅ ~~品味金句仍是英文~~ —— commit `327915f`：`_generate_one_sentence(top_tags, steamid, lang)` 走 `HERO_TEMPLATES`，22 archetype × 2 变体 × en/zh，变体按 `steamid % len(variants)` 选；`/api/taste/{steamid}/profile?lang=` 接 lang 参；前端 Result.tsx 切语言时同时 refetch taste + regret
   - ✅ ~~tag 名字全英文~~ —— 本轮：`scripts/build_tag_i18n.py` 抓 Steam 官方 populartags 两套语言按 tagid join，落 `data/tag_i18n.json` + 复制到 `frontend/src/locales/`；前端 `useTagLabel()` hook 在 zh 模式下做 lookup，TagRadar / TasteProfileTab（ranked + cluster name + chips）/ RegretTab（pattern title）/ RecommendationsTab（shared_tags）全部接入。Cluster name 改从 `dominant_tags` 前端重组（旧 backend `c.name` 留作 dominant_tags 空时的 fallback）

### 优先级 4 — 数据 / 算法深化（高工程量、ROI 因目标而异）

5. **扩 corpus 5k → 15k**（一个周末）
   - `phase1_fetch_corpus.py` 支持续传，~6-9 小时 fetch + `phase1_build_index` 10 秒 + `phase4_build_tag_embedding` + `phase4plus_train` 10 几分钟
   - 数据增量 12MB → 35-40MB，git 仍可接受
   - 法律 / 政策：Steam Store + SteamSpy 公开数据，没有限制
   - 收益：解决推荐总是长尾老游戏的问题（5k 是按销量 top 抓的，新游戏漏掉很多）；**且可能让 Phase 4+ trained encoder 真的超过 SPPMI 基线**——大数据量是 contrastive learning 显出优势的前提，跑出来又是一个 portfolio 故事「我重新跑了消融，结论变了」
   - 不建议自动化（不要 cron），人工 6 个月一刷

6. **Phase 5: Bayesian taste posterior + multi-query**（数天）
   - taste vector 升级为带置信度的后验
   - 5+ similar query 维度（similar / for-you / slower / chill / hidden / shorter）
   - 实现 §6.7 / §6.5 里原 spec 计划过但未建的"相似游戏多 query"页面
   - 让简历"multi-query similarity system"从"规划过"变成"上线了"

### 优先级 5 — 不太可能做但记录

7. **LLM 文案润色**（半天）
   - 自然接入点：用 LLM 生成每个 regret cluster 的独特一句话诊断（替换上面 #2 的模板池）
   - 或生成 taste hero quote（替换现有模板）
   - **但**：前面 #2 已经能给 80% 效果且零成本零延迟；只在 #2 做完仍觉不够时考虑
   - 项目"故意不用 LLM"在面试里是个**更强的叙事**，加 LLM 反而减分（详见 §13 协作建议里的"实证主义"段）
8. **协同过滤**（中长期）：如果有真用户访问数据后，做 "owners of X also own Y"
9. **价格 / 评论分析**：重新引入 ITAD，做"Similar but cheaper"维度

---

## 11. 待调查 / 已知小问题

### 仍然 open

- ℹ️ **Render 冷启动**：当前后端是付费档，冷启动不严重，已 demote。若日后回 free tier，方案见 §10。
- ⚠️ **Top recs 倾向长尾老游戏**：corpus 是按 SteamSpy 销量 top-5k 抓的，新游戏覆盖不足。`fresh_fit` mode（commit `95a8792`）能缓解但治标，根治要扩 corpus（§10 scoreboard #1）。
- ⚠️ **雷达图 narrow viewport 标签内边距**：~900px 以下时左右两侧长名字（如 "Great Soundtrack"）紧贴 SVG 边缘。不截断，只是挤。修法：[TagRadar.tsx](frontend/src/components/TagRadar.tsx) 里 `radius = center * 0.62` 降到 `0.55`，或外层套 `px-2`。

### 信息性 / 易踩坑

- ℹ️ **评价数据已经在用**：`recommend()` 有 `min_reviews=50` + `min_quality=0.65` 硬过滤 + `(0.85 + 0.30*quality)` 软加成（[taste_engine.py:_ensure_extended_meta()](backend/taste_engine.py)）。新对话别再以为没接入评价。
- ℹ️ **`explain()` 签名是 3 元组**（`shared_tags`, `evidence`, `closest_match`），不是 2 元组。目前只有 [main.py:_build_rec_card](backend/main.py) 和 [taste_engine.py:format_recommendations](backend/taste_engine.py) 调用，都已更新。
- ℹ️ **新 API 契约（i18n / fresh_fit 引入）**：
  - `GET /api/taste/{steamid}/profile?lang=zh|en` —— `lang` 默认 zh，未知值退回 zh
  - `GET /api/taste/{steamid}/regret?lang=zh|en` —— `lang` 默认 zh，未知值退回 zh（不报错）
  - `GET /api/taste/{steamid}/recommend/new?mode=...` —— `mode` 合法值 `best_fit | hidden_gem | stretch | fresh_fit`（fresh_fit 是新加的）

### 已修复（按时间倒序）

- ✅ ~~tag 名字全英文~~ — 本轮，Steam 官方 populartags en+schinese 按 tagid join，90.6% 覆盖，useTagLabel hook 渲染期 lookup
- ✅ ~~品味金句仅 EN + 模板薄~~ — commit `327915f`，22 archetype × 2 变体 × en/zh，hash(steamid) 选变体
- ✅ ~~ErrorState 未 i18n~~ — commit `72b9c91`，diagnose() 改返 kind，body 在组件里按 kind 切换
- ✅ ~~Regret 文案重复~~ — commit `eb764d4`
- ✅ ~~`release_date` 未用于偏置~~ — commit `95a8792`
- ✅ ~~高时长宽 tag 游戏霸占归因~~ — closed-form decomposition + closest_match，commit `246bab9`
- ✅ ~~`explain()` 大库 SQL 风暴~~ — 改为纯 in-memory sparse 点积，commit `246bab9`
- ✅ ~~Vite 类型缺失构建失败~~（修了）
- ✅ ~~Vercel SPA 404~~（修了）
- ✅ ~~CORS 尾斜杠~~（修了）
- ✅ ~~SteamID 精度~~（修了）

---

## 12. 与新对话的协作建议

接手新对话时：
1. **先看 §10 scoreboard 拿全局**——一眼能看到剩下没做的 5 件事 + 最近完成的 4 个 commit
2. **不需要重读所有源代码**——先读 `steam-game-advisor-project.md` 拿到设计意图，再针对要改的模块读对应文件
3. **不要重复造轮子**——上面"已完成"列表里的功能都跑通了，不要建议再做一遍
4. **GIT 操作要小心**——每个 commit 都单一职责。新改动尽量同样原则（参考最近 3 commit 的拆分粒度：regret / fresh_fit / i18n 各一个）
5. **改动后必须本地跑通再 push**——push = 自动重新部署生产。本地：
   - 后端：`py -m uvicorn backend.main:app --reload`
   - 前端：`cd frontend && npm run dev`
6. **当前最高优先级 = 扩 corpus 5k → 15k**——参考 §10 scoreboard #1。可缓解长尾老游戏问题，且有翻盘 Phase 4+ 消融的可能。

---

## 13. 用户偏好（重要！协作风格）

观察到的用户偏好（这些都已经达成共识）：
- 喜欢**简洁直接**的回答，不要废话和过度铺垫
- 在做大方向决策前要**讨论清楚**（这是为什么我们花很多对话定下了 taste lens 方向）
- 不喜欢**理想化 / 过度设计**的方案，会反问"是不是太定制了？"
- 重视**实证而非流行**：Phase 0 的 6 方法对比就是用户推着我做的
- 重视**可解释性 + portfolio 卖点**：每个功能都讨论过简历怎么写
- 对**未经验证的复杂方案警惕**，会让先用最简单的方法验证

不要给他端上：长篇技术评估、unsolicited 改名建议、模板化总结。要给他：具体、可行、有判断力的下一步。
