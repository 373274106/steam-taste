# Steam Taste Lens — Project Plan

> 文件名暂时保留 `steam-game-advisor-project.md`，但项目已从"购买建议器"转向"玩家品味透镜"。后续可考虑改名为 `steam-taste-lens-project.md`。
>
> **公开品牌**：**Playprint**（前端标题、页面文案、URL `playprint`-style 命名）。
> **代码层命名**：保留 Steam Taste Lens / `steam-taste-lens-frontend` / `backend/taste_engine.py`，
> 因为这是项目的算法身份，rebrand 只是产品包装。两层并存是有意的。

## 1. Project Summary

Steam Taste Lens 是一个面向 Steam 玩家的网页应用。它不是给 Steam 商店锦上添花的推荐器，而是**揭示 Steam 不愿意告诉你的事情**的玩家品味透镜。

它回答的核心问题不是"这款游戏好不好"，而是：

- 我到底是哪种玩家？我的品味边界在哪？
- 我买了哪些游戏其实根本没玩？是什么类型？
- 我应该试试什么我没玩过、但真的会爱的游戏？
- 一款目标游戏，对"现在的我"来说到底匹配吗？

核心输出是品味画像 + 个性化推荐 + 反思性洞察，**不是购买建议**。

## 2. Project Positioning

### 2.1 Why this exists

Steam 自己有强大的推荐算法和"相似游戏"功能。在纯推荐准确性上我们做不过——他们手里有几亿用户的购买数据、协同过滤、好友图。

但 Steam 的推荐有一个根本约束：**它服务于让玩家买更多的商业目标**。它永远不会：

- 告诉你"你买了 8 款生存游戏，中位时长 1.8 小时，慎重"
- 揭示你库里那些"买了从来没启动"的购买模式
- 优先推荐你长尾、小众但更适合你的游戏（推爆款转化率更高）
- 解释为什么推荐 X 而不是 Y
- 让你按"类似但更慢 / 更便宜 / 更短"等多维度查询

这些 Steam 不会做的事，是我们的产品定位。

### 2.2 Target Users

- 已经有可观 Steam 游戏库的玩家（library size ≥ 20）
- 经常买了不玩、想搞清楚自己消费模式的人
- 想知道自己 taste 边界、找下一款"自己会真玩"的游戏的人
- 对推荐黑盒不满意、想要可解释结果的人

### 2.3 Core Value vs Steam

| 维度 | Steam 官方 | Taste Lens |
|---|---|---|
| 优化目标 | 转化率（买更多）| 契合度（买对）|
| 倾向 | 热门 + 高销量 | 长尾 + 合适 |
| 透明度 | 黑盒 | 完全可解释（标签 + 时长证据）|
| 反向建议 | 不会 | 会（"你不适合这个类型"）|
| 自省工具 | 几乎没有 | 中心功能（Regret / Profile）|
| 多 query 相似度 | 单一固定 | 多种变体 |

明确不追求"比 Steam 的推荐精度更高"。差异化在目标、透明度、自省维度。

## 3. Design Principles

### 3.1 Web First

网页应用，无需安装，链接即用，适合 portfolio 展示。

### 3.2 Not a Chatbot

界面以 taste 画像、推荐卡片、洞察图表为主。LLM 在 MVP 不使用，Phase N+ 可选用于自然语言润色。

### 3.3 Explainable Recommendations

每条推荐必须给出证据：

```text
推荐《Inscryption》

依据：
- 你在《Slay the Spire》投入 73 小时，《Monster Train》35 小时
- 三款游戏共享 deckbuilder / dark-atmosphere tags
- 但《Inscryption》比你常玩的 deckbuilder 慢，平均通关 12 小时
  你的 deckbuilder 中位时长 25 小时，你能消化
```

### 3.4 Demo Mode Required

不是所有访问者都愿意输入 Steam ID 或资料公开。系统必须有 Demo Mode（一组预设玩家库），让面试官 / 访问者无需登录即可体验完整功能。

### 3.5 Honest About Confidence

如果用户库过小（< 20 款）、或目标游戏在嵌入空间无强相似邻居（cosine < 阈值），系统应**明确告知**而不是硬推。这是和 Steam 不同的态度——我们承认"不确定"。

## 4. Main Features

### 4.1 Taste Profile

中心功能。展示用户的玩家画像。

模块：

- 总览：库大小、总时长、最高时长游戏
- Tag affinity 雷达图（top 8 标签，时长加权）
- 游戏散点图（UMAP 2D 投影，点 = 游戏，颜色按主标签）
- Taste 簇识别 + 自动命名（KMeans on user library embeddings）
- "你最像哪种玩家"一句话总结

示例：

```text
你主要在三个 taste 簇里：
- 深夜 Roguelite（Hades 130h, Risk of Rain 2 65h, Returnal 40h）
- 大策略（CK III 200h, Stellaris 120h, EU IV 80h）
- 开放世界 RPG（Skyrim 90h, Witcher 3 70h）

但你库里还有 12 款"生存建造"游戏，平均 2.3 小时——这不是你真正的 taste。
```

### 4.2 Personalized Recommendations

输入：用户 taste profile
输出：用户未拥有、但与 taste centroid 相近的游戏

差异化设计：

- **去热门偏置**：默认排除 Steam 销量 top 10% 的爆款（用户自己会看到）
- **多目标 query**：
  - `best_fit`：最接近 taste centroid（默认）
  - `stretch`：邻近簇但不完全在 centroid 上，拓展边界
  - `hidden_gem`：低销量 + 高契合度
  - `quick_try`：通关时长 < 10h，适合试水
- 每条推荐附"为什么"：共享标签 + 用户时长证据

### 4.3 Similar Games（Multi-Query）

输入：任意一款目标游戏（用户输入名字 / appid / Steam URL）
输出：多种"类似"维度

| Query | 实现 |
|---|---|
| Similar | 嵌入空间最近邻 |
| Similar but slower | 邻居 ∩ 平均通关时长更长 |
| Similar but for you | 邻居 ∩ 用户 taste 距离更近（个性化重排）|
| Similar but more chill | 邻居 ∩ 标签含 cozy / relaxing / no-fail |
| Similar but shorter | 邻居 ∩ 平均通关时长更短 |

每种 query 输出 5-8 个候选 + 解释。

### 4.4 Library Regret Detector

中心功能。揭示用户购买模式中的"白买"问题。

分析维度：

- 按 tag 簇聚合：每个簇的"购买数 vs 平均时长"
- 高购买 / 低时长 簇标记为 **Regret 簇**
- 个别游戏：库里时长 < 0.5h 且发售 > 3 个月的"沉睡"游戏
- 模式诊断："你似乎在 Sale 期间过量购买 X 类型"

示例：

```text
你的 Regret 簇：

1. 生存建造（8 款，中位时长 1.8h）
   你似乎被这类游戏的概念吸引，但实际玩不下去。
   建议：未来对 survival craft tag 的游戏多观望、少购买。

2. 4X 策略（5 款，中位时长 4.2h）
   除 Stellaris 之外都没怎么玩。
   你可能更适合"快节奏 4X"或"小规模策略"，纯大型 4X 不适合你。
```

这个功能 Steam 永远不会做（鼓励买少 = 反商业利益），但对玩家价值极高，也是项目最有传播性的功能。

## 5. Data Sources

### 5.1 Steam Owned Games（核心）

用途：用户拥有的游戏 + 总时长 + 近两周时长

来源：
- Steam Web API: `IPlayerService/GetOwnedGames`
- 需要 Steam API key（后端持有）+ 用户 SteamID
- 用户资料需公开，或通过 OpenID 登录获取 SteamID

### 5.2 Steam Game Metadata（核心）

用途：构建游戏语料库的核心特征，输入嵌入模型

字段：
- `name` / `appid` / `header_image` / `type`
- `short_description`（200-400 字）
- `tags`（用户众标，多语言）
- `genres` / `categories`（官方分类）
- `release_date`

来源：
- Steam Store API: `/api/appdetails?appids=...`
- SteamSpy: 销量估计、tag 频次（用于热度筛选）

限制：
- Steam Store API 限速 ~200 req / 5 min
- 抓 5000 款约需 2-3 小时（一次性 + 周更）

### 5.3 Tag-Based Similarity（核心）

⚠️ **方向更新**：Phase 0 嵌入对比实验（[scripts/embedding_compare.py](scripts/embedding_compare.py)）显示，纯 transformer 嵌入（55% merged hit rate）显著输给基于 tag 的方法（**tag Jaccard 85%，TF-IDF tag 余弦 83%**）。原因是描述文本中的营销/剧情文案污染了语义信号。

MVP 改为 **tag-based similarity** 主路径，sentence-transformer 降级为 Phase 4+ 的语义扩展层。

主要特征源：
- **SteamSpy 用户众标**（`tags`）：每款 15+ 高频 tag，用户提炼的语义关键词
- **Steam Store genres**：官方大类（Action / Indie / RPG），作为辅助
- 不使用：description 文本（噪声 > 信号）

权重方案：
- 简单基线：tag Jaccard `|A ∩ B| / |A ∪ B|`
- 进阶：TF-IDF 加权 tag 余弦，IDF = `log(N / df(tag))`
  - 抑制 "Indie", "Singleplayer" 等泛 tag
  - 强化 "Bullet Hell", "Roguelike Deckbuilder" 等稀有 tag
- Phase 4+：tag co-occurrence embedding（见 6.5）

存储：
- 倒排索引（tag → [appid 列表]），快速候选过滤
- TF-IDF 矩阵（5000 × ~400 tags）：稀疏 numpy，几 MB
- SQLite 存元数据 + tag 列表

### 5.4 Out of Scope

明确**不在 MVP 范围**的数据源：

- **Price History (ITAD)**：购买建议方向已弃，价格不是核心信号。"Similar but cheaper" 功能可在 Phase 7+ 重新引入
- **Steam Reviews**：评论摘要 / 风险分析全部移除。后续可作 taste 信号增强（情感分析），但不是当前 scope
- **LLM API**：MVP 不使用。所有解释通过模板拼接

## 6. Taste Engine（多层架构）

Taste Engine 不是单一算法，是 6 层逐步加深的系统。Phase 1 跑通 6.1-6.2 基线，后续 Phase 加深度。每层独立可 demo，技术深度逐层递增。

### 6.1 Layer 1: Tag Inverted Index + TF-IDF（基线）

游戏 × tag 倒排索引 + TF-IDF 权重：

```python
# 离线一次性算好
for game in corpus:
    for tag in game.tags:
        inverted_index[tag].append(game.appid)

df[tag] = len(inverted_index[tag])
N = len(corpus)
idf[tag] = log((N + 1) / (df[tag] + 1)) + 1   # smoothed

for game in corpus:
    for tag in game.tags:
        tfidf[game, tag] = count(tag, game) * idf[tag]
    tfidf[game] = normalize(tfidf[game])   # L2 norm
```

存储：稀疏 TF-IDF 矩阵 + tag 倒排索引，SQLite 几 MB。

### 6.2 Layer 2: Game-Game Similarity（Phase 0 验证过 85%）

```python
def similar_games(target_appid, k=10):
    target_vec = tfidf[target_appid]
    # 候选限定为 target 至少共享 1 个 high-IDF tag 的游戏（用倒排索引快速过滤）
    candidates = union(inverted_index[tag] for tag in target.tags if idf[tag] > threshold)
    scores = cosine(target_vec, tfidf[candidates])
    return top_k(candidates, scores, k)
```

可选混合：`final = 0.7 * tfidf_cosine + 0.3 * jaccard(target.tags, candidate.tags)`

### 6.3 Layer 3: User Taste Vector（playtime-weighted）

用户 taste 不是中心点，是**全局 tag affinity 向量**：

```python
def user_taste_vector(library):
    taste = zeros(len(tag_vocab))
    for appid, playtime_min in library:
        if appid not in corpus:
            continue
        weight = log(playtime_min / 60 + 1)   # log-hours
        taste += weight * tfidf[appid]
    return normalize(taste)
```

推荐 = 用户 taste 向量与候选游戏 TF-IDF 的余弦：

```python
def recommend(user_taste, owned_set, mode="best_fit"):
    candidates = corpus - owned_set
    scores = cosine(user_taste, tfidf[candidates])
    if mode == "hidden_gem":
        scores -= 0.1 * log(popularity_rank + 1)
    elif mode == "stretch":
        # 取距离适中的（不完全在 centroid 上）
        scores = scores * (1 - abs(scores - 0.6))
    return top_k(candidates, scores)
```

### 6.4 Layer 4: HDBSCAN Library Clustering（Regret 检测核心）

用 HDBSCAN（不是 KMeans，因为无法预设簇数，且 KMeans 假设簇是球形）：

```python
from hdbscan import HDBSCAN

# 用户库的每款游戏在 tag 空间的向量
library_vecs = [tfidf[appid] for appid, _ in library]

clusterer = HDBSCAN(min_cluster_size=3, metric="cosine")
labels = clusterer.fit_predict(library_vecs)

for cluster_id in unique(labels):
    if cluster_id == -1:   # noise
        continue
    cluster_games = [g for g, l in zip(library, labels) if l == cluster_id]
    median_playtime = median(playtime for _, playtime in cluster_games)
    if median_playtime < REGRET_THRESHOLD and len(cluster_games) >= 3:
        flag_regret_cluster(cluster_games)
```

HDBSCAN 的优势：
- 自动确定簇数
- 识别噪声点（不强行归簇）
- 不假设簇为球形（用户库实际形状不规则）

### 6.5 Layer 5: Tag Co-occurrence Embedding（Phase 4，✅ 已完成）

从 5000 款游戏的 tag 共现矩阵学一个**自训练 50 维 tag embedding**（不是用预训练 transformer）：

```python
# 构建 tag-tag 共现矩阵
cooc[t1, t2] = count(games containing both t1 and t2)
ppmi[t1, t2] = log(cooc[t1, t2] * N / (df[t1] * df[t2]))   # PPMI

# SVD 降到 50 维
tag_embedding = SVD(ppmi, k=50)
```

用途：
- 自动发现近义 tag（"Rogue-like" ≈ "Rogue-lite" ≈ "Roguelike"），合并语义
- 给冷门游戏（tag 少）做语义扩展：用 embedding 找最近的 tag 集合
- 解决 tag 拼写变体 / 翻译问题

技术栈：纯 numpy，无 torch。约 100 行代码。

**实测结果（Phase 0 probe 集，K=5）**：
- TF-IDF 基线：83.2% merged hit rate
- PPMI + SVD（本层）：**85.6% merged**（+2.4pp）
- 同义词探针实际命中：`Rogue-like` 邻居 = [Rogue-lite 0.96, Action Roguelike 0.85, Perma Death 0.83]

生产已用：`/api/game/similar?method=ppmi`，调用入口 `TasteEngine.tag_neighbors()` /
`TasteEngine.game_dense_vec()`。落地数据 `data/tag_embedding.npy` (437 × 50)。

### 6.5.1 Layer 5+: Trained Dual-Encoder（Phase 4+，✅ 已完成，结果诚实但 negative）

把 Layer 5 进一步推到"真正的对比学习"——PyTorch 训练一个 MLP encoder：

```python
# 架构：MLP encoder (V → 512 → 256), ReLU + dropout + L2 norm
# Loss: InfoNCE with in-batch negatives, temperature 0.15
# 正样本：共享 >=2 个 high-IDF tag 的游戏对（10.6 万对）
# Phase 0 probe 集 84 款 held out（不进训练对）
```

**实测结果（probe 75 款 / 8 簇，K=5 merged，CI ±5.1pp）**：
- TF-IDF baseline:   **83.2%**
- PPMI + SVD（6.5）:  **85.6%** ← 实际表现最好
- Trained dual encoder: **81.1%** ← 比基线低 2.1pp，**落在 CI 内 → "持平"而非"输"**

**解读**：~5000 款小语料 + 已经"用户众标提炼过"的高质量 tag 信号下，对比学习**在该
样本规模上无法与矩阵分解显著区分**（Levy & Goldberg 2014 预言了这一点，word2vec 在
小数据上 ≈ SPPMI 矩阵分解）。这个 null 结果**不是失败**——它是简历"实验驱动、不迷信
深度学习"故事的核心证据。

落地数据 `data/game_embedding.npy` (4985 × 256) 仍保留，作为 `/api/game/similar?method=trained`
的第三路对照，供前端 demo 三路对比时使用。Runtime 不强制依赖 torch（只 train 脚本需要）。

### 6.6 Layer 6: Bayesian Confidence（Phase 5+）

把 taste vector 升级为带不确定性的后验分布：

```python
prior = uniform_dirichlet(tag_vocab)
for appid, playtime in library:
    evidence_strength = log(playtime / 60 + 1)
    posterior = bayesian_update(posterior, tfidf[appid], evidence_strength)

confidence = 1 - entropy(posterior) / max_entropy
```

低 confidence 时 UI 标"画像还在形成中"，宽置信区间。

### 6.7 Multi-Query System

5+ 个正交查询，每个是 Layer 2 / Layer 3 上的不同排序函数：

```python
similar(X)             = top-k by tfidf_cosine
similar_but_for_you    = top-k by tfidf_cosine * cos(candidate, user_taste)
similar_but_slower     = top-k by tfidf_cosine where median_playtime > target_playtime
similar_but_chill      = top-k by tfidf_cosine ∩ has_tags(["Cozy", "Relaxing", "No Fail"])
similar_but_hidden     = top-k by tfidf_cosine * (1 - popularity_score)
```

### 6.8 Explanation Layer（闭式归因 + 双槽证据）

每个推荐附带：

- **共享 high-IDF tags**（top 4）：候选 vec 与 taste vec 的逐 tag 贡献 `cand[t] * taste[t]`
  排序，取最大几项。例：`Rogue-lite / Roguelike Deckbuilder / Card Battler / Rogue-like`
- **Drivers（playtime × fit）**：库内贡献最大的 1-2 款，按**闭式分解**排序。因为
  taste vector 是 `Σ_g log(1+hours_g) · v_g` 的归一化，每个候选的推荐 cosine 也是
  各库内游戏贡献的精确线性组合：

  ```text
  contribution(g, cand) = log(1+hours_g) · cosine(g_vec, cand_vec)
  ```

  按此值排序——这是"用户多久 × 这游戏多像候选"的真实分摊，**而不是**早期版本里
  `overlap × log(hours)` 那种被时长压倒的近似（旧式让 MHW 343h 这类宽 tag 高时长
  游戏霸占所有归因）。
- **Closest fit slot**：纯 cosine 不带时长权重的库内最近邻，**只在它与 drivers
  不同**时显示（避免重复）。解决 broad-but-heavy 游戏问题——MHW 是大头 driver 没错，
  但 Tales of Zestiria（25h）才是 Tales of Berseria 这个推荐的**真正定向匹配**。
  相似度 < 0.30 时不显示，避免硬凑。
- **反向证据**（计划中，未实现）：用户库里类似但低时长的，作为风险提示

实现：模板字符串拼接，无 LLM；纯 in-memory 稀疏点积，无 per-game SQL。Phase N+ 可选
LLM 做自然语言润色。

API 落地：`shared_tags: string[]` / `evidence_games: EvidenceGame[]` /
`closest_match: EvidenceGame | null`，见 `backend/taste_engine.py:explain()`。

## 7. Product Pages

### 7.1 Home

- Steam ID / Profile URL 输入框
- Demo Mode 按钮
- 隐私提示

### 7.2 Taste Profile Page（核心）

- 总览数据
- Tag affinity 雷达图
- UMAP 2D taste map（散点图）
- Taste 簇卡片
- "你最像哪种玩家"

### 7.3 Recommendations Page

- 4 个 tab：Best Fit / Stretch / Hidden Gem / Quick Try
- 每条推荐卡片：封面 + 名字 + 一句话解释 + 共享 tags + 用户证据

### 7.4 Similar Games Page

- 顶部目标游戏输入框
- 5 个 query tab
- 结果列表

### 7.5 Library Regret Page

- Regret 簇可视化（散点图，Regret 簇标红）
- 每个 Regret 簇诊断卡
- 沉睡游戏列表

## 8. Technical Architecture

### 8.1 Stack

Frontend:
- React + Vite + TypeScript + Tailwind
- Recharts（雷达图、柱图）
- D3 或 react-force-graph（散点图）

Backend:
- Python + FastAPI
- numpy + scipy + scikit-learn（TF-IDF、cosine、SVD）
- hdbscan（用户库聚类）
- umap-learn（2D 降维，可选）
- requests（Steam API）
- SQLite

明确**不依赖**：sentence-transformers / torch / transformers。Phase 0 实验证实 tag-based 方法显著优于 transformer 嵌入，且 stack 简化（部署镜像从 ~1.5 GB 降到 ~200 MB）。

Phase 4 自训练 tag co-occurrence embedding 用 numpy SVD 实现，不引入 torch。

Deployment:
- Frontend: Vercel
- Backend: Render / Fly.io（轻量镜像 ~200 MB）

### 8.2 Backend Endpoints

```text
GET  /api/steam/library?steamId=...           用户库 + 时长
GET  /api/taste/profile?steamId=...           完整 taste 画像
GET  /api/taste/recommendations?steamId=...&mode=best_fit
GET  /api/taste/regret?steamId=...
GET  /api/game/similar?appid=...&user=optional&mode=similar
GET  /api/game/resolve?input=...              URL/appid 解析
GET  /api/demo/profile                        demo 数据
```

### 8.3 Data Flow

```text
预先（离线，每月一次）:
  Steam Store API + SteamSpy → 抓 5000 款元数据 + tags → SQLite
  构建 tag 倒排索引 + TF-IDF 矩阵 → sparse npz
  Phase 4+: tag 共现 SVD → tag_embedding.npy（50 维 × ~400 tags）

请求时（在线）:
  Steam Web API → 用户 owned games + playtime
  过滤到 corpus → playtime-weighted taste vector（tag 空间）
  派生 query:
    - 推荐: cosine(user_taste, tfidf[candidates])
    - 相似: cosine(tfidf[target], tfidf[candidates])
    - Regret: HDBSCAN(library_vecs) → 低 playtime 簇
  解释模板拼接共享 tags + 证据游戏
  → JSON 返回前端
```

### 8.4 Data Architecture

无"训练"，全部为缓存分层：

| 数据 | 策略 | 频率 |
|---|---|---|
| 游戏元数据 + tags + TF-IDF | 预抓 + SQLite + sparse npz | 每月 |
| Tag 倒排索引 | 离线构建，加载到内存 | 重启时 |
| Tag co-occurrence embedding (Phase 4+)| 离线 SVD + npy | 每月 |
| 用户 library | 现场拉 + 缓存 24h | 每次请求 |
| 用户 taste vector | 不持久化（cache key = library hash）| 重算 |
| 推荐 / Regret 结果 | 缓存 24h | 24h |

## 9. Development Phases

### Phase 0: Validation（✅ 完成）

- ✅ ITAD 探针（已弃用，方向转后不需要）
- ✅ **嵌入可行性探针**：180 款密度簇游戏，6 种方法 nearest-neighbor 比较
  - 结果：tag Jaccard 85% / TF-IDF tag cosine 83% / transformer 嵌入 55%
  - 决策：tag-based 主路径，砍掉 transformer 依赖
  - 84 款被纳入 held-out probe set，给 Phase 4 / 4+ 提供独立评估

### Phase 1: Game Corpus + TF-IDF Baseline（✅ 完成）

- 抓 5000 款 Steam 热门游戏元数据 + SteamSpy tags（按销量/热度排序）
- 构建 tag 倒排索引
- 计算 TF-IDF 矩阵（sparse），存 SQLite + npz
- 健康检查：随机抽 20 款看 game-game 相似度合理性
- Deliverable：`/api/game/similar?appid=...` 能工作

### Phase 2: User Taste Vector + Recommendations（✅ 完成）

- Steam library 拉取（先支持公开 SteamID，OpenID 推后）
- Playtime-weighted user taste vector（tag 空间）
- Endpoints：`/api/taste/profile`、`/api/taste/recommendations?mode=best_fit`
- Demo profile JSON 准备（写死一个高质量的"理想用户"）

### Phase 3: HDBSCAN Library Clustering + Regret（✅ 完成）

- HDBSCAN 用户库聚类（cosine metric on TF-IDF vectors）
- Regret 检测：低中位 playtime + 簇大小 ≥ 3
- 诊断模板：自动归纳簇的 dominant tags + 写成诊断卡
- Endpoint：`/api/taste/regret`

### Phase 4: Tag Co-occurrence Embedding（深度层，✅ 完成）

- 从 corpus 构建 tag-tag 共现矩阵 → PPMI 归一化 → numpy SVD 降到 50 维
- 同义词探针通过：`Rogue-like` ↔ `Rogue-lite` cosine 0.96
- 三路检索消融（probe K=5）：TF-IDF 83.2% → **PPMI 85.6%（+2.4pp）**
- 生产已用：`/api/game/similar?method=ppmi`
- 落地：`data/tag_embedding.npy` + meta.json

### Phase 4+: Trained Dual-Encoder Ablation（深度层，✅ 完成，结果 honest negative）

- PyTorch MLP encoder + InfoNCE + in-batch negatives
- Phase 0 probe 集 held out（75 款在 corpus 内，84 款相关 appid 全部从训练对中剔除），10.6 万对 positive 训练
- 结果：trained 81.1% merged，**比 TF-IDF 基线低 2.1pp（落在 ±5.1pp CI 内），比 PPMI 低 4.5pp**
- 解读 + portfolio 价值：见 §6.5.1。简历卖点不是"训了个 SOTA"，是
  "实证对比 + 在小语料 + 高质量 tag 信号下诚实承认对比学习不优于矩阵分解"
- 落地：`data/game_embedding.npy` + 训练日志；runtime 不强制依赖 torch

### Phase 5: Bayesian Confidence + Multi-Query（未做）

- Bayesian taste posterior（Dirichlet prior + 观测更新）
- 置信度上 UI（小库标注"画像形成中"）
- 5 个 similar query 维度：similar / for-you / slower / chill / hidden
- Stretch / Hidden Gem / Quick Try 推荐模式

### Phase 6: Frontend + Polish + Deploy（✅ 完成）

- Vite + React + TS + Tailwind v4
- 部署上线 Vercel + Render，已通过真实 1095 款库测试
- 三个核心页：Home / Result（3 个 tab）
- Demo Mode（一组预设 26 款库）
- Smart LoadingState + ErrorState
- UMAP 散点图未做（雷达图 + cluster 卡片代替，效果更编辑）

### Phase 6.5: Playprint 品牌重塑 + Result 3-Act 改版（✅ 完成）

- 前端 brand rename → **Playprint**（仓库/Python 内部仍叫 Steam Taste Lens）
- 视觉系统：retro-arcade × editorial（Pixelify Sans + Hanken Grotesk + JetBrains Mono，amber on near-black）
- 双层排印分级：Pixelify 顶层 hero + 大数字 scoreboard；Hanken `tracking-tight + weight 600` 用在中层 section/sub-tab
- Result 页改 **3-Act 叙事**：Act I 你的 taste · Act II 你会爱的游戏 · Act III 安静被淘汰的
- Act I 新增纯 SVG 自实现 `TagRadar`（无图表库依赖）

### Phase 6.6: 推荐归因修正（✅ 完成）

- `explain()` 重写为闭式分解 + closest-fit slot（详见 §6.8）
- 副作用：干掉了大库下的 N 次 SQL tag 查询，纯 in-memory 稀疏点积

### Phase 7+（未做，方向再扩才考虑）

- README + 截图 + portfolio writeup（**目前最高优先级 TODO**）
- 价格 / 评论分析、UMAP 2D taste map、协同过滤、多语言 i18n

## 10. MVP Definition

MVP 完成的标志：

- Demo Mode 可用，无需 Steam 账号即可体验
- 真实 Steam ID 可输入，拉到库，画出 Taste Profile
- 至少一个推荐 query 工作（Best Fit）
- Library Regret 检测出至少一个簇
- 推荐有可读的"为什么"解释

MVP 不需要：

- Steam OpenID 登录（公开 profile 直输 SteamID 即可）
- 价格信息
- 评论摘要
- LLM
- UMAP 散点图（雷达图 + 列表先用着）
- Tag co-occurrence embedding（Phase 4+ 加深度时再做）
- Bayesian confidence（Phase 5+）

## 11. Complete Vision

完整版支持：

- 4 个核心功能完整：Taste Profile / Recs / Similar / Regret
- Steam OpenID 登录
- 5 个 similar query 维度
- UMAP 2D taste map 可视化
- Demo Mode（含多个预设玩家库）
- 部署在线 + 自定义域名

## 12. Portfolio Angle

简历卖点：

```text
- 实验对比 6 种 game-similarity 方法（transformer embedding / TF-IDF /
  tag Jaccard 等），实证 tag-based 方法在该问题上比 transformer 嵌入
  高 30 个百分点（Phase 0）
- 三路检索消融（Phase 4 / 4+）：TF-IDF 基线 83.2% → 自训练 PPMI+SVD
  tag embedding 85.6% → 自训练 InfoNCE dual encoder 81.1%（小语料 +
  高质量 tag 信号下对比学习不优于矩阵分解，与 Levy & Goldberg 2014
  理论预测一致），生产线选用 PPMI
- 多层 Taste Engine：TF-IDF tag 余弦 → playtime-weighted user vector
  → HDBSCAN library clustering → 自训练 tag co-occurrence embedding
- 推荐归因可解释：把推荐 cosine 做闭式单游戏分解（log(1+hours) ×
  cosine），并新增 "closest fit" slot 解决高时长宽 tag 游戏霸占
  归因的问题
- Library Regret 检测：揭示 Steam 出于商业利益不会展示的用户消费模式洞察
- 全栈：FastAPI + SQLite + React + Tailwind，runtime 镜像 < 200 MB；
  PyTorch 仅在离线训练脚本里
```

中文面试解释：

```text
我做了一个 Steam 玩家品味透镜。它不和 Steam 比推荐准确度——Steam 有几亿用户的协同
过滤数据，纯准确度我们做不过。我们做的是 Steam 不愿意做的事：揭示玩家自己的消费
模式，给可解释的推荐，按"类似但更慢/更轻松"等多维度查询，还能告诉你哪些类型你买
了但其实玩不下去（Library Regret）。

技术上我做了一个对比实验：测了 transformer 嵌入、TF-IDF、tag Jaccard 等 6 种方法
做 game-game 相似度。发现 tag-based 方法比 transformer 嵌入高 30 个百分点——因为
游戏描述里的营销文案污染了语义信号，而 Steam 的众标 tag 已经是用户提炼好的关键词。

基于这个发现设计了多层架构：底层 TF-IDF tag 余弦，用户层 playtime-weighted taste
vector，聚类层 HDBSCAN 识别 Library Regret 簇，加深层是从 corpus 自训练的 tag
co-occurrence embedding（解决 "Rogue-like" / "Rogue-lite" 同义词问题）。
```

英文版：

```text
Built Playprint, a Steam taste lens with a multi-layer architecture:
  1) TF-IDF tag cosine similarity (outperformed transformer embeddings
     by 30pp on game-game similarity in a 6-way Phase 0 ablation)
  2) Playtime-weighted user taste vector in tag space
  3) HDBSCAN library clustering for regret detection
  4) Self-trained PPMI + SVD tag embedding for synonym merging (+2.4pp
     merged hit rate on probe vs TF-IDF baseline; productionized)
  5) Three-way retrieval ablation including an InfoNCE-trained dual
     encoder — honest finding: contrastive learning did NOT beat the
     SPPMI matrix-factorization baseline on this small corpus, matching
     Levy & Goldberg 2014's theoretical prediction
Recommendation attribution decomposes the cosine into a per-game share
(log-playtime × cosine), plus a "closest fit" slot to prevent broad
high-playtime games from monopolizing every explanation. Library Regret
surfaces consumption patterns Steam's commercially-aligned recommender
will not show. Runtime: FastAPI + SQLite + React, <200MB image; PyTorch
only in offline training scripts.
```

## 13. Risks and Constraints

### Tag Coverage on Long Tail（New Top Risk）

✅ 原 Top Risk "Embedding Quality" 已通过 Phase 0 实验解决——发现 tag-based 方法在 game-game 相似度上比 transformer embedding 高 30%，且简化了 stack。

**新 Top Risk**：5000 款热门 corpus 之外，**长尾 / 极新 / 极冷门**游戏 SteamSpy tag 数据可能不足或缺失。

应对：
- 用户库中无 tag 数据的游戏直接跳过（不影响 taste vector，只是少一份证据）
- 用户库 corpus 命中 < 50% 时 UI 显示"画像可能不完整"
- 第二期 corpus 扩到 15000 款覆盖更多长尾
- Phase 4+ tag co-occurrence embedding 可以做语义扩展（用临近 tag 补全）

### Corpus Coverage

与 Top Risk 相关。5000 款热门覆盖大部分用户库，但长尾用户（冷门 / 独立 / VR 多）命中率可能低。详见上一条。

### Steam Profile Privacy

部分用户资料私密。

应对：
- 明确指引开启公开
- Demo Mode 兜底
- 后续接入 OpenID 登录

### Steam Store API Rate Limit

抓 5000 款需 2-3 小时分批跑。一次性可接受。

### Cold Start (Small Libraries)

用户库 < 20 款时 centroid 不稳。

应对：
- 置信度阈值 + UI 标注
- 引导用户手选喜欢的游戏作为种子

### Training Component（Phase 4 / 4+ 完成后定稿）

项目有**两个真正的训练步骤**：

1. **Phase 4 — PPMI + SVD tag embedding**（生产已用）：从 5000 款 corpus 的 tag-tag
   共现矩阵自学 50 维 tag 表示空间，numpy SVD 实现，无 torch。同义词合并通过，probe
   集 +2.4pp。

2. **Phase 4+ — InfoNCE 训练的 dual encoder**（消融用，未上生产）：PyTorch MLP 编码器，
   in-batch negatives + 温度 0.15，~10 万对正样本，Phase 0 probe 集 held out。**消融
   结果：trained 比 TF-IDF 基线低 2.1pp，比 PPMI 低 4.5pp**。

其他层（TF-IDF / cosine / HDBSCAN）都是统计计算，不是训练。

面试解释要诚实：**两个训练组件，一个赢了基线、一个输给了基线，二者都被诚实保留并报告**。
卖点不是"做了 SOTA"，是"实验驱动 + 在该数据规模和信号质量下，对比学习不优于矩阵分解，
且我们承认并写进了 portfolio"。这比假装训练赢了更可信。

## 14. Current Status & Next Step

**项目已上线**：[playprint](https://steam-taste.vercel.app) + [API](https://steam-taste.onrender.com)。
Phase 0 → Phase 4+ → Phase 6.6 全部完成，详见 §9。

**当前最高优先级**：portfolio writeup。

1. **README.md**（仓库首页空的）
   - 三张截图：Act I taste 雷达 / Act II rec 卡 / Act III regret 报告
   - 一句话定位 + 公开 demo 链接
   - 三路检索消融结果表（TF-IDF / PPMI / trained 的诚实对比）
   - 本地启动指南
   - 技术栈徽章

2. **简历段落定稿**（已有素材在 §12，但需要数字化）
   - 实际成绩补充："1095 款真实库 → 62 簇 + 45 regret patterns + 311 sleeping games"
   - 三路消融的具体数字

**次要优先级**：
- Render 冷启动应对（uptimerobot 心跳，或前端 Home 页静默预热）
- Phase 5（Bayesian + multi-query），如果有时间深化算法层
- Demo Mode 多个预设玩家（拓展叙事性）

**已知小问题**：narrow viewport 雷达图 label 内边距、`explain()` 3 元组签名兼容性，
详见 HANDOFF.md §11。
