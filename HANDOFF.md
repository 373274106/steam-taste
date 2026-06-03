# Steam Taste Lens — 交接文档

> 给新对话用：把这份 + `steam-game-advisor-project.md` 一起读，能完整接手项目。
> 项目当前**已上线**，端到端可访问，处于"打磨 + 写 portfolio writeup"阶段。

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
| 数据存储 | SQLite (`data/corpus.db`) + scipy sparse npz (`data/tfidf.npz`)|
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
│       ├── index.css                # Tailwind + 主题 CSS 变量 + 动画
│       ├── vite-env.d.ts            # Vite import.meta.env 类型声明
│       ├── lib/
│       │   ├── api.ts               # 后端 API 客户端（fetch wrapper）
│       │   └── types.ts             # 所有 API 响应的 TS 类型
│       ├── pages/
│       │   ├── Home.tsx             # 落地页：OpenID + URL paste + Demo 三档
│       │   └── Result.tsx           # 4 tab shell + 状态管理
│       └── components/
│           ├── TasteProfileTab.tsx
│           ├── RecommendationsTab.tsx  # Discover New + Play What You Own
│           ├── RegretTab.tsx           # Mixed / Pure / Sleeping 三 sub-tab
│           ├── LoadingState.tsx        # 4 步进度条
│           └── ErrorState.tsx          # 智能错误诊断（私密资料/找不到/网络）
│
├── scripts/                         # 一次性 / 离线脚本
│   ├── phase1_fetch_corpus.py       # 抓 5000 款游戏（~2 小时，可续传）
│   ├── phase1_build_index.py        # 构建 TF-IDF 矩阵
│   ├── phase1_health_check.py       # 抽样验证 nearest neighbor
│   ├── phase2_test_engine.py        # 离线测试 demo 用户
│   ├── phase2b_test_real_user.py   # 测试真实 SteamID 端到端
│   ├── phase3_test_regret.py        # 测试 regret 检测
│   ├── embedding_probe.py           # Phase 0：transformer 嵌入实验
│   ├── embedding_compare.py         # Phase 0：6 种方法对比（验证 tag-based 优势）
│   ├── embedding_diagnose.py        # Phase 0：邻居诊断
│   └── itad_match_probe.py          # Phase 0 早期探针（已废弃）
│
└── data/                            # 已 commit 进 git（12MB）
    ├── corpus.db                    # 4985 款游戏元数据 + tags
    ├── tfidf.npz                    # 4985 × 437 sparse TF-IDF 矩阵
    ├── tag_vocab.json
    ├── appid_order.json
    └── inverted_index.json
```

---

## 6. Git 历史

```
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
- 抓 SteamSpy top 5000 款元数据 + 标签
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

### Phase 6：端到端 Web 产品
- FastAPI 后端 13 个 endpoint + Steam OpenID + TTL 缓存
- React 前端 + Tailwind v4 + 4 个 tab
- Vercel + Render 自动部署
- 测试通过 HexQuarter 真实 1095 款库 → 62 簇 + 45 regret patterns + 311 sleeping games

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

### 优先级 1（必做，对 portfolio 影响大）
1. **写 README.md**（仓库首页空的，面试官会先看）
   - 项目截图（taste / recs / regret 三张）
   - 一句话定位 + 视频/动图（可选）
   - 技术栈徽章
   - 本地启动指南
   - 公开 demo 链接
   - 实验结论："tag-based 在 game-game similarity 上比 transformer 嵌入高 30%"

2. **简历介绍段落**（中英双语版）
   - 已有素材在 `steam-game-advisor-project.md` 的 §12 节
   - 可以再扩展添加实际成绩数字：「在真实 1095 款库测试中识别出 311 款 untouched games + 45 个 regret patterns」

### 优先级 2（可选打磨）
3. **Render 冷启动应对**
   - 加一个 cron job 每 10 分钟 ping `/api/health` 保持活跃（uptimerobot.com 免费）
   - 或前端在 Home 页就静默 ping 一下后端预热
   - 或升级 Render Starter $7/月

4. **隐私 / Demo 模式 UX 改进**
   - Demo 模式可以让用户看到 "Demo Player" 的具体游戏库构成（透明）
   - 添加"分享我的 taste 画像"截图导出按钮（增加传播）

5. **错误状态扩展**
   - 添加 Steam API 限流的友好提示
   - 添加 Render 冷启动期间的 "服务正在启动..." 提示（30s 倒计时）

### 优先级 3（算法深度，post-MVP）
6. **Phase 4: Tag co-occurrence embedding**（项目 md §6.5）
   - 从 corpus 构建 PPMI + SVD 学 50 维 tag 表示
   - 解决 "Rogue-like" / "Rogue-lite" / "Roguelike" 同义词合并
   - 给冷门游戏（tag 少）做语义扩展
   - 这是简历"自训练 ML"的核心卖点

7. **Phase 5: Bayesian taste posterior + multi-query**
   - taste vector 升级为带置信度的后验
   - 5+ similar query 维度（similar_but_slower / similar_but_chill 等）

8. **Phase 7+: 价格 / 评论分析**（如果方向再扩）
   - 重新引入 ITAD 价格数据（购买时机）
   - Steam 评论摘要（LLM 摘要，可选）
   - 现在的代码里有 `steam_client.py` 但只用了 GetOwnedGames，扩展容易

### 优先级 4（不太可能做但记录一下）
9. **多语言支持**：UI 文案目前是中英混用，整理成专门的 i18n
10. **更大 corpus**：从 5000 扩到 15000，覆盖更多长尾用户库
11. **协同过滤**：如果有用户访问数据后，做 "owners of X also own Y"

---

## 11. 待调查 / 已知小问题

- ✅ ~~SteamID 精度~~（修了）
- ✅ ~~CORS 尾斜杠~~（修了）
- ✅ ~~Vercel SPA 404~~（修了）
- ✅ ~~Vite 类型缺失构建失败~~（修了）
- ⚠️ Render free tier 冷启动 30s——已知限制，不算 bug
- ⚠️ Top recommendations 倾向旧 RPG（Two Worlds 2008 / Lightning Returns 等）。原因：用户 1095 款库已经包含所有现代好 RPG，算法只能在长尾里找。这不是 bug，是真实约束。要优化要么扩 corpus 要么加 release_year 偏置。
- ✅ ~~`explain()` 大库 SQL 风暴~~（修了——`explain()` 已改为纯 in-memory sparse 点积，归因公式也修正为 `log(1+hours) × cosine(g, cand)` 的闭式拆解，不再被高时长游戏霸占归因）

---

## 12. 与新对话的协作建议

接手新对话时：
1. **不需要重读所有源代码**——先读 `steam-game-advisor-project.md` 拿到设计意图，再针对要改的模块读对应文件
2. **不要重复造轮子**——上面"已完成"列表里的功能都跑通了，不要建议再做一遍
3. **GIT 操作要小心**——4 commit 历史是干净的，每个 commit 都有意义。新改动也保持单一职责的 commit。
4. **改动后必须本地跑通再 push**——push = 自动重新部署生产。本地：
   - 后端：`py -m uvicorn backend.main:app --reload`
   - 前端：`cd frontend && npm run dev`
5. **README 是下一步最高优先级**——参考"待优化"§10.1

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
