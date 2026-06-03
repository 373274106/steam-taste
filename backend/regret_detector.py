"""Library Regret detector — Phase 3.

Clusters a user's Steam library in TF-IDF tag space using HDBSCAN, then
identifies clusters where the median playtime is low. These are "regret
clusters" — games the user repeatedly bought from a category but doesn't
actually enjoy playing.

This is the centerpiece insight Steam will never surface: it actively
discourages purchases in those categories rather than encouraging more.

Algorithm:
  1. For each library game in corpus, fetch its TF-IDF row → library matrix
  2. HDBSCAN cluster (euclidean on L2-normalized = cosine equivalent)
  3. Per cluster:
     - median_playtime_hours
     - dominant tags (cluster centroid argmax in vocab space)
     - representative games (highest playtime in cluster)
  4. Flag clusters where median < REGRET_THRESHOLD_HOURS
  5. Also surface "sleeping" games: any game with < 0.5h playtime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Callable, Optional

import numpy as np
from sklearn.cluster import HDBSCAN

from .taste_engine import TasteEngine


REGRET_THRESHOLD_HOURS = 5.0     # median playtime below this = potential regret
SLEEPING_THRESHOLD_MIN = 30      # bought but played < 30min = "sleeping"
MIN_CLUSTER_SIZE = 3             # HDBSCAN: don't flag a cluster smaller than this
MIXED_REGRET_HIGH_PLAYTIME_H = 20.0   # if max in cluster >= this, classify as MIXED, not pure

# Tags that indicate the "cluster" is software/tools, not games. Valve marks
# many of these as type='game' (Wallpaper Engine etc), so we exclude by tag.
NON_GAME_TAGS = {
    "Utilities", "Software", "Software Training",
    "Animation & Modeling", "Design & Illustration",
    "Audio Production", "Video Production", "Photo Editing",
    "Web Publishing", "Game Development",
}


@dataclass
class LibraryCluster:
    label: int                                # HDBSCAN label; -1 means noise
    games: list[tuple[int, str, int]]         # (appid, name, playtime_minutes)
    dominant_tags: list[str]
    median_playtime_hours: float
    total_playtime_hours: float
    max_playtime_hours: float = 0.0
    is_regret: bool = False
    regret_kind: str = ""                     # "" | "pure" | "mixed"
    diagnosis: str = ""


@dataclass
class RegretReport:
    total_games: int
    games_in_corpus: int
    clusters: list[LibraryCluster] = field(default_factory=list)
    regret_clusters: list[LibraryCluster] = field(default_factory=list)
    sleeping_games: list[tuple[int, str, int]] = field(default_factory=list)


def detect_regret(
    engine: TasteEngine,
    library: list[tuple[int, int]],
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    regret_threshold_hours: float = REGRET_THRESHOLD_HOURS,
    lang: str = "zh",
) -> RegretReport:
    """Run the full pipeline against a library."""
    report = RegretReport(total_games=len(library), games_in_corpus=0)

    # Filter to true games we have TF-IDF for (skip DLC / software / soundtracks)
    in_corpus: list[tuple[int, int, int]] = []   # (appid, playtime_min, row_idx)
    for appid, playtime_min in library:
        row = engine.appid_to_row.get(appid)
        if row is None:
            continue
        if not engine.is_game(appid):
            continue
        in_corpus.append((appid, int(playtime_min), row))
    report.games_in_corpus = len(in_corpus)

    if len(in_corpus) < min_cluster_size:
        # Too small to cluster meaningfully
        return _finalize_with_sleeping(report, in_corpus, engine)

    # Stack library vectors
    row_indices = [r for _, _, r in in_corpus]
    library_matrix = engine.tfidf[row_indices].toarray()

    # HDBSCAN — euclidean on L2-normalized vectors is monotone w.r.t. cosine
    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=1,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(library_matrix)

    # Bundle into clusters
    by_label: dict[int, list[int]] = {}
    for i, lbl in enumerate(labels):
        by_label.setdefault(int(lbl), []).append(i)

    # Preload names
    appids_in_corpus = [a for a, _, _ in in_corpus]
    engine._load_meta_batch(appids_in_corpus)

    for lbl, members_idx in by_label.items():
        if lbl == -1:
            # Noise — emit as one "noise cluster" but don't tag as regret
            games = [
                (in_corpus[i][0],
                 engine._meta_cache.get(in_corpus[i][0], ("?",))[0],
                 in_corpus[i][1])
                for i in members_idx
            ]
            cluster = LibraryCluster(
                label=-1,
                games=games,
                dominant_tags=[],
                median_playtime_hours=median(p / 60 for _, _, p in games),
                total_playtime_hours=sum(p / 60 for _, _, p in games),
            )
            report.clusters.append(cluster)
            continue

        # Build cluster
        games = [
            (in_corpus[i][0],
             engine._meta_cache.get(in_corpus[i][0], ("?",))[0],
             in_corpus[i][1])
            for i in members_idx
        ]
        playtimes_hours = [p / 60 for _, _, p in games]
        med = median(playtimes_hours)
        total = sum(playtimes_hours)
        max_h = max(playtimes_hours) if playtimes_hours else 0.0

        # Dominant tags = cluster centroid argmax in vocab space
        centroid = library_matrix[members_idx].mean(axis=0)
        top_tag_cols = np.argsort(centroid)[-6:][::-1]
        dominant = [engine.vocab[c] for c in top_tag_cols if centroid[c] > 0]

        # Exclude software/tool clusters (Valve mis-types some non-games as games)
        is_software_cluster = any(t in NON_GAME_TAGS for t in dominant[:3])

        is_regret = (
            med < regret_threshold_hours
            and len(games) >= min_cluster_size
            and not is_software_cluster
        )
        # Classify: did the user find a "true love" in this cluster?
        regret_kind = ""
        if is_regret:
            regret_kind = "mixed" if max_h >= MIXED_REGRET_HIGH_PLAYTIME_H else "pure"

        cluster = LibraryCluster(
            label=int(lbl),
            games=sorted(games, key=lambda g: -g[2]),  # sort by playtime desc
            dominant_tags=dominant,
            median_playtime_hours=med,
            total_playtime_hours=total,
            max_playtime_hours=max_h,
            is_regret=is_regret,
            regret_kind=regret_kind,
        )

        if is_regret:
            cluster.diagnosis = _build_diagnosis(cluster, lang=lang)
            report.regret_clusters.append(cluster)
        report.clusters.append(cluster)

    # Sleeping games: any game with very low playtime (regardless of cluster)
    for appid, playtime_min, _ in in_corpus:
        if playtime_min < SLEEPING_THRESHOLD_MIN:
            name = engine._meta_cache.get(appid, ("?",))[0]
            report.sleeping_games.append((appid, name, playtime_min))
    report.sleeping_games.sort(key=lambda g: g[2])

    return report


def _finalize_with_sleeping(
    report: RegretReport,
    in_corpus: list[tuple[int, int, int]],
    engine: TasteEngine,
) -> RegretReport:
    """For tiny libraries — skip clustering but still surface sleeping games."""
    appids = [a for a, _, _ in in_corpus]
    engine._load_meta_batch(appids)
    for appid, playtime_min, _ in in_corpus:
        if playtime_min < SLEEPING_THRESHOLD_MIN:
            name = engine._meta_cache.get(appid, ("?",))[0]
            report.sleeping_games.append((appid, name, playtime_min))
    return report


# ============================================================
# Diagnosis text generation (template pool + domain awareness)
# ============================================================

# Tag families that signal a genre cluster — used by B-tier domain-specific
# pure-regret templates. Match is by **any tag in signature** appearing in the
# cluster's top dominant tags. Order matters: first match wins. Keep these
# clusters narrow and confident — a vague match produces worse diagnosis text
# than the generic fallback.
_DOMAIN_SIGNATURES: list[tuple[str, set[str]]] = [
    ("survival_craft", {"Survival", "Crafting", "Base Building",
                        "Open World Survival Craft", "Resource Management"}),
    ("grand_strategy", {"4X", "Grand Strategy", "Turn-Based Strategy",
                        "Wargame", "Political"}),
    ("souls_like",     {"Souls-like"}),
    ("roguelite",      {"Rogue-lite", "Rogue-like", "Roguelike Deckbuilder",
                        "Action Roguelike"}),
    ("horror",         {"Horror", "Psychological Horror", "Survival Horror"}),
    ("jrpg",           {"JRPG", "Visual Novel", "Anime"}),
    ("cozy",           {"Cozy", "Relaxing", "Cute", "Wholesome"}),
    ("simulation",     {"Simulation", "Management", "City Builder",
                        "Tycoon", "Automation", "Farming Sim"}),
    ("shmup",          {"Bullet Hell", "Shoot 'Em Up", "Twin Stick Shooter"}),
]


def _classify_domain(dominant_tags: list[str]) -> str | None:
    """Map a cluster's dominant tags to a known genre family, if any. Looks
    only at the top 4 dominant tags to avoid spurious matches in long tag
    lists, and returns the first family with any tag intersection."""
    top = set(dominant_tags[:4])
    for domain, signature in _DOMAIN_SIGNATURES:
        if top & signature:
            return domain
    return None


@dataclass
class _DiagTemplate:
    """A diagnosis template paired with a selector and bilingual bodies.

    `selector(ctx)` returns True if this template applies to the cluster.
    Bodies are `str.format`-strings consuming the same context dict.
    """
    name: str
    selector: Callable[[dict], bool]
    zh: str
    en: str

    def render(self, ctx: dict, lang: str) -> str:
        body = self.en if lang == "en" else self.zh
        return body.format(**ctx)


def _diag_context(cluster: LibraryCluster) -> dict:
    """Build the shared template context. Computes everything any template
    might need; templates pick the fields they care about."""
    n = len(cluster.games)
    med = cluster.median_playtime_hours
    top_tags = ", ".join(cluster.dominant_tags[:3]) if cluster.dominant_tags else "?"
    reps_str = ", ".join(f"{name} ({pt/60:.1f}h)" for _, name, pt in cluster.games[:3])
    domain = _classify_domain(cluster.dominant_tags)

    ctx = {
        "n": n,
        "med": med,
        "top_tags": top_tags,
        "reps_str": reps_str,
        "domain": domain,
    }

    if cluster.regret_kind == "mixed":
        winners = [g for g in cluster.games
                   if g[2] / 60 >= MIXED_REGRET_HIGH_PLAYTIME_H]
        winner_count = len(winners)
        anchor_name, anchor_hours = (
            (winners[0][1], winners[0][2] / 60) if winners else ("?", 0.0)
        )
        rest_n = n - winner_count
        untouched = sum(1 for _, _, pt in cluster.games if pt / 60 < 1.0)
        ctx.update({
            "winners": winners,
            "winner_str": ", ".join(f"{name} ({pt/60:.0f}h)"
                                    for _, name, pt in winners[:2]),
            "winner_count": winner_count,
            "anchor_name": anchor_name,
            "anchor_hours": anchor_hours,
            "rest_n": rest_n,
            "untouched": untouched,
            "untouched_ratio": (untouched / rest_n) if rest_n > 0 else 0.0,
        })
    return ctx


# ----- Mixed-regret templates (first match wins) -----
_MIXED_TEMPLATES: list[_DiagTemplate] = [
    _DiagTemplate(
        name="single_anchor_deep",
        selector=lambda c: c["winner_count"] == 1 and c["anchor_hours"] >= 100,
        zh=(
            "{anchor_name} 一款 {anchor_hours:.0f}h——这就是你跟这个类型的全部关系。\n"
            "  库里还有 {rest_n} 款同类，其中 {untouched} 款几乎没碰。\n"
            "  主要标签: {top_tags}\n"
            "  建议: {anchor_name} 已经替你 cover 了这个类型，新作除非有颠覆性突破否则别买。"
        ),
        en=(
            "{anchor_name} at {anchor_hours:.0f}h — that's the whole relationship with this genre.\n"
            "  {rest_n} more sit in the same lane, {untouched} barely touched.\n"
            "  Main tags: {top_tags}\n"
            "  Verdict: {anchor_name} already covers this genre. Skip the rest unless something truly innovates."
        ),
    ),
    _DiagTemplate(
        name="high_untouched_ratio",
        selector=lambda c: c["rest_n"] > 0 and c["untouched_ratio"] >= 0.7,
        zh=(
            "你已经在这个类型里找到真爱：{winner_str}。\n"
            "  库里还囤了 {rest_n} 款同类，其中 {untouched} 款几乎是 0h——这是 wishlist 购物，不是想玩。\n"
            "  主要标签: {top_tags}\n"
            "  建议: 这个类型你已经吃饱了。下次看到「我会喜欢」请提醒自己已经买过 {rest_n} 次了。"
        ),
        en=(
            "You found what you love here: {winner_str}.\n"
            "  But {rest_n} more sit on the shelf, {untouched} at ~0h — that's wishlist shopping, not appetite.\n"
            "  Main tags: {top_tags}\n"
            "  Verdict: You've had your fill. Next time something looks tempting, remember you've already bought it {rest_n} times."
        ),
    ),
    _DiagTemplate(
        name="saturation",
        selector=lambda c: c["n"] >= 6,
        zh=(
            "你已经把这个类型玩透了：{winner_str}。\n"
            "  库里还有 {rest_n} 款同类。再买等于买重复票。\n"
            "  主要标签: {top_tags}\n"
            "  建议: 这个类型你已经够了，转头看看完全不同的方向更可能有惊喜。"
        ),
        en=(
            "You've already gone deep here: {winner_str}.\n"
            "  {rest_n} more sit in the library — buying another is buying a ticket to a movie you've seen.\n"
            "  Main tags: {top_tags}\n"
            "  Verdict: Try something outside this lane. Higher odds of surprise."
        ),
    ),
    _DiagTemplate(
        name="mixed_classic",
        selector=lambda c: True,
        zh=(
            "你已经在这个类型里找到真爱：{winner_str}。\n"
            "  但你库里还有 {rest_n} 款同类游戏（其中 {untouched} 款几乎没碰）。\n"
            "  主要标签: {top_tags}\n"
            "  建议: 你已经有了这个类型的代表作，再买同类基本不会动。"
        ),
        en=(
            "You found your favorite here: {winner_str}.\n"
            "  But {rest_n} more games sit there ({untouched} essentially untouched).\n"
            "  Main tags: {top_tags}\n"
            "  Verdict: You already have the one. More of the same won't get played."
        ),
    ),
]


# ----- Pure-regret domain-specific templates (B-tier) -----
# Selectors here only check the domain key. They're picked by domain lookup
# in `_build_diagnosis`, not by scanning the pool.
_PURE_DOMAIN_TEMPLATES: dict[str, _DiagTemplate] = {
    "survival_craft": _DiagTemplate(
        name="survival_craft",
        selector=lambda c: True,
        zh=(
            "{n} 款生存建造游戏，中位时长 {med:.1f}h——这类玩法靠时间堆出成就感，"
            "你给不出前 10 小时的投入。\n"
            "  代表: {reps_str}\n"
            "  建议: 「投入时间换收获」不是你的循环。下次想买请先问自己：愿意为这盘第一晚牺牲什么？"
        ),
        en=(
            "{n} survival-craft titles at {med:.1f}h median — the payoff comes slowly and "
            "you don't pay the first 10 hours.\n"
            "  Top: {reps_str}\n"
            "  Verdict: 'Time-as-reward' isn't your loop. Ask before buying: would you give the first night to this?"
        ),
    ),
    "grand_strategy": _DiagTemplate(
        name="grand_strategy",
        selector=lambda c: True,
        zh=(
            "{n} 款 4X / 大策略，中位时长 {med:.1f}h——学习曲线把你劝退在了开局 5 小时内。\n"
            "  代表: {reps_str}\n"
            "  建议: 你需要的是「开局就能进入心流」的策略，不是「读 50 页 wiki 才能开始」的那种。"
        ),
        en=(
            "{n} 4X / grand-strategy titles at {med:.1f}h median — the learning curve kicks you out before hour 5.\n"
            "  Top: {reps_str}\n"
            "  Verdict: You want strategy that flows from minute one, not strategy that demands a 50-page wiki."
        ),
    ),
    "souls_like": _DiagTemplate(
        name="souls_like",
        selector=lambda c: True,
        zh=(
            "{n} 款魂系游戏，中位时长 {med:.1f}h——你被「硬核」标签吸引，但实际死 5 次就关了。\n"
            "  代表: {reps_str}\n"
            "  建议: 你想要的是「克服困难」的故事，不是真的去克服。找类魂氛围 + 难度可调的会更合适。"
        ),
        en=(
            "{n} souls-like titles at {med:.1f}h median — the 'hardcore' label draws you in, but five deaths and you bail.\n"
            "  Top: {reps_str}\n"
            "  Verdict: You want the story of overcoming hard things, not the act. Look for souls-flavored games with adjustable difficulty."
        ),
    ),
    "roguelite": _DiagTemplate(
        name="roguelite",
        selector=lambda c: True,
        zh=(
            "{n} 款 roguelite，中位时长 {med:.1f}h——「随机性 + 重玩价值」吸引你买入，但前 5 局还没尝到甜头就走了。\n"
            "  代表: {reps_str}\n"
            "  建议: roguelite 的 reward loop 需要 10 小时才打开，你给不出这个起步成本。"
        ),
        en=(
            "{n} roguelite titles at {med:.1f}h median — 'randomness + replayability' got you to buy, but you bail before the first sweet run.\n"
            "  Top: {reps_str}\n"
            "  Verdict: Roguelite loops take ~10h to unlock. You don't pay that startup cost."
        ),
    ),
    "horror": _DiagTemplate(
        name="horror",
        selector=lambda c: True,
        zh=(
            "{n} 款 horror，中位时长 {med:.1f}h——氛围在 trailer 里很吸引人，但单人 horror 你顶不住。\n"
            "  代表: {reps_str}\n"
            "  建议: 这类游戏你应该看主播，不是自己玩。"
        ),
        en=(
            "{n} horror titles at {med:.1f}h median — the atmosphere reads great in trailers, but alone you bail.\n"
            "  Top: {reps_str}\n"
            "  Verdict: This is a watch-streamers genre for you, not a play-yourself one."
        ),
    ),
    "jrpg": _DiagTemplate(
        name="jrpg",
        selector=lambda c: True,
        zh=(
            "{n} 款 JRPG / 视觉小说，中位时长 {med:.1f}h——想看剧情，但 40-80h 的承诺你给不出。\n"
            "  代表: {reps_str}\n"
            "  建议: 找剧情吃掉时长更短的（10-15h），或者直接看动画 / 看 LP，而不是自己开档。"
        ),
        en=(
            "{n} JRPG / visual novel titles at {med:.1f}h median — you want the story but won't commit 40-80h to get it.\n"
            "  Top: {reps_str}\n"
            "  Verdict: Look for tight-narrative games (10-15h), or just watch the anime / let's-play."
        ),
    ),
    "cozy": _DiagTemplate(
        name="cozy",
        selector=lambda c: True,
        zh=(
            "{n} 款治愈 / 休闲游戏，中位时长 {med:.1f}h——你以为自己想要放松，但其实需要的是刺激。\n"
            "  代表: {reps_str}\n"
            "  建议: 治愈类不是你的解压方式，你需要的是「赢一把」的多巴胺，不是「种一片地」的慢循环。"
        ),
        en=(
            "{n} cozy / relaxing titles at {med:.1f}h median — you think you want to unwind, but actually want stimulation.\n"
            "  Top: {reps_str}\n"
            "  Verdict: Cozy isn't your decompression. You want a win-rush, not a slow-grow loop."
        ),
    ),
    "simulation": _DiagTemplate(
        name="simulation",
        selector=lambda c: True,
        zh=(
            "{n} 款模拟 / 经营，中位时长 {med:.1f}h——概念让你着迷（开公司！开餐厅！开城市！），"
            "实际操作起来 spreadsheet 让你犯困。\n"
            "  代表: {reps_str}\n"
            "  建议: 你买的是「成为另一个职业」的幻想，不是真的想做表。看看带模拟元素但节奏更紧的游戏。"
        ),
        en=(
            "{n} sim / management titles at {med:.1f}h median — the fantasy fascinates "
            "(run a company! a city!), but the spreadsheets put you to sleep.\n"
            "  Top: {reps_str}\n"
            "  Verdict: You bought the 'become another profession' daydream, not the desire to actually do bookkeeping. Look for sim-flavored games with tighter pacing."
        ),
    ),
    "shmup": _DiagTemplate(
        name="shmup",
        selector=lambda c: True,
        zh=(
            "{n} 款弹幕 / shmup，中位时长 {med:.1f}h——美术风格让你点了购买，但实际反射神经的要求你受不了。\n"
            "  代表: {reps_str}\n"
            "  建议: 这是「买美术」型购买。看看同美术方向但节奏可控的（例如视觉小说 + 弹幕氛围混合品）。"
        ),
        en=(
            "{n} shmup / bullet-hell titles at {med:.1f}h median — the art got you to buy, but the reflex demands burn you out.\n"
            "  Top: {reps_str}\n"
            "  Verdict: This is art-driven purchasing. Look for the same aesthetic in slower-paced games."
        ),
    ),
}


# ----- Pure-regret quantitative fallbacks (when domain doesn't match) -----
_PURE_FALLBACK_TEMPLATES: list[_DiagTemplate] = [
    _DiagTemplate(
        name="stockpile",
        selector=lambda c: c["n"] >= 8,
        zh=(
            "{n} 款此类游戏，中位时长仅 {med:.1f}h——这不是少数失误，是模式。\n"
            "  主要标签: {top_tags}\n"
            "  代表: {reps_str}\n"
            "  建议: 你对这个类型的购买冲动 > 实际兴趣。下次看到同类，先把这 {n} 款打开试试再决定。"
        ),
        en=(
            "{n} titles in this genre at {med:.1f}h median — this isn't a couple of misses, it's a pattern.\n"
            "  Main tags: {top_tags}\n"
            "  Top: {reps_str}\n"
            "  Verdict: Your buying urge for this genre runs ahead of your actual interest. Next time, open one of the {n} you already own first."
        ),
    ),
    _DiagTemplate(
        name="never_opened",
        selector=lambda c: c["med"] < 0.5,
        zh=(
            "{n} 款此类游戏，中位时长 {med:.1f}h——基本是一打开就关。\n"
            "  主要标签: {top_tags}\n"
            "  代表: {reps_str}\n"
            "  建议: 这个类型在你脑海里的样子和实际玩起来的样子是两回事。承认这一点，未来 hard skip。"
        ),
        en=(
            "{n} titles in this genre at {med:.1f}h median — you open, you close.\n"
            "  Main tags: {top_tags}\n"
            "  Top: {reps_str}\n"
            "  Verdict: The version of this genre in your head isn't the one that actually exists. Accept that, hard-skip next time."
        ),
    ),
    _DiagTemplate(
        name="pure_classic",
        selector=lambda c: True,
        zh=(
            "你拥有 {n} 款此类游戏，中位时长仅 {med:.1f} 小时。\n"
            "  主要标签: {top_tags}\n"
            "  代表游戏: {reps_str}\n"
            "  建议: 这个类型不适合你，未来别再买。"
        ),
        en=(
            "You own {n} titles in this genre, median playtime {med:.1f}h.\n"
            "  Main tags: {top_tags}\n"
            "  Top: {reps_str}\n"
            "  Verdict: This genre doesn't fit you. Don't keep buying it."
        ),
    ),
]


def _build_diagnosis(cluster: LibraryCluster, lang: str = "zh") -> str:
    """Diagnose a regret cluster. Pipeline:

      1. Mixed regret → pick from `_MIXED_TEMPLATES` by selector (first match wins)
      2. Pure regret with recognized genre domain → use the domain-specific
         B-tier template (most informative because it names the *why*)
      3. Pure regret fallback → pick from `_PURE_FALLBACK_TEMPLATES` by selector

    `lang` is "zh" or "en". Defaults to zh for backward compat — i18n wires
    the API query param through to this argument in a later phase.
    """
    ctx = _diag_context(cluster)

    if cluster.regret_kind == "mixed":
        for tmpl in _MIXED_TEMPLATES:
            if tmpl.selector(ctx):
                return tmpl.render(ctx, lang)
        return ""  # unreachable — fallback always matches

    domain = ctx.get("domain")
    if domain and domain in _PURE_DOMAIN_TEMPLATES:
        return _PURE_DOMAIN_TEMPLATES[domain].render(ctx, lang)

    for tmpl in _PURE_FALLBACK_TEMPLATES:
        if tmpl.selector(ctx):
            return tmpl.render(ctx, lang)
    return ""  # unreachable


def _regret_severity(cluster: LibraryCluster) -> float:
    """Higher = more 'wasted' — used to rank which regret clusters to show first.

    Heuristic: size × (1 / (1 + median_hours)) — bigger pile of low-playtime
    games scores higher. A cluster of 8 games at 0.1h scores way above
    a cluster of 3 games at 4h.
    """
    return len(cluster.games) / (1.0 + cluster.median_playtime_hours)


def format_regret_report(
    engine: TasteEngine,
    report: RegretReport,
    max_regret_clusters: int = 10,
    max_sleeping_games: int = 15,
) -> str:
    """Pretty-print a RegretReport."""
    lines = []
    lines.append(f"\n{'=' * 70}")
    lines.append("LIBRARY REGRET REPORT")
    lines.append(f"{'=' * 70}")
    lines.append(f"Library size: {report.total_games}")
    lines.append(f"In corpus:    {report.games_in_corpus} ({report.games_in_corpus / max(1, report.total_games) * 100:.0f}%)")
    lines.append("")

    # Cluster overview
    real_clusters = [c for c in report.clusters if c.label != -1]
    lines.append(f"Identified {len(real_clusters)} taste clusters + "
                 f"{sum(1 for c in report.clusters if c.label == -1 for _ in c.games)} unclustered (noise) games\n")

    for c in sorted(real_clusters, key=lambda x: -x.total_playtime_hours):
        marker = "[REGRET]" if c.is_regret else "[OK]    "
        lines.append(f"{marker} Cluster {c.label}: {len(c.games)} games, "
                     f"median {c.median_playtime_hours:.1f}h, total {c.total_playtime_hours:.1f}h")
        lines.append(f"  dominant tags: {', '.join(c.dominant_tags[:5])}")
        # Show top games + bottom 2 playtimes, avoiding overlap on small clusters
        if len(c.games) <= 5:
            for appid, name, pt in c.games:
                lines.append(f"    {name[:38]:38}  {pt/60:>6.1f}h")
        else:
            top_3 = c.games[:3]
            bot_2 = c.games[-2:]
            for appid, name, pt in top_3:
                lines.append(f"    {name[:38]:38}  {pt/60:>6.1f}h")
            lines.append(f"    ... and {len(c.games) - 5} more, ending with:")
            for appid, name, pt in bot_2:
                lines.append(f"    {name[:38]:38}  {pt/60:>6.1f}h")
        lines.append("")

    # Regret diagnoses, ranked by severity, limited
    if report.regret_clusters:
        ranked = sorted(report.regret_clusters, key=_regret_severity, reverse=True)
        shown = ranked[:max_regret_clusters]
        hidden = len(ranked) - len(shown)

        pure_n = sum(1 for c in report.regret_clusters if c.regret_kind == "pure")
        mixed_n = sum(1 for c in report.regret_clusters if c.regret_kind == "mixed")

        lines.append(f"\n{'=' * 70}")
        lines.append(
            f"REGRET CLUSTERS ({len(report.regret_clusters)} total: "
            f"{pure_n} pure, {mixed_n} mixed — showing top {len(shown)} by severity)"
        )
        lines.append(f"{'=' * 70}")
        lines.append("  [PURE]   no game in this genre stuck — avoid future purchases")
        lines.append("  [MIXED]  found a true love but kept buying same-genre — stop")
        for i, c in enumerate(shown, 1):
            sev = _regret_severity(c)
            kind_tag = f"[{c.regret_kind.upper():<5}]"
            lines.append(f"\n#{i} {kind_tag}  severity {sev:.1f}  (cluster {c.label}):")
            lines.append(f"  {c.diagnosis}")
        if hidden > 0:
            lines.append(f"\n  ... and {hidden} more regret clusters (less severe)")
    else:
        lines.append("\nNo regret clusters detected. Your purchases align with your playtime — well done!")

    # Sleeping games
    if report.sleeping_games:
        lines.append(f"\n{'=' * 70}")
        lines.append(f"SLEEPING GAMES (< {SLEEPING_THRESHOLD_MIN} min played) — {len(report.sleeping_games)} total")
        lines.append(f"{'=' * 70}")
        for appid, name, pt in report.sleeping_games[:max_sleeping_games]:
            lines.append(f"  {name[:50]:50}  {pt:>4} min")
        if len(report.sleeping_games) > max_sleeping_games:
            lines.append(f"  ... and {len(report.sleeping_games) - max_sleeping_games} more")

    return "\n".join(lines)
