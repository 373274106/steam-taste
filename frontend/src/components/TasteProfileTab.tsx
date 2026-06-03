import type { TasteProfile } from "../lib/types";

interface Props {
  taste: TasteProfile;
  onSelectTab: (t: "recs" | "regret") => void;
}

export default function TasteProfileTab({ taste, onSelectTab }: Props) {
  const maxWeight = Math.max(...taste.top_tags.map((t) => t.weight), 0.01);

  return (
    <div className="space-y-8">
      {/* One-sentence header */}
      <div>
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
          your taste in one sentence
        </div>
        <h2 className="text-2xl font-bold text-slate-100">{taste.one_sentence}</h2>
        <div className="text-xs text-slate-500 mt-2">
          confidence {(taste.confidence * 100).toFixed(0)}% ·
          {" "}{taste.library_stats.in_corpus} / {taste.library_stats.total_games} games matched in corpus
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Top tags bar chart */}
        <div className="bg-[var(--color-steam-panel)] rounded-lg p-5 border border-slate-800">
          <h3 className="font-semibold mb-4 text-sm uppercase tracking-wider text-slate-400">
            Top Taste Tags
          </h3>
          <div className="space-y-2">
            {taste.top_tags.map((t) => (
              <div key={t.tag} className="flex items-center gap-3">
                <div className="w-32 text-sm truncate">{t.tag}</div>
                <div className="flex-1 bg-slate-800 h-5 rounded overflow-hidden">
                  <div
                    className="h-full bg-[var(--color-steam-blue)]"
                    style={{ width: `${(t.weight / maxWeight) * 100}%` }}
                  />
                </div>
                <div className="w-12 text-right text-xs text-slate-500">
                  {t.weight.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cluster summary */}
        <div className="bg-[var(--color-steam-panel)] rounded-lg p-5 border border-slate-800">
          <h3 className="font-semibold mb-4 text-sm uppercase tracking-wider text-slate-400">
            Taste Clusters ({taste.clusters.length})
          </h3>
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
            {taste.clusters.slice(0, 12).map((c) => (
              <div
                key={c.label}
                className={`p-3 rounded border ${
                  c.is_regret
                    ? "border-red-900/60 bg-red-950/20"
                    : "border-slate-800 bg-slate-900/40"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="font-medium text-sm">{c.name}</div>
                  <div className="text-xs text-slate-400">
                    {c.total_hours.toFixed(0)}h · {c.game_count} games
                  </div>
                </div>
                <div className="text-xs text-slate-500">
                  {c.sample_games.slice(0, 3).map((g) => g.name).join(" · ")}
                </div>
                {c.is_regret && (
                  <div className="text-xs text-red-400 mt-1">
                    {c.regret_kind === "mixed" ? "Mixed regret" : "Pure regret"}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => onSelectTab("recs")}
          className="bg-[var(--color-steam-blue)] hover:bg-blue-500 transition px-4 py-2 rounded text-sm font-medium"
        >
          看推荐 →
        </button>
        <button
          onClick={() => onSelectTab("regret")}
          className="bg-slate-800 hover:bg-slate-700 transition px-4 py-2 rounded text-sm"
        >
          看 Library Regret →
        </button>
      </div>
    </div>
  );
}
