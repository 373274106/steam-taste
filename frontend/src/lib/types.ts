// API response shapes — mirrors backend/main.py

// NOTE: SteamID64 is a 17-digit integer that exceeds JS Number.MAX_SAFE_INTEGER.
// The backend always serializes it as a string. Never cast to number on the
// frontend — keep it as a string throughout (URL params, fetch paths, etc).

export interface ProfileSummary {
  steam_id: string;
  persona_name: string;
  avatar_url: string;
  library_size: number;
  total_hours: number;
}

export interface ResolveResponse {
  steam_id: string;
  persona_name: string;
  avatar_url: string;
}

export interface TagWeight {
  tag: string;
  weight: number;
}

export interface SampleGame {
  appid: number;
  name: string;
  playtime_hours: number;
}

export interface TasteCluster {
  label: number;
  name: string;
  dominant_tags: string[];
  total_hours: number;
  median_hours: number;
  game_count: number;
  is_regret: boolean;
  regret_kind: "" | "pure" | "mixed";
  sample_games: SampleGame[];
}

export interface TasteProfile {
  one_sentence: string;
  top_tags: TagWeight[];
  clusters: TasteCluster[];
  confidence: number;
  library_stats: {
    total_games: number;
    in_corpus: number;
    coverage: number;
  };
}

export interface EvidenceGame {
  appid: number;
  name: string;
  playtime_hours: number;
}

export interface RecCard {
  appid: number;
  name: string;
  header_image: string;
  tags: string[];
  match_pct: number;
  shared_tags: string[];
  evidence_games: EvidenceGame[];
  steam_url: string;
  current_playtime_min?: number; // only on "owned" recs
}

export interface RecommendResponse {
  mode?: string;
  items: RecCard[];
}

export interface RegretGame {
  appid: number;
  name: string;
  playtime_hours: number;
}

export interface RegretCluster {
  label: number;
  dominant_tags: string[];
  diagnosis: string;
  kind: "pure" | "mixed";
  game_count: number;
  median_hours: number;
  max_hours: number;
  games: RegretGame[];
}

export interface SleepingGame {
  appid: number;
  name: string;
  playtime_min: number;
}

export interface RegretReport {
  stats: {
    total_games: number;
    in_corpus: number;
    sleeping_count: number;
    regret_cluster_count: number;
    pure_count: number;
    mixed_count: number;
  };
  mixed: RegretCluster[];
  pure: RegretCluster[];
  sleeping_preview: SleepingGame[];
}
