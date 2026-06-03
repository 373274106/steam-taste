"""Steam Taste Lens — core engine.

Layer 1-3 of the multi-layer architecture (see project md §6):
  - Layer 1: tag inverted index + TF-IDF (built offline by phase1_build_index.py)
  - Layer 2: game-game similarity (cosine on TF-IDF rows)
  - Layer 3: user taste vector (playtime-weighted sum) + recommendation queries

Higher layers (HDBSCAN regret, tag co-occurrence embedding, Bayesian confidence)
land in Phase 3, 4, 5 respectively.

This module is pure compute and SQLite reads — no Steam Web API calls.
Steam library fetching lives in backend/steam_client.py (Phase 2 Step B).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from math import log
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy import sparse


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"

DB_PATH = DATA_DIR / "corpus.db"
TFIDF_PATH = DATA_DIR / "tfidf.npz"
APPID_PATH = DATA_DIR / "appid_order.json"
VOCAB_PATH = DATA_DIR / "tag_vocab.json"


# ============================================================
# Data types
# ============================================================

@dataclass
class GameRef:
    """Minimal info about a game shown in results."""
    appid: int
    name: str
    header_image: str = ""
    tags: list[str] = None        # top tags by votes, for display


@dataclass
class Recommendation:
    game: GameRef
    score: float                  # cosine similarity [0, 1]
    shared_tags: list[str]        # tags contributing most to the match
    evidence_games: list[tuple[int, str, int]]  # (appid, name, playtime_min) from user's library


# ============================================================
# Engine — loads artifacts once, serves multiple queries
# ============================================================

class TasteEngine:
    """Loads index artifacts into memory. Thread-safe for reads."""

    def __init__(self,
                 db_path: Path = DB_PATH,
                 tfidf_path: Path = TFIDF_PATH,
                 appid_path: Path = APPID_PATH,
                 vocab_path: Path = VOCAB_PATH):
        self.db_path = db_path
        self.tfidf: sparse.csr_matrix = sparse.load_npz(tfidf_path)
        self.appid_order: list[int] = json.loads(appid_path.read_text(encoding="utf-8"))
        self.appid_to_row: dict[int, int] = {a: i for i, a in enumerate(self.appid_order)}
        self.vocab: list[str] = json.loads(vocab_path.read_text(encoding="utf-8"))
        self.tag_to_col: dict[str, int] = {t: i for i, t in enumerate(self.vocab)}
        # Lazy-loaded metadata cache: appid -> (name, header_image, owners_low)
        self._meta_cache: dict[int, tuple[str, str, int]] = {}

    @property
    def corpus_size(self) -> int:
        return self.tfidf.shape[0]

    # ------------------------------------------------------------
    # Metadata lookups
    # ------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _load_meta_batch(self, appids: Iterable[int]) -> None:
        missing = [a for a in appids if a not in self._meta_cache]
        if not missing:
            return
        with self._conn() as c:
            placeholders = ",".join("?" * len(missing))
            cur = c.execute(
                f"SELECT appid, name, header_image, owners_low FROM games WHERE appid IN ({placeholders})",
                missing,
            )
            for appid, name, header, owners in cur.fetchall():
                self._meta_cache[appid] = (name or "", header or "", owners or 0)

    def name_of(self, appid: int) -> str:
        self._load_meta_batch([appid])
        return self._meta_cache.get(appid, ("", "", 0))[0]

    def top_tags_for_game(self, appid: int, k: int = 6) -> list[str]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT tag FROM game_tags WHERE appid = ? ORDER BY votes DESC LIMIT ?",
                (appid, k),
            )
            return [t for (t,) in cur.fetchall()]

    def game_ref(self, appid: int, include_tags: bool = True) -> GameRef:
        self._load_meta_batch([appid])
        name, header, _ = self._meta_cache.get(appid, ("?", "", 0))
        tags = self.top_tags_for_game(appid, 6) if include_tags else []
        return GameRef(appid=appid, name=name, header_image=header, tags=tags)

    # ------------------------------------------------------------
    # Layer 2: game-game similarity
    # ------------------------------------------------------------

    def _row(self, appid: int) -> sparse.csr_matrix | None:
        idx = self.appid_to_row.get(appid)
        if idx is None:
            return None
        return self.tfidf[idx]

    def _cosine_against_all(self, vec: sparse.csr_matrix) -> np.ndarray:
        """Cosine similarity between vec (1×V, normalized) and all corpus rows."""
        sims = self.tfidf @ vec.T            # (N, 1) sparse
        return np.asarray(sims.todense()).flatten()

    def similar_to_game(self, appid: int, k: int = 10, exclude: set[int] | None = None) -> list[tuple[int, float]]:
        """Find games most similar to `appid`. Returns [(appid, score), ...]."""
        row = self._row(appid)
        if row is None:
            return []
        sims = self._cosine_against_all(row)
        target_row = self.appid_to_row[appid]
        sims[target_row] = -1.0
        exclude = exclude or set()
        # Mask excluded
        for x in exclude:
            r = self.appid_to_row.get(x)
            if r is not None:
                sims[r] = -1.0
        top = np.argsort(sims)[-k:][::-1]
        return [(self.appid_order[i], float(sims[i])) for i in top]

    # ------------------------------------------------------------
    # Layer 3: user taste vector + recommendations
    # ------------------------------------------------------------

    def compute_taste_vector(
        self,
        library: list[tuple[int, int]],
    ) -> tuple[np.ndarray, dict]:
        """library = [(appid, playtime_minutes), ...]
        Returns (dense_vector_normalized, stats_dict).
        Games not in corpus are silently skipped (counted in stats).
        """
        V = self.tfidf.shape[1]
        taste = np.zeros(V, dtype=np.float64)
        n_total = len(library)
        n_in_corpus = 0
        total_weight = 0.0
        contributing: list[tuple[int, int, float]] = []  # (appid, playtime, weight)

        for appid, playtime_min in library:
            row_idx = self.appid_to_row.get(appid)
            if row_idx is None:
                continue
            hours = max(0.0, playtime_min / 60.0)
            # log(1 + hours) — keeps 0h at 0, but log-saturating after 100h
            w = log(1.0 + hours)
            if w <= 0:
                continue
            row = self.tfidf[row_idx]
            taste += w * row.toarray().flatten()
            total_weight += w
            n_in_corpus += 1
            contributing.append((appid, playtime_min, w))

        # L2 normalize
        norm = float(np.linalg.norm(taste))
        if norm > 0:
            taste /= norm

        stats = {
            "library_size": n_total,
            "in_corpus": n_in_corpus,
            "coverage": (n_in_corpus / n_total) if n_total else 0.0,
            "total_weight": total_weight,
            "confidence": min(1.0, n_in_corpus / 30.0),  # rough heuristic, see §6.6
            "contributing": contributing,
        }
        return taste, stats

    def top_taste_tags(self, taste_vec: np.ndarray, k: int = 10) -> list[tuple[str, float]]:
        """Identify the tag columns with the highest weights in the taste vector."""
        top_cols = np.argsort(taste_vec)[-k:][::-1]
        return [(self.vocab[c], float(taste_vec[c])) for c in top_cols if taste_vec[c] > 0]

    def recommend(
        self,
        taste_vec: np.ndarray,
        owned_appids: set[int],
        k: int = 10,
        mode: str = "best_fit",
        min_reviews: int = 50,
        min_quality: float = 0.65,
    ) -> list[tuple[int, float]]:
        """Find top-K games matching the taste vector. Applies:
          - owned filter (exclude games already in library)
          - type='game' filter (no DLC, software, demo, music)
          - min_reviews filter (kill unreliable signal)
          - min_quality filter (kill widely-disliked games)
          - mode-specific scoring tweak (hidden_gem / stretch / best_fit)
          - quality boost (soft preference for highly-rated games)
        """
        # tfidf @ taste = cosine since both normalized
        sims = self.tfidf @ taste_vec
        sims = np.asarray(sims).flatten()

        # 1. Exclude owned games
        for appid in owned_appids:
            row = self.appid_to_row.get(appid)
            if row is not None:
                sims[row] = -1.0

        # 2. Type filter: only true games
        sims = np.where(self._is_game_array(), sims, -1.0)

        # 3. Hard quality filters
        quality = self._quality_array()
        rev_count = self._review_count_array()
        sims = np.where(rev_count >= min_reviews, sims, -1.0)
        sims = np.where(quality >= min_quality, sims, -1.0)

        # 4. Mode tweaks
        if mode == "hidden_gem":
            popularity = self._popularity_array()
            sims = sims - 0.10 * np.log1p(popularity / 1_000_000)
        elif mode == "stretch":
            sims = sims * (1.0 - np.abs(sims - 0.55))
        # best_fit: no extra tweak

        # 5. Soft quality boost — multiply by (0.85 + 0.30 * quality) → range 1.04–1.15
        sims = np.where(sims > 0, sims * (0.85 + 0.30 * quality), sims)

        top = np.argsort(sims)[-k:][::-1]
        return [(self.appid_order[i], float(sims[i])) for i in top if sims[i] > 0]

    def _popularity_array(self) -> np.ndarray:
        """Per-row popularity (owners_low) cached. Loaded once."""
        self._ensure_extended_meta()
        return self._pop_arr

    def _quality_array(self) -> np.ndarray:
        """Per-row positive review ratio in [0,1]. Smoothed: 0 reviews -> 0.5."""
        self._ensure_extended_meta()
        return self._quality_arr

    def _review_count_array(self) -> np.ndarray:
        """Per-row total review count (positive + negative)."""
        self._ensure_extended_meta()
        return self._review_count_arr

    def _is_game_array(self) -> np.ndarray:
        """Per-row boolean: is the entry a 'game' (vs dlc/software/music/etc)."""
        self._ensure_extended_meta()
        return self._is_game_arr

    def is_game(self, appid: int) -> bool:
        """O(1) check whether an appid is a true game in the corpus."""
        self._ensure_extended_meta()
        return appid in self._game_appids_set

    def _ensure_extended_meta(self) -> None:
        """One-shot load of popularity, quality, review counts, and type from SQLite."""
        if hasattr(self, "_pop_arr"):
            return
        with self._conn() as c:
            placeholders = ",".join("?" * len(self.appid_order))
            cur = c.execute(
                f"SELECT appid, owners_low, positive_reviews, negative_reviews, type "
                f"FROM games WHERE appid IN ({placeholders})",
                self.appid_order,
            )
            rows = {a: (o or 0, p or 0, n or 0, t or "") for a, o, p, n, t in cur.fetchall()}

        pop = []
        quality = []
        rev_count = []
        is_game = []
        game_set: set[int] = set()
        for a in self.appid_order:
            o, p, n, t = rows.get(a, (0, 0, 0, ""))
            pop.append(o)
            total = p + n
            # Smoothed positive ratio: (p + 5) / (total + 10) — Laplace-style prior at 0.5
            quality.append((p + 5) / (total + 10))
            rev_count.append(total)
            is_g = (t == "game")
            is_game.append(is_g)
            if is_g:
                game_set.add(a)

        self._pop_arr = np.asarray(pop, dtype=np.float64)
        self._quality_arr = np.asarray(quality, dtype=np.float64)
        self._review_count_arr = np.asarray(rev_count, dtype=np.float64)
        self._is_game_arr = np.asarray(is_game, dtype=bool)
        self._game_appids_set = game_set

    # ------------------------------------------------------------
    # Explanation layer
    # ------------------------------------------------------------

    def explain(
        self,
        candidate_appid: int,
        taste_vec: np.ndarray,
        library: list[tuple[int, int]],
        max_shared_tags: int = 4,
        max_evidence: int = 2,
    ) -> tuple[list[str], list[tuple[int, str, int]]]:
        """Why was this game recommended?

        Returns:
          shared_tags  - high-affinity tags the candidate has that the user's taste has
          evidence     - user's games that contributed most: (appid, name, playtime_min)
        """
        cand_row = self._row(candidate_appid)
        if cand_row is None:
            return [], []
        cand_arr = cand_row.toarray().flatten()
        # Element-wise contribution = cand[tag] * taste[tag]
        contrib = cand_arr * taste_vec
        top_cols = np.argsort(contrib)[-max_shared_tags:][::-1]
        shared = [self.vocab[c] for c in top_cols if contrib[c] > 0]

        # Find which library games contributed most to those tags
        ev_scores: dict[int, float] = {}
        with self._conn() as c:
            cand_tags_set = set(shared)
            for appid, playtime_min in library:
                if appid == candidate_appid:
                    continue
                if appid not in self.appid_to_row:
                    continue
                # how many of the shared tags does this lib game have?
                cur = c.execute(
                    "SELECT tag FROM game_tags WHERE appid = ?",
                    (appid,),
                )
                lib_tags = {t for (t,) in cur.fetchall()}
                overlap = len(cand_tags_set & lib_tags)
                if overlap == 0:
                    continue
                hours = playtime_min / 60.0
                ev_scores[appid] = overlap * log(1.0 + hours)

        top_lib = sorted(ev_scores.items(), key=lambda kv: kv[1], reverse=True)[:max_evidence]
        evidence = []
        if top_lib:
            self._load_meta_batch([a for a, _ in top_lib])
            playtime_lookup = dict(library)
            for appid, _ in top_lib:
                name = self._meta_cache.get(appid, ("?",))[0]
                evidence.append((appid, name, playtime_lookup.get(appid, 0)))
        return shared, evidence


# ============================================================
# Convenience: format human-readable output
# ============================================================

def format_taste_profile(engine: TasteEngine, taste_vec: np.ndarray, stats: dict) -> str:
    top = engine.top_taste_tags(taste_vec, 12)
    lines = []
    lines.append(f"Library:  {stats['library_size']} games, "
                 f"{stats['in_corpus']} in corpus ({stats['coverage']*100:.0f}%)")
    lines.append(f"Confidence: {stats['confidence']:.2f}")
    lines.append("")
    lines.append("Top taste tags:")
    for tag, weight in top:
        bar = "#" * int(weight * 30 / max((w for _, w in top), default=1))
        lines.append(f"  {tag:<28}  {weight:.3f}  {bar}")
    return "\n".join(lines)


def format_recommendations(
    engine: TasteEngine,
    recs: list[tuple[int, float]],
    taste_vec: np.ndarray,
    library: list[tuple[int, int]],
    title: str = "Recommendations",
) -> str:
    lines = [f"\n=== {title} ==="]
    for appid, score in recs:
        ref = engine.game_ref(appid)
        shared, evidence = engine.explain(appid, taste_vec, library)
        lines.append(f"\n[{appid:>8}] {ref.name}  (score {score:.3f})")
        if ref.tags:
            lines.append(f"  tags:     {', '.join(ref.tags)}")
        if shared:
            lines.append(f"  matches:  {', '.join(shared)}")
        if evidence:
            ev_str = ", ".join(f"{n} ({p/60:.0f}h)" for _, n, p in evidence)
            lines.append(f"  because:  {ev_str}")
    return "\n".join(lines)
