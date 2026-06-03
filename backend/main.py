"""Steam Taste Lens — FastAPI app.

Run dev server:
    py -m uvicorn backend.main:app --reload --port 8000

Then visit:
    http://localhost:8000/docs    — interactive API explorer
    http://localhost:8000/api/health
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import auth
from .cache import TTLCache
from .config import settings
from .demo import DEMO_AVATAR, DEMO_LIBRARY, DEMO_PERSONA, DEMO_STEAMID
from .regret_detector import detect_regret
from .steam_client import (
    LibraryEntry,
    SteamApiError,
    fetch_library,
    fetch_player_summary,
    resolve_steamid,
)
from .taste_engine import TasteEngine


# ============================================================
# State (loaded once at startup)
# ============================================================

state: dict = {}
library_cache = TTLCache(maxsize=500, ttl=3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading Taste Engine...")
    engine = TasteEngine()
    state["engine"] = engine
    print(f"  corpus: {engine.corpus_size} games, vocab: {len(engine.vocab)} tags")
    yield
    state.clear()


app = FastAPI(title="Steam Taste Lens API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_engine() -> TasteEngine:
    eng = state.get("engine")
    if eng is None:
        raise HTTPException(503, "Engine not ready")
    return eng


# ============================================================
# Library fetch with caching (helper used by many endpoints)
# ============================================================

def _get_library_cached(steamid: int) -> list[LibraryEntry]:
    if steamid == DEMO_STEAMID:
        # synthesize LibraryEntry list from DEMO_LIBRARY
        eng = get_engine()
        out = []
        for appid, pt in DEMO_LIBRARY:
            out.append(LibraryEntry(
                appid=appid,
                name=eng.name_of(appid) or f"appid {appid}",
                playtime_minutes=int(pt),
            ))
        return out
    cached = library_cache.get(steamid)
    if cached is not None:
        return cached
    entries = fetch_library(steamid)
    library_cache.set(steamid, entries)
    return entries


def _library_tuples(steamid: int) -> list[tuple[int, int]]:
    if steamid == DEMO_STEAMID:
        return [(a, int(p)) for a, p in DEMO_LIBRARY]
    entries = _get_library_cached(steamid)
    return [(e.appid, e.playtime_minutes) for e in entries]


# ============================================================
# Health
# ============================================================

@app.get("/api/health")
def health():
    eng = state.get("engine")
    return {
        "status": "ok" if eng else "loading",
        "corpus_size": eng.corpus_size if eng else 0,
    }


# ============================================================
# Auth (Steam OpenID)
# ============================================================

@app.get("/api/auth/steam/login")
def steam_login():
    url = auth.build_login_url(
        return_to=f"{settings.backend_base}/api/auth/steam/callback",
        realm=settings.backend_base,
    )
    return RedirectResponse(url)


@app.get("/api/auth/steam/callback")
def steam_callback(request: Request):
    params = dict(request.query_params)
    steamid = auth.verify_callback(params)
    if not steamid:
        return RedirectResponse(f"{settings.frontend_base}/?error=auth_failed")
    return RedirectResponse(f"{settings.frontend_base}/result?steamid={steamid}")


# ============================================================
# Profile
# ============================================================

class ResolveRequest(BaseModel):
    input: str


@app.post("/api/profile/resolve")
def profile_resolve(req: ResolveRequest):
    try:
        steamid = resolve_steamid(req.input)
    except SteamApiError as e:
        raise HTTPException(400, str(e))
    summary = fetch_player_summary(steamid)
    return {
        # SteamID64 exceeds JS Number.MAX_SAFE_INTEGER — always return as string
        "steam_id": str(steamid),
        "persona_name": summary.get("personaname", ""),
        "avatar_url": summary.get("avatarfull", ""),
    }


@app.get("/api/profile/{steamid}/summary")
def profile_summary(steamid: int):
    if steamid == DEMO_STEAMID:
        return {
            "steam_id": str(DEMO_STEAMID),
            "persona_name": DEMO_PERSONA,
            "avatar_url": DEMO_AVATAR,
            "library_size": len(DEMO_LIBRARY),
            "total_hours": round(sum(p for _, p in DEMO_LIBRARY) / 60, 1),
        }
    summary = fetch_player_summary(steamid)
    try:
        entries = _get_library_cached(steamid)
    except SteamApiError as e:
        raise HTTPException(403, str(e))
    return {
        "steam_id": str(steamid),
        "persona_name": summary.get("personaname", ""),
        "avatar_url": summary.get("avatarfull", ""),
        "library_size": len(entries),
        "total_hours": round(sum(e.playtime_minutes for e in entries) / 60, 1),
    }


@app.get("/api/profile/{steamid}/library")
def profile_library(steamid: int):
    try:
        entries = _get_library_cached(steamid)
    except SteamApiError as e:
        raise HTTPException(403, str(e))
    return {
        "games": [
            {
                "appid": e.appid,
                "name": e.name,
                "playtime_minutes": e.playtime_minutes,
                "playtime_2weeks_minutes": e.playtime_2weeks_minutes,
            }
            for e in entries
        ],
    }


@app.get("/api/demo/profile")
def demo_profile():
    """Single endpoint returning everything the demo flow needs."""
    return profile_summary(DEMO_STEAMID)


# ============================================================
# Taste profile
# ============================================================

def _generate_one_sentence(top_tags: list[tuple[str, float]]) -> str:
    """Cheeky one-liner characterizing the player based on top tag mix."""
    if not top_tags:
        return "Your library is too small to characterize."
    tags = [t for t, _ in top_tags[:6]]
    s = set(tags)

    has_rpg       = bool(s & {"RPG", "Action RPG", "JRPG", "CRPG", "Open World"})
    has_strategy  = bool(s & {"Strategy", "Grand Strategy", "4X", "Turn-Based Strategy"})
    has_mp        = bool(s & {"Multiplayer", "Online Co-Op", "Co-op", "PvP", "Battle Royale", "MOBA"})
    has_narrative = bool(s & {"Story Rich", "Choices Matter", "Visual Novel", "Atmospheric"})
    has_rogue     = bool(s & {"Rogue-lite", "Rogue-like", "Action Roguelike"})
    has_horror    = bool(s & {"Horror", "Survival Horror", "Psychological Horror"})
    has_cozy      = bool(s & {"Cozy", "Wholesome", "Relaxing", "Life Sim"})

    if has_rpg and has_mp:
        return "Multi-genre player: deep singleplayer RPGs by night, competitive multiplayer by day"
    if has_strategy and has_rogue:
        return "Strategist by trade, roguelite obsessive on the side"
    if has_rpg and has_narrative:
        return "Narrative-driven RPG explorer"
    if has_rogue and has_strategy:
        return "Deckbuilder & roguelite specialist"
    if has_horror and has_mp:
        return "Co-op horror enthusiast"
    if has_cozy:
        return "Cozy-leaning player — comfort over challenge"
    if has_rogue:
        return "Roguelite obsessive — the run never ends"
    if has_strategy:
        return "Grand strategist — empires take time"
    if has_mp:
        return "Competitive multiplayer focused"
    if has_rpg:
        return "RPG-leaning player"
    return f"Eclectic player with a preference for {tags[0]}"


@app.get("/api/taste/{steamid}/profile")
def taste_profile(steamid: int):
    eng = get_engine()
    try:
        library = _library_tuples(steamid)
    except SteamApiError as e:
        raise HTTPException(403, str(e))

    taste, stats = eng.compute_taste_vector(library)
    top_tags = eng.top_taste_tags(taste, k=12)

    report = detect_regret(eng, library)
    clusters = []
    for c in sorted(report.clusters, key=lambda x: -x.total_playtime_hours):
        if c.label == -1:
            continue
        name = " / ".join(c.dominant_tags[:2]) if c.dominant_tags else f"Cluster {c.label}"
        clusters.append({
            "label": c.label,
            "name": name,
            "dominant_tags": c.dominant_tags[:5],
            "total_hours": round(c.total_playtime_hours, 1),
            "median_hours": round(c.median_playtime_hours, 1),
            "game_count": len(c.games),
            "is_regret": c.is_regret,
            "regret_kind": c.regret_kind,
            "sample_games": [
                {"appid": a, "name": n, "playtime_hours": round(p / 60, 1)}
                for a, n, p in c.games[:5]
            ],
        })

    return {
        "one_sentence": _generate_one_sentence(top_tags),
        "top_tags": [{"tag": t, "weight": round(w, 3)} for t, w in top_tags],
        "clusters": clusters,
        "confidence": round(stats["confidence"], 2),
        "library_stats": {
            "total_games": stats["library_size"],
            "in_corpus": stats["in_corpus"],
            "coverage": round(stats["coverage"], 2),
        },
    }


# ============================================================
# Recommendations
# ============================================================

def _match_pct(score: float) -> float:
    """Rescale raw cosine [0, 1] to a more intuitive 0-99 match %.
    Typical good matches sit at sim 0.4-0.7 — sqrt curve lifts them
    into the 60-85 range that feels confident, while keeping low scores low.
    """
    if score <= 0:
        return 1.0
    return max(1.0, min(99.0, (score ** 0.5) * 100))


def _build_rec_card(
    eng: TasteEngine,
    appid: int,
    match_score: float,
    taste_vec,
    library: list[tuple[int, int]],
    extra: Optional[dict] = None,
) -> dict:
    ref = eng.game_ref(appid)
    shared, evidence, closest = eng.explain(appid, taste_vec, library)
    pct = _match_pct(match_score)
    card = {
        "appid": appid,
        "name": ref.name,
        "header_image": ref.header_image,
        "tags": ref.tags,
        "match_pct": round(pct, 1),
        "shared_tags": shared,
        "evidence_games": [
            {"appid": a, "name": n, "playtime_hours": round(p / 60, 1)}
            for a, n, p in evidence
        ],
        "closest_match": (
            {"appid": closest[0], "name": closest[1], "playtime_hours": round(closest[2] / 60, 1)}
            if closest else None
        ),
        "steam_url": f"https://store.steampowered.com/app/{appid}",
    }
    if extra:
        card.update(extra)
    return card


@app.get("/api/taste/{steamid}/recommend/new")
def recommend_new(steamid: int, mode: str = "best_fit", k: int = 10):
    eng = get_engine()
    try:
        library = _library_tuples(steamid)
    except SteamApiError as e:
        raise HTTPException(403, str(e))

    if mode not in ("best_fit", "hidden_gem", "stretch", "fresh_fit"):
        raise HTTPException(400, f"unknown mode '{mode}'")

    taste, _ = eng.compute_taste_vector(library)
    owned = {a for a, _ in library}
    recs = eng.recommend(taste, owned, k=k, mode=mode)
    return {
        "mode": mode,
        "items": [_build_rec_card(eng, a, s, taste, library) for a, s in recs],
    }


@app.get("/api/taste/{steamid}/recommend/owned")
def recommend_owned(steamid: int, k: int = 15, max_playtime_hours: float = 2.0):
    """Owned-but-unplayed games ranked by taste fit. The killer mirror of Regret."""
    import numpy as np
    eng = get_engine()
    try:
        library = _library_tuples(steamid)
    except SteamApiError as e:
        raise HTTPException(403, str(e))

    taste, _ = eng.compute_taste_vector(library)
    max_pt_min = max_playtime_hours * 60

    candidates: list[tuple[int, int, float]] = []
    for appid, playtime in library:
        if playtime > max_pt_min:
            continue
        row = eng.appid_to_row.get(appid)
        if row is None:
            continue
        if not eng.is_game(appid):
            continue
        game_vec = np.asarray(eng.tfidf[row].todense()).flatten()
        score = float(taste @ game_vec)
        if score > 0:
            candidates.append((appid, playtime, score))

    candidates.sort(key=lambda x: -x[2])
    top = candidates[:k]

    items = []
    for appid, playtime, score in top:
        items.append(_build_rec_card(
            eng, appid, score, taste, library,
            extra={"current_playtime_min": int(playtime)},
        ))
    return {"items": items}


# ============================================================
# Library Regret
# ============================================================

@app.get("/api/taste/{steamid}/regret")
def regret_endpoint(steamid: int, lang: str = "zh"):
    if lang not in ("zh", "en"):
        # Unknown locale → fall back to zh rather than erroring out.
        lang = "zh"
    eng = get_engine()
    try:
        library = _library_tuples(steamid)
    except SteamApiError as e:
        raise HTTPException(403, str(e))

    report = detect_regret(eng, library, lang=lang)

    def serialize(c):
        return {
            "label": c.label,
            "dominant_tags": c.dominant_tags[:5],
            "diagnosis": c.diagnosis,
            "kind": c.regret_kind,
            "game_count": len(c.games),
            "median_hours": round(c.median_playtime_hours, 1),
            "max_hours": round(c.max_playtime_hours, 1),
            "games": [
                {"appid": a, "name": n, "playtime_hours": round(p / 60, 1)}
                for a, n, p in c.games
            ],
        }

    pure = [serialize(c) for c in report.regret_clusters if c.regret_kind == "pure"]
    mixed = [serialize(c) for c in report.regret_clusters if c.regret_kind == "mixed"]

    # Sort by severity = count / (1 + median_hours)
    def sev(c):
        return c["game_count"] / (1 + c["median_hours"])

    pure.sort(key=sev, reverse=True)
    mixed.sort(key=sev, reverse=True)

    return {
        "stats": {
            "total_games": report.total_games,
            "in_corpus": report.games_in_corpus,
            "sleeping_count": len(report.sleeping_games),
            "regret_cluster_count": len(report.regret_clusters),
            "pure_count": len(pure),
            "mixed_count": len(mixed),
        },
        "mixed": mixed,
        "pure": pure,
        "sleeping_preview": [
            {"appid": a, "name": n, "playtime_min": p}
            for a, n, p in report.sleeping_games[:30]
        ],
    }


# ============================================================
# Algorithm introspection (Phase 4)
# ============================================================

@app.get("/api/algo/tag_neighbors")
def tag_neighbors(tag: str, k: int = 8):
    """Semantic neighbors of a tag from the self-trained co-occurrence embedding.

    Demo endpoint to showcase the Phase 4 layer: shows that "Rogue-like" ~
    "Rogue-lite", "Cozy" ~ "Wholesome", etc. — without any pretrained model.
    """
    eng = get_engine()
    if not eng.has_tag_embedding:
        raise HTTPException(503, "Tag embedding not loaded on this deployment")
    nbs = eng.tag_neighbors(tag, k=k)
    if not nbs and tag not in eng.tag_to_col:
        raise HTTPException(404, f"Tag {tag!r} not in vocabulary")
    return {
        "tag": tag,
        "neighbors": [{"tag": t, "sim": round(s, 3)} for t, s in nbs],
    }


@app.get("/api/algo/game_neighbors")
def game_neighbors(appid: int, method: str = "ppmi", k: int = 8):
    """Game-game retrieval through one of three embeddings.

    method:
      tfidf   — sparse TF-IDF cosine baseline (437 dim)
      ppmi    — PPMI tag embedding projection (50 dim, +2.4pp on probe)
      trained — InfoNCE-trained dual encoder (256 dim, baseline parity)

    Demo endpoint that exposes the Phase 4 / Phase 4+ ablation live.
    """
    eng = get_engine()
    if method not in ("tfidf", "ppmi", "trained"):
        raise HTTPException(400, f"Unknown method: {method!r}")
    if method == "ppmi" and not eng.has_tag_embedding:
        raise HTTPException(503, "PPMI embedding not loaded")
    if method == "trained" and not eng.has_game_embedding:
        raise HTTPException(503, "Trained encoder embedding not loaded")
    if appid not in eng.appid_to_row:
        raise HTTPException(404, f"appid {appid} not in corpus")

    pairs = eng.similar_games(appid, k=k, method=method)
    return {
        "appid": appid,
        "name": eng.name_of(appid),
        "method": method,
        "neighbors": [
            {
                "appid": a,
                "name": eng.name_of(a),
                "sim": round(s, 3),
            }
            for a, s in pairs
        ],
    }


# ============================================================
# Game metadata
# ============================================================

@app.get("/api/game/{appid}")
def game_meta(appid: int):
    eng = get_engine()
    ref = eng.game_ref(appid)
    if not ref.name:
        raise HTTPException(404, "Game not in corpus")
    return {
        "appid": appid,
        "name": ref.name,
        "header_image": ref.header_image,
        "tags": ref.tags,
        "steam_url": f"https://store.steampowered.com/app/{appid}",
    }
