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
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from math import log
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy import sparse


# Year currently used as the "now" reference for recency scoring. We use the
# corpus's most recent release year (computed lazily, so re-fetching new
# games shifts the curve automatically) and fall back to wall-clock UTC if
# the corpus is empty.
_YEAR_RE = re.compile(r"\b(19[7-9]\d|20[0-3]\d)\b")


def _parse_year(s: str | None) -> int | None:
    """Extract a 4-digit year from a Steam release_date string like
    'Nov 1, 2000' or 'Q4 2024'. Returns None when no plausible year fits."""
    if not s:
        return None
    m = _YEAR_RE.search(s)
    return int(m.group(1)) if m else None


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"

DB_PATH = DATA_DIR / "corpus.db"
TFIDF_PATH = DATA_DIR / "tfidf.npz"
APPID_PATH = DATA_DIR / "appid_order.json"
VOCAB_PATH = DATA_DIR / "tag_vocab.json"
TAG_EMBED_PATH = DATA_DIR / "tag_embedding.npy"
GAME_EMBED_PATH = DATA_DIR / "game_embedding.npy"


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
                 vocab_path: Path = VOCAB_PATH,
                 tag_embed_path: Path = TAG_EMBED_PATH,
                 game_embed_path: Path = GAME_EMBED_PATH):
        self.db_path = db_path
        self.tfidf: sparse.csr_matrix = sparse.load_npz(tfidf_path)
        self.appid_order: list[int] = json.loads(appid_path.read_text(encoding="utf-8"))
        self.appid_to_row: dict[int, int] = {a: i for i, a in enumerate(self.appid_order)}
        self.vocab: list[str] = json.loads(vocab_path.read_text(encoding="utf-8"))
        self.tag_to_col: dict[str, int] = {t: i for i, t in enumerate(self.vocab)}
        # Phase 4: self-trained tag co-occurrence embedding (PPMI + SVD).
        # Optional — engine still works if the npy file is missing.
        if tag_embed_path.exists():
            self.tag_embedding: np.ndarray | None = np.load(tag_embed_path).astype(np.float32)
        else:
            self.tag_embedding = None
        # Phase 4+: trained dual-encoder game embedding (InfoNCE).
        # Also optional; missing file leaves the field as None.
        if game_embed_path.exists():
            self.game_embedding: np.ndarray | None = np.load(game_embed_path).astype(np.float32)
        else:
            self.game_embedding = None
        # PPMI-based dense game embedding (lazily computed from tfidf @ tag_embedding).
        self._ppmi_game_embedding: np.ndarray | None = None
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
          - mode-specific scoring tweak (best_fit / hidden_gem / stretch / fresh_fit)
          - quality boost (soft preference for highly-rated games)
          - fresh_fit only: recency boost on top of the quality boost
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
        # best_fit / fresh_fit: no pre-quality tweak

        # 5. Soft quality boost — multiply by (0.85 + 0.30 * quality) → range 1.04–1.15
        sims = np.where(sims > 0, sims * (0.85 + 0.30 * quality), sims)

        # 6. fresh_fit recency multiplier — applied after quality so the two
        #    soft preferences stack instead of competing. Range 1.00–1.30:
        #    age 0y → ×1.30, 5y → ×1.15, 15y → ×1.075.
        if mode == "fresh_fit":
            recency = self._recency_array()
            sims = np.where(sims > 0, sims * (1.0 + 0.30 * recency), sims)

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

    def _recency_array(self) -> np.ndarray:
        """Per-row recency in (0, 1], smooth decay from the corpus's reference
        year. Unknown release date → neutral midpoint 0.5."""
        self._ensure_extended_meta()
        return self._recency_arr

    def is_game(self, appid: int) -> bool:
        """O(1) check whether an appid is a true game in the corpus."""
        self._ensure_extended_meta()
        return appid in self._game_appids_set

    def _ensure_extended_meta(self) -> None:
        """One-shot load of popularity, quality, review counts, type, and
        release year from SQLite. The recency array is derived from the
        latest year actually present in the corpus, so adding fresh games
        in a later refetch automatically shifts the reference point."""
        if hasattr(self, "_pop_arr"):
            return
        with self._conn() as c:
            placeholders = ",".join("?" * len(self.appid_order))
            cur = c.execute(
                f"SELECT appid, owners_low, positive_reviews, negative_reviews, type, release_date "
                f"FROM games WHERE appid IN ({placeholders})",
                self.appid_order,
            )
            rows = {a: (o or 0, p or 0, n or 0, t or "", d or "")
                    for a, o, p, n, t, d in cur.fetchall()}

        pop = []
        quality = []
        rev_count = []
        is_game = []
        years: list[int | None] = []
        game_set: set[int] = set()
        for a in self.appid_order:
            o, p, n, t, d = rows.get(a, (0, 0, 0, "", ""))
            pop.append(o)
            total = p + n
            # Smoothed positive ratio: (p + 5) / (total + 10) — Laplace-style prior at 0.5
            quality.append((p + 5) / (total + 10))
            rev_count.append(total)
            is_g = (t == "game")
            is_game.append(is_g)
            if is_g:
                game_set.add(a)
            years.append(_parse_year(d))

        self._pop_arr = np.asarray(pop, dtype=np.float64)
        self._quality_arr = np.asarray(quality, dtype=np.float64)
        self._review_count_arr = np.asarray(rev_count, dtype=np.float64)
        self._is_game_arr = np.asarray(is_game, dtype=bool)
        self._game_appids_set = game_set

        # Recency: 1 / (1 + age_in_years / 5).
        # Reference year = max parsed year in corpus, else wall clock.
        # Games without a parsed year get the neutral midpoint (≈0.5) so
        # fresh_fit neither boosts nor penalizes them.
        known = [y for y in years if y is not None]
        ref_year = max(known) if known else datetime.now(timezone.utc).year
        recency = np.empty(len(years), dtype=np.float64)
        neutral = 1.0 / (1.0 + 5.0 / 5.0)  # = 0.5; what a 5-year-old game gets
        for i, y in enumerate(years):
            if y is None:
                recency[i] = neutral
            else:
                age = max(0, ref_year - y)
                recency[i] = 1.0 / (1.0 + age / 5.0)
        self._recency_arr = recency
        self._recency_ref_year = ref_year

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
        min_relative_contrib: float = 0.20,
        min_closest_sim: float = 0.30,
    ) -> tuple[list[str], list[tuple[int, str, int]], tuple[int, str, int] | None]:
        """Why was this game recommended?

        Returns:
          shared_tags    - high-affinity tags the candidate has that the user's taste has
          evidence       - library games that drove the match (playtime × fit)
          closest_match  - the library game with the highest pure tag-similarity to
                           the candidate, surfaced only when it is NOT already one of
                           the drivers and the similarity passes `min_closest_sim`.
                           Resolves the "broad high-playtime game eats every
                           attribution" problem by giving the on-target small game
                           a dedicated slot.

        Attribution is the closed-form decomposition of the recommendation
        cosine. The taste vector is the L2-normalized playtime-weighted sum
        of library tf-idf rows, so the per-candidate cosine equals
            Σ_g [ log(1+hours_g) · cosine(g_vec, cand_vec) ] / ‖raw_taste‖
        and we rank library games by w_g · cosine(g, cand). A small but
        on-target library game beats a high-playtime broad game whose tag
        profile only loosely overlaps. Evidence below `min_relative_contrib`
        of the top contributor is dropped to suppress filler attributions.
        """
        cand_row = self._row(candidate_appid)
        if cand_row is None:
            return [], [], None
        cand_arr = cand_row.toarray().flatten()
        # Element-wise contribution = cand[tag] * taste[tag]
        contrib = cand_arr * taste_vec
        top_cols = np.argsort(contrib)[-max_shared_tags:][::-1]
        shared = [self.vocab[c] for c in top_cols if contrib[c] > 0]

        # Per library-game similarity + weighted contribution.
        # cosine(g, cand) = g_vec · cand_arr since both rows are L2-normalized.
        all_contribs: list[tuple[int, float, float]] = []  # (appid, w*sim, sim)
        for appid, playtime_min in library:
            if appid == candidate_appid:
                continue
            row_idx = self.appid_to_row.get(appid)
            if row_idx is None:
                continue
            w = log(1.0 + max(0.0, playtime_min / 60.0))
            if w <= 0:
                continue
            sim = float(self.tfidf[row_idx].multiply(cand_arr).sum())
            if sim <= 0:
                continue
            all_contribs.append((appid, w * sim, sim))

        if not all_contribs:
            return shared, [], None

        playtime_lookup = dict(library)

        # Drivers: top by playtime-weighted contribution
        all_contribs.sort(key=lambda x: x[1], reverse=True)
        threshold = all_contribs[0][1] * min_relative_contrib
        top_lib = [c for c in all_contribs if c[1] >= threshold][:max_evidence]
        driver_appids = {a for a, _, _ in top_lib}

        self._load_meta_batch([a for a, _, _ in top_lib])
        evidence: list[tuple[int, str, int]] = [
            (a, self._meta_cache.get(a, ("?",))[0], playtime_lookup.get(a, 0))
            for a, _, _ in top_lib
        ]

        # Closest match: highest pure cosine, only if distinct from drivers and strong enough
        closest_match: tuple[int, str, int] | None = None
        cl_appid, _, cl_sim = max(all_contribs, key=lambda x: x[2])
        if cl_sim >= min_closest_sim and cl_appid not in driver_appids:
            self._load_meta_batch([cl_appid])
            name = self._meta_cache.get(cl_appid, ("?",))[0]
            closest_match = (cl_appid, name, playtime_lookup.get(cl_appid, 0))

        return shared, evidence, closest_match

    # ------------------------------------------------------------
    # Phase 4: Tag co-occurrence embedding (PPMI + SVD, self-trained)
    # ------------------------------------------------------------

    @property
    def has_tag_embedding(self) -> bool:
        return self.tag_embedding is not None

    def tag_neighbors(self, tag: str, k: int = 8) -> list[tuple[str, float]]:
        """Semantic neighbors of a tag in the self-trained embedding space.

        Returns [(tag, cosine_sim), ...] sorted descending.
        Empty if the tag is missing from vocab or embedding isn't loaded.
        """
        if self.tag_embedding is None:
            return []
        col = self.tag_to_col.get(tag)
        if col is None:
            return []
        sims = self.tag_embedding @ self.tag_embedding[col]
        sims[col] = -1.0
        top = np.argsort(sims)[-k:][::-1]
        return [(self.vocab[i], float(sims[i])) for i in top if sims[i] > 0]

    def game_dense_vec(self, appid: int) -> np.ndarray | None:
        """Project a game into the dense PPMI tag-embedding space.

        Result = TF-IDF-weighted sum of tag embeddings, L2-normalized.
        Returns None if the game is not in corpus or embedding unavailable.
        """
        if self.tag_embedding is None:
            return None
        row = self._row(appid)
        if row is None:
            return None
        dense = np.asarray(row @ self.tag_embedding).flatten().astype(np.float32)
        n = float(np.linalg.norm(dense))
        if n > 0:
            dense /= n
        return dense

    # ------------------------------------------------------------
    # Phase 4+: Trained dual-encoder embedding (InfoNCE) for retrieval
    # ------------------------------------------------------------

    @property
    def has_game_embedding(self) -> bool:
        return self.game_embedding is not None

    def _ppmi_games(self) -> np.ndarray | None:
        """All-corpus PPMI game embedding, cached."""
        if self.tag_embedding is None:
            return None
        if self._ppmi_game_embedding is None:
            dense = np.asarray(self.tfidf @ self.tag_embedding).astype(np.float32)
            norms = np.linalg.norm(dense, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._ppmi_game_embedding = (dense / norms).astype(np.float32)
        return self._ppmi_game_embedding

    def similar_games(
        self,
        appid: int,
        k: int = 10,
        method: str = "ppmi",
        exclude: set[int] | None = None,
    ) -> list[tuple[int, float]]:
        """Game-game retrieval via the chosen embedding.

        method:
          - "tfidf": sparse TF-IDF cosine (baseline, 437 dim)
          - "ppmi":  PPMI tag embedding projection (50 dim, +2.4pp on probe)
          - "trained": trained dual encoder (256 dim, baseline parity)
        """
        if method == "tfidf":
            return self.similar_to_game(appid, k=k, exclude=exclude)

        if method == "ppmi":
            corpus_emb = self._ppmi_games()
            target = self.game_dense_vec(appid)
        elif method == "trained":
            corpus_emb = self.game_embedding
            row = self.appid_to_row.get(appid)
            target = corpus_emb[row] if (corpus_emb is not None and row is not None) else None
        else:
            raise ValueError(f"Unknown method: {method!r}")

        if corpus_emb is None or target is None:
            return []

        sims = corpus_emb @ target
        target_row = self.appid_to_row[appid]
        sims[target_row] = -1.0
        for x in exclude or ():
            r = self.appid_to_row.get(x)
            if r is not None:
                sims[r] = -1.0
        top = np.argsort(sims)[-k:][::-1]
        return [(self.appid_order[i], float(sims[i])) for i in top]


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
        shared, evidence, closest = engine.explain(appid, taste_vec, library)
        lines.append(f"\n[{appid:>8}] {ref.name}  (score {score:.3f})")
        if ref.tags:
            lines.append(f"  tags:     {', '.join(ref.tags)}")
        if shared:
            lines.append(f"  matches:  {', '.join(shared)}")
        if evidence:
            ev_str = ", ".join(f"{n} ({p/60:.0f}h)" for _, n, p in evidence)
            lines.append(f"  because:  {ev_str}")
        if closest:
            lines.append(f"  closest:  {closest[1]} ({closest[2]/60:.0f}h)")
    return "\n".join(lines)
