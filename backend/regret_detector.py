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
from typing import Optional

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
            cluster.diagnosis = _build_diagnosis(cluster)
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


def _build_diagnosis(cluster: LibraryCluster) -> str:
    """Template diagnosis. Two variants:

      - pure regret: nothing in the cluster stuck — outright avoid this genre
      - mixed regret: one or two games stuck big, but rest didn't — the user
        found their fix and shouldn't keep buying same-genre
    """
    n = len(cluster.games)
    med = cluster.median_playtime_hours
    top_tags = ", ".join(cluster.dominant_tags[:3]) if cluster.dominant_tags else "?"

    if cluster.regret_kind == "mixed":
        # Identify the "true love" (highest playtime) + the untouched count
        winners = [g for g in cluster.games if g[2] / 60 >= MIXED_REGRET_HIGH_PLAYTIME_H]
        winner_str = ", ".join(f"{name} ({pt/60:.0f}h)" for _, name, pt in winners[:2])
        untouched = sum(1 for _, _, pt in cluster.games if pt / 60 < 1.0)
        return (
            f"你已经在这个类型里找到真爱：{winner_str}。\n"
            f"  但你库里还有 {n - len(winners)} 款同类游戏（其中 {untouched} 款几乎没碰）。\n"
            f"  主要标签: {top_tags}\n"
            f"  建议: 你已经有了这个类型的代表作，再买同类基本不会动。"
        )

    # Pure regret
    reps = ", ".join(f"{name} ({pt/60:.1f}h)" for _, name, pt in cluster.games[:3])
    return (
        f"你拥有 {n} 款此类游戏，中位时长仅 {med:.1f} 小时。\n"
        f"  主要标签: {top_tags}\n"
        f"  代表游戏: {reps}\n"
        f"  建议: 这个类型不适合你，未来别再买。"
    )


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
