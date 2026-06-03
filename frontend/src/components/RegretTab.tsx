import { useState } from "react";
import type { RegretCluster, RegretReport } from "../lib/types";

type Kind = "mixed" | "pure" | "sleeping";

const KIND_META: Record<Kind, { label: string; section: string; intro: string }> = {
  mixed: {
    label: "mixed regret",
    section: "§01",
    intro:
      "You already found your favorites in these genres, then kept buying more. Same itch, but the original still scratches it best — the new ones sit unstarted.",
  },
  pure: {
    label: "pure regret",
    section: "§02",
    intro:
      "Types you keep buying and never click with. Each time on sale you think \"this one will land\" — and then it doesn't. These genres aren't for you. That's fine.",
  },
  sleeping: {
    label: "sleeping games",
    section: "§03",
    intro:
      "Bought, never properly started — under 30 minutes total. Shown ascending by playtime. The most quietly abandoned first.",
  },
};

export default function RegretTab({ regret }: { regret: RegretReport }) {
  const [kind, setKind] = useState<Kind>("mixed");
  const kindCount =
    kind === "mixed"
      ? regret.stats.mixed_count
      : kind === "pure"
      ? regret.stats.pure_count
      : regret.stats.sleeping_count;

  return (
    <div className="space-y-10 sm:space-y-14">
      {/* Stats — cartridge label badges, big pixel numbers */}
      <section>
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-4">
          act iii · the audit
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatBadge label="library" value={regret.stats.total_games} />
          <StatBadge label="in corpus" value={regret.stats.in_corpus} />
          <StatBadge
            label="untouched"
            value={regret.stats.sleeping_count}
            suffix="games"
            accent="coral"
          />
          <StatBadge
            label="regret patterns"
            value={regret.stats.regret_cluster_count}
            accent="amber"
          />
        </div>
      </section>

      {/* Kind switcher */}
      <section>
        <div className="flex items-stretch border-b border-[var(--color-border)] -mb-px overflow-x-auto">
          {(["mixed", "pure", "sleeping"] as Kind[]).map((k) => {
            const active = kind === k;
            const count =
              k === "mixed"
                ? regret.stats.mixed_count
                : k === "pure"
                ? regret.stats.pure_count
                : regret.stats.sleeping_count;
            return (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`flex-1 min-w-[140px] py-3 sm:py-4 px-3 sm:px-5 text-left border-b-2 transition-colors ${
                  active
                    ? "border-[var(--color-accent)]"
                    : "border-transparent hover:bg-[var(--color-surface-1)]"
                }`}
              >
                <div
                  className={`font-mono text-[10px] uppercase tracking-[0.2em] mb-0.5 flex items-baseline gap-2 ${
                    active
                      ? "text-[var(--color-accent)]"
                      : "text-[var(--color-text-dim)]"
                  }`}
                >
                  <span>{KIND_META[k].section}</span>
                  <span className="tabular text-[var(--color-text-dim)]">
                    ({count})
                  </span>
                </div>
                <div
                  className={`text-base sm:text-lg leading-tight tracking-tight ${
                    active
                      ? "text-[var(--color-text-hi)]"
                      : "text-[var(--color-text-mid)]"
                  }`}
                  style={{ fontWeight: 600 }}
                >
                  {KIND_META[k].label}
                </div>
              </button>
            );
          })}
        </div>

        {/* Intro paragraph */}
        <div className="mt-7 max-w-[60ch]">
          <p className="text-[var(--color-text-mid)] text-base sm:text-lg leading-relaxed">
            {KIND_META[kind].intro}
          </p>
        </div>
      </section>

      {/* Content */}
      <section>
        {kind === "mixed" && (
          <ClusterList clusters={regret.mixed.slice(0, 10)} kind="mixed" />
        )}
        {kind === "pure" && (
          <ClusterList clusters={regret.pure.slice(0, 10)} kind="pure" />
        )}
        {kind === "sleeping" && <SleepingGrid games={regret.sleeping_preview} />}

        {kind !== "sleeping" && kindCount === 0 && (
          <EmptyState kind={kind} />
        )}
      </section>
    </div>
  );
}

function StatBadge({
  label,
  value,
  suffix,
  accent,
}: {
  label: string;
  value: number;
  suffix?: string;
  accent?: "coral" | "amber";
}) {
  const color =
    accent === "coral"
      ? "text-[var(--color-coral)]"
      : accent === "amber"
      ? "text-[var(--color-accent)]"
      : "text-[var(--color-text-hi)]";
  return (
    <div className="bg-[var(--color-surface-1)] border border-[var(--color-border)] p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-1.5">
        {label}
      </div>
      <div className="flex items-baseline gap-1.5">
        <div
          className={`font-display tabular leading-none ${color}`}
          style={{ fontSize: "clamp(1.75rem, 5vw, 2.5rem)", fontWeight: 600 }}
        >
          {value.toLocaleString()}
        </div>
        {suffix && (
          <div className="font-mono text-xs text-[var(--color-text-dim)] tracking-wider">
            {suffix}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ kind }: { kind: "mixed" | "pure" }) {
  return (
    <div className="border border-[var(--color-border)] py-16 px-6 text-center">
      <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
        all clear
      </p>
      <p
        className="text-2xl text-[var(--color-text-hi)] mb-2 tracking-tight"
        style={{ fontWeight: 600 }}
      >
        {kind === "mixed" ? "no duplicates detected" : "no abandoned genres"}
      </p>
      <p className="text-sm text-[var(--color-text-lo)] max-w-md mx-auto">
        {kind === "mixed"
          ? "When you fall for a genre, you stick with the originals. Healthy."
          : "Whatever you buy, you actually try. That's rarer than you think."}
      </p>
    </div>
  );
}

function ClusterList({
  clusters,
  kind,
}: {
  clusters: RegretCluster[];
  kind: "mixed" | "pure";
}) {
  if (clusters.length === 0) return null;
  const accent =
    kind === "mixed"
      ? "border-[var(--color-accent-soft)]"
      : "border-[var(--color-coral-deep)]/40";

  return (
    <ol className="space-y-5">
      {clusters.map((c, i) => (
        <li
          key={c.label}
          className={`bg-[var(--color-surface-1)] border ${accent} p-5 sm:p-6`}
        >
          {/* Header */}
          <header className="flex items-start justify-between gap-4 mb-4">
            <div className="min-w-0">
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-1">
                pattern no. {String(i + 1).padStart(2, "0")}
              </div>
              <h3
                className="text-lg sm:text-xl text-[var(--color-text-hi)] leading-tight tracking-tight"
                style={{ fontWeight: 600 }}
              >
                {c.dominant_tags.slice(0, 3).join(" / ") || `Cluster ${c.label}`}
              </h3>
            </div>
            <div className="text-right shrink-0 font-mono text-xs tabular">
              <div className="text-[var(--color-text-hi)]">
                {c.game_count} games
              </div>
              <div className="text-[var(--color-text-dim)]">
                median {c.median_hours}h
              </div>
            </div>
          </header>

          {/* Diagnosis */}
          {c.diagnosis && (
            <p className="text-sm sm:text-base text-[var(--color-text-mid)] whitespace-pre-line leading-relaxed mb-5">
              {c.diagnosis}
            </p>
          )}

          {/* Thumbnails */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {c.games.slice(0, 5).map((g) => (
              <a
                key={g.appid}
                href={`https://store.steampowered.com/app/${g.appid}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block group/thumb"
              >
                <img
                  src={`https://cdn.akamai.steamstatic.com/steam/apps/${g.appid}/header.jpg`}
                  alt=""
                  className="w-full aspect-[460/215] object-cover bg-[var(--color-bg)] grayscale-[15%] group-hover/thumb:grayscale-0 transition-all"
                  onError={(e) =>
                    ((e.target as HTMLImageElement).style.display = "none")
                  }
                />
                <div className="font-mono text-xs text-[var(--color-text-mid)] mt-1.5 truncate">
                  {g.name}
                </div>
                <div className="font-mono text-[10px] text-[var(--color-text-dim)] tabular">
                  {g.playtime_hours}h
                </div>
              </a>
            ))}
          </div>
        </li>
      ))}
    </ol>
  );
}

function SleepingGrid({
  games,
}: {
  games: { appid: number; name: string; playtime_min: number }[];
}) {
  if (games.length === 0) {
    return (
      <div className="border border-[var(--color-border)] py-16 px-6 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
          clean shelf
        </p>
        <p
          className="text-2xl text-[var(--color-text-hi)] tracking-tight"
          style={{ fontWeight: 600 }}
        >
          no sleeping games
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {games.map((g) => (
        <a
          key={g.appid}
          href={`https://store.steampowered.com/app/${g.appid}`}
          target="_blank"
          rel="noopener noreferrer"
          className="block bg-[var(--color-surface-1)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] p-3 transition-colors group"
        >
          <img
            src={`https://cdn.akamai.steamstatic.com/steam/apps/${g.appid}/header.jpg`}
            alt=""
            className="w-full aspect-[460/215] object-cover bg-[var(--color-bg)] grayscale-[20%] group-hover:grayscale-0 transition-all mb-2"
            onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
          />
          <div className="text-sm text-[var(--color-text-hi)] truncate">
            {g.name}
          </div>
          <div className="font-mono text-[10px] text-[var(--color-coral)] tabular uppercase tracking-wider mt-0.5">
            {g.playtime_min}m played
          </div>
        </a>
      ))}
    </div>
  );
}
