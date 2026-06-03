import { useState } from "react";
import type { RecCard, RecommendResponse } from "../lib/types";

interface Props {
  recsNew: RecommendResponse;
  recsOwned: RecommendResponse;
}

type Mode = "new" | "owned";

const MODE_META: Record<Mode, { label: string; caption: string; intro: string }> = {
  new: {
    label: "discover new",
    caption: "games you don't own yet",
    intro:
      "Ranked by taste similarity against your library. Excludes anything already in your collection. Each pick comes with its evidence — the games of yours that contributed most to the match.",
  },
  owned: {
    label: "play what you own",
    caption: "the backlog, sorted by fit",
    intro:
      "Games you already bought but barely started, ranked by how well they fit your current taste. Steam won't show you this list — finishing what you own doesn't drive their revenue.",
  },
};

export default function RecommendationsTab({ recsNew, recsOwned }: Props) {
  const [mode, setMode] = useState<Mode>("new");
  const items = mode === "new" ? recsNew.items : recsOwned.items;

  return (
    <div className="space-y-10 sm:space-y-14">
      {/* Mode switcher — small act-style nav */}
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
          act ii · recommendations
        </p>
        <div className="flex items-stretch border-b border-[var(--color-border)] -mb-px">
          {(["new", "owned"] as Mode[]).map((m) => {
            const active = mode === m;
            return (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 sm:flex-none sm:min-w-[200px] py-3 sm:py-4 px-2 sm:px-5 text-left border-b-2 transition-colors ${
                  active
                    ? "border-[var(--color-accent)]"
                    : "border-transparent hover:bg-[var(--color-surface-1)]"
                }`}
              >
                <div
                  className={`font-mono text-[10px] uppercase tracking-[0.2em] mb-0.5 ${
                    active
                      ? "text-[var(--color-accent)]"
                      : "text-[var(--color-text-dim)]"
                  }`}
                >
                  §{m === "new" ? "01" : "02"}
                </div>
                <div
                  className={`font-display text-base sm:text-lg leading-tight ${
                    active
                      ? "text-[var(--color-text-hi)]"
                      : "text-[var(--color-text-mid)]"
                  }`}
                  style={{ fontWeight: 500 }}
                >
                  {MODE_META[m].label}
                </div>
              </button>
            );
          })}
        </div>

        {/* Editorial intro for selected mode */}
        <div className="mt-7 max-w-[60ch]">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-2">
            {MODE_META[mode].caption}
          </p>
          <p className="text-[var(--color-text-mid)] text-base sm:text-lg leading-relaxed">
            {MODE_META[mode].intro}
          </p>
        </div>
      </div>

      {/* Results — editorial review entries */}
      <section>
        {items.length === 0 ? (
          <EmptyState mode={mode} />
        ) : (
          <ol className="space-y-4 sm:space-y-5">
            {items.map((card, i) => (
              <RecEntry key={card.appid} card={card} mode={mode} rank={i + 1} />
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function EmptyState({ mode }: { mode: Mode }) {
  return (
    <div className="border border-[var(--color-border)] py-16 px-6 text-center">
      <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
        {mode === "owned" ? "clean backlog" : "no matches"}
      </p>
      <p
        className="font-display text-2xl text-[var(--color-text-hi)] mb-2"
        style={{ fontWeight: 500 }}
      >
        {mode === "owned"
          ? "your backlog is clean"
          : "no strong matches in the corpus"}
      </p>
      <p className="text-sm text-[var(--color-text-lo)]">
        {mode === "owned"
          ? "Impressive purchasing discipline. Or you just play everything you buy."
          : "Try a different account, or come back after we expand the corpus."}
      </p>
    </div>
  );
}

function RecEntry({
  card,
  mode,
  rank,
}: {
  card: RecCard;
  mode: Mode;
  rank: number;
}) {
  return (
    <li className="bg-[var(--color-surface-1)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] transition-colors group">
      <div className="grid grid-cols-1 sm:grid-cols-[224px_1fr] gap-0">
        {/* Cover */}
        {card.header_image ? (
          <a
            href={card.steam_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block overflow-hidden bg-[var(--color-bg)] aspect-[460/215] sm:aspect-auto"
          >
            <img
              src={card.header_image}
              alt=""
              className="w-full h-full object-cover grayscale-[15%] group-hover:grayscale-0 transition-all"
              onError={(e) =>
                ((e.target as HTMLImageElement).style.display = "none")
              }
            />
          </a>
        ) : (
          <div className="bg-[var(--color-bg)] aspect-[460/215] sm:aspect-auto" />
        )}

        {/* Body */}
        <div className="p-5 min-w-0 flex flex-col gap-3">
          {/* Title row */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-1">
                no. {String(rank).padStart(2, "0")}
                {mode === "owned" &&
                  card.current_playtime_min !== undefined && (
                    <span className="ml-3 text-[var(--color-coral)]">
                      ◆ owned · {card.current_playtime_min}m played
                    </span>
                  )}
              </div>
              <h3
                className="font-display text-xl sm:text-2xl text-[var(--color-text-hi)] leading-tight"
                style={{ fontWeight: 500 }}
              >
                {card.name}
              </h3>
            </div>
            {/* Match score — big tabular */}
            <div className="text-right shrink-0">
              <div
                className="font-display text-3xl sm:text-4xl text-[var(--color-accent)] tabular leading-none"
                style={{ fontWeight: 600 }}
              >
                {card.match_pct.toFixed(0)}
                <span className="text-base text-[var(--color-text-dim)]">%</span>
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] mt-1">
                match
              </div>
            </div>
          </div>

          {/* Shared tags */}
          {card.shared_tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {card.shared_tags.slice(0, 5).map((t) => (
                <span
                  key={t}
                  className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 bg-[var(--color-surface-2)] text-[var(--color-text-mid)]"
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          {/* Evidence */}
          {card.evidence_games.length > 0 && (
            <div className="text-sm text-[var(--color-text-mid)] leading-relaxed">
              <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mr-2">
                because of
              </span>
              {card.evidence_games.map((g, i) => (
                <span key={g.appid}>
                  <span className="text-[var(--color-text-hi)]">{g.name}</span>
                  <span className="font-mono text-xs text-[var(--color-text-dim)] tabular ml-1">
                    {g.playtime_hours}h
                  </span>
                  {i < card.evidence_games.length - 1 && (
                    <span className="text-[var(--color-text-dim)]"> · </span>
                  )}
                </span>
              ))}
            </div>
          )}

          {/* Footer link */}
          <div className="mt-auto pt-1">
            <a
              href={card.steam_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-mid)] hover:text-[var(--color-accent)] transition-colors"
            >
              view on steam ↗
            </a>
          </div>
        </div>
      </div>
    </li>
  );
}
