import type { TasteProfile } from "../lib/types";

interface Props {
  taste: TasteProfile;
  onSelectTab: (t: "recs" | "regret") => void;
}

export default function TasteProfileTab({ taste, onSelectTab }: Props) {
  const tags = taste.top_tags.slice(0, 12);
  const maxWeight = Math.max(...tags.map((t) => t.weight), 0.01);
  const coverage = taste.library_stats.coverage;

  // Split clusters into regret / non-regret for editorial ordering
  const orderedClusters = [...taste.clusters].sort((a, b) =>
    b.total_hours - a.total_hours,
  );

  return (
    <div className="space-y-14 sm:space-y-20">
      {/* ====================  HERO  ==================== */}
      <section>
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
          act i · your taste in one sentence
        </p>
        <blockquote
          className="font-display text-[var(--color-text-hi)] leading-[1.1] max-w-[26ch]"
          style={{
            fontSize: "clamp(1.75rem, 4.5vw, 3rem)",
            fontWeight: 500,
            letterSpacing: "0.005em",
          }}
        >
          <span className="text-[var(--color-accent)] mr-2" aria-hidden>
            “
          </span>
          {taste.one_sentence.toLowerCase()}
          <span className="text-[var(--color-accent)] ml-1" aria-hidden>
            ”
          </span>
        </blockquote>
        <div className="mt-5 flex flex-wrap items-baseline gap-x-6 gap-y-1 font-mono text-xs text-[var(--color-text-dim)] uppercase tracking-[0.18em] tabular">
          <span>
            confidence{" "}
            <span className="text-[var(--color-text-mid)]">
              {(taste.confidence * 100).toFixed(0)}%
            </span>
          </span>
          <span>
            corpus match{" "}
            <span className="text-[var(--color-text-mid)]">
              {taste.library_stats.in_corpus} / {taste.library_stats.total_games}
            </span>
          </span>
          <span>
            coverage{" "}
            <span className="text-[var(--color-text-mid)]">
              {(coverage * 100).toFixed(0)}%
            </span>
          </span>
        </div>
      </section>

      {/* ====================  TAG AFFINITY (high-score style)  ==================== */}
      <section>
        <div className="flex items-baseline gap-4 mb-6">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-accent)]">
            §01
          </span>
          <h2
            className="font-display text-2xl sm:text-3xl text-[var(--color-text-hi)]"
            style={{ fontWeight: 500 }}
          >
            tag affinity, top 12
          </h2>
          <div className="h-px flex-1 bg-[var(--color-border)] translate-y-[-0.35em]" />
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] tabular">
            weight = playtime × idf
          </span>
        </div>

        <ol className="space-y-1">
          {tags.map((t, i) => {
            const pct = (t.weight / maxWeight) * 100;
            return (
              <li
                key={t.tag}
                className="group grid items-baseline gap-4 py-2.5 border-b border-[var(--color-border)]/40 hover:border-[var(--color-accent-soft)] transition-colors"
                style={{ gridTemplateColumns: "auto 1fr auto auto" }}
              >
                <span className="font-mono text-sm text-[var(--color-text-dim)] tabular w-9">
                  #{String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-base sm:text-lg text-[var(--color-text-hi)] truncate">
                  {t.tag}
                </span>
                {/* Pixel bar — block characters give retro feel */}
                <span
                  aria-hidden
                  className="font-mono text-xs sm:text-sm text-[var(--color-accent)] hidden sm:block w-32 sm:w-40 text-right tracking-[-0.05em] overflow-hidden whitespace-nowrap"
                  style={{ letterSpacing: "0" }}
                >
                  {"█".repeat(Math.max(1, Math.round(pct / 5)))}
                </span>
                <span className="font-mono text-sm text-[var(--color-text-mid)] tabular w-12 text-right">
                  {t.weight.toFixed(2)}
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      {/* ====================  TASTE CLUSTERS (cartridge cards)  ==================== */}
      <section>
        <div className="flex items-baseline gap-4 mb-6">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-accent)]">
            §02
          </span>
          <h2
            className="font-display text-2xl sm:text-3xl text-[var(--color-text-hi)]"
            style={{ fontWeight: 500 }}
          >
            your library, clustered
          </h2>
          <div className="h-px flex-1 bg-[var(--color-border)] translate-y-[-0.35em]" />
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] tabular">
            hdbscan · {taste.clusters.length} clusters
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {orderedClusters.slice(0, 10).map((c, i) => (
            <article
              key={c.label}
              className="bg-[var(--color-surface-1)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] p-4 sm:p-5 transition-colors"
            >
              {/* Cartridge header */}
              <header className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0">
                  <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-1">
                    profile #{String(i + 1).padStart(2, "0")}
                  </div>
                  <h3
                    className="font-display text-lg sm:text-xl text-[var(--color-text-hi)] leading-tight"
                    style={{ fontWeight: 500 }}
                  >
                    {c.name}
                  </h3>
                </div>
                <div className="text-right font-mono text-xs tabular shrink-0">
                  <div className="text-[var(--color-accent)]">
                    {c.total_hours.toFixed(0)}h
                  </div>
                  <div className="text-[var(--color-text-dim)]">
                    {c.game_count} games
                  </div>
                </div>
              </header>

              {/* Thumbnail strip */}
              {c.sample_games.length > 0 && (
                <div className="flex gap-1 mb-3">
                  {c.sample_games.slice(0, 4).map((g) => (
                    <a
                      key={g.appid}
                      href={`https://store.steampowered.com/app/${g.appid}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 min-w-0 group"
                      title={`${g.name} · ${g.playtime_hours}h`}
                    >
                      <img
                        src={`https://cdn.akamai.steamstatic.com/steam/apps/${g.appid}/header.jpg`}
                        alt=""
                        className="w-full aspect-[460/215] object-cover bg-[var(--color-bg)] grayscale-[15%] group-hover:grayscale-0 transition-all"
                        onError={(e) =>
                          ((e.target as HTMLImageElement).style.display = "none")
                        }
                      />
                    </a>
                  ))}
                </div>
              )}

              {/* Sample games line */}
              <div className="text-xs text-[var(--color-text-lo)] truncate mb-2.5">
                {c.sample_games
                  .slice(0, 3)
                  .map((g) => g.name)
                  .join(" · ")}
              </div>

              {/* Dominant tags */}
              <div className="flex flex-wrap gap-1.5 items-center">
                {c.dominant_tags.slice(0, 4).map((t) => (
                  <span
                    key={t}
                    className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 bg-[var(--color-surface-2)] text-[var(--color-text-mid)]"
                  >
                    {t}
                  </span>
                ))}
                {c.is_regret && (
                  <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-coral)]">
                    ◆ {c.regret_kind === "mixed" ? "mixed regret" : "pure regret"}
                  </span>
                )}
              </div>
            </article>
          ))}
        </div>

        {orderedClusters.length > 10 && (
          <div className="mt-4 font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] text-center">
            + {orderedClusters.length - 10} more in act iii
          </div>
        )}
      </section>

      {/* ====================  ACT NAVIGATION  ==================== */}
      <section className="pt-8 border-t border-[var(--color-border)]">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-5">
          continue
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            onClick={() => onSelectTab("recs")}
            className="group flex items-center gap-4 p-4 bg-[var(--color-surface-1)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent-soft)] transition-colors text-left"
          >
            <span className="font-mono text-2xl text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] transition-colors tabular w-10 shrink-0">
              ii
            </span>
            <div className="min-w-0 flex-1">
              <div
                className="font-display text-lg text-[var(--color-text-hi)] leading-tight"
                style={{ fontWeight: 500 }}
              >
                what you'd love next
              </div>
              <div className="text-xs text-[var(--color-text-lo)] mt-0.5">
                personalized recommendations + games you already own
              </div>
            </div>
            <span className="font-mono text-lg text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] group-hover:translate-x-1 transition-all shrink-0">
              →
            </span>
          </button>
          <button
            onClick={() => onSelectTab("regret")}
            className="group flex items-center gap-4 p-4 bg-[var(--color-surface-1)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent-soft)] transition-colors text-left"
          >
            <span className="font-mono text-2xl text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] transition-colors tabular w-10 shrink-0">
              iii
            </span>
            <div className="min-w-0 flex-1">
              <div
                className="font-display text-lg text-[var(--color-text-hi)] leading-tight"
                style={{ fontWeight: 500 }}
              >
                quietly outgrown
              </div>
              <div className="text-xs text-[var(--color-text-lo)] mt-0.5">
                types you bought but barely played
              </div>
            </div>
            <span className="font-mono text-lg text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] group-hover:translate-x-1 transition-all shrink-0">
              →
            </span>
          </button>
        </div>
      </section>
    </div>
  );
}
