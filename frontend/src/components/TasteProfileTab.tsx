import { useTranslation } from "react-i18next";
import type { TasteProfile } from "../lib/types";
import { useTagLabel } from "../lib/tags";
import TagRadar from "./TagRadar";

interface Props {
  taste: TasteProfile;
  onSelectTab: (t: "recs" | "regret") => void;
}

export default function TasteProfileTab({ taste, onSelectTab }: Props) {
  const { t } = useTranslation();
  const tagLabel = useTagLabel();
  const tags = taste.top_tags.slice(0, 12);
  const coverage = taste.library_stats.coverage;

  const orderedClusters = [...taste.clusters].sort(
    (a, b) => b.total_hours - a.total_hours,
  );

  return (
    <div className="space-y-14 sm:space-y-20">
      {/* ====================  HERO  ==================== */}
      <section>
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
          {t("taste.kicker")}
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
          {(taste.one_sentence || t("taste.fallbackSentence")).toLowerCase()}
          <span className="text-[var(--color-accent)] ml-1" aria-hidden>
            ”
          </span>
        </blockquote>
        <div className="mt-5 flex flex-wrap items-baseline gap-x-6 gap-y-1 font-mono text-xs text-[var(--color-text-dim)] uppercase tracking-[0.18em] tabular">
          <span>
            {t("taste.stats.confidence")}{" "}
            <span className="text-[var(--color-text-mid)]">
              {(taste.confidence * 100).toFixed(0)}%
            </span>
          </span>
          <span>
            {t("taste.stats.corpusMatch")}{" "}
            <span className="text-[var(--color-text-mid)]">
              {taste.library_stats.in_corpus} / {taste.library_stats.total_games}
            </span>
          </span>
          <span>
            {t("taste.stats.coverage")}{" "}
            <span className="text-[var(--color-text-mid)]">
              {(coverage * 100).toFixed(0)}%
            </span>
          </span>
        </div>
      </section>

      {/* ====================  TAG AFFINITY (radar + ranking)  ==================== */}
      <section>
        <div className="flex items-baseline gap-4 mb-7">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-accent)]">
            {t("taste.tagAffinity.kicker")}
          </span>
          <h2
            className="text-xl sm:text-2xl text-[var(--color-text-hi)] tracking-tight"
            style={{ fontWeight: 600 }}
          >
            {t("taste.tagAffinity.heading")}
          </h2>
          <div className="h-px flex-1 bg-[var(--color-border)] translate-y-[-0.35em]" />
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] tabular">
            {t("taste.tagAffinity.metric")}
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-8 lg:gap-12 items-center">
          {/* Radar — top 8 */}
          <div className="relative">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-2">
              {t("taste.tagAffinity.radarLabel")}
            </p>
            <TagRadar data={tags} top={8} />
          </div>

          {/* Compact ranking — top 12 */}
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-text-dim)] mb-3">
              {t("taste.tagAffinity.rankedLabel")}
            </p>
            <ol className="grid grid-cols-1 gap-0">
              {tags.map((tag, i) => (
                <li
                  key={tag.tag}
                  className="grid items-baseline gap-3 py-1.5 border-b border-[var(--color-border)]/40 last:border-0"
                  style={{ gridTemplateColumns: "auto 1fr auto" }}
                >
                  <span className="font-mono text-xs text-[var(--color-text-dim)] tabular w-7">
                    #{String(i + 1).padStart(2, "0")}
                  </span>
                  <span
                    className={`text-sm text-[var(--color-text-hi)] truncate ${
                      i < 3 ? "text-[var(--color-accent)]" : ""
                    }`}
                  >
                    {tagLabel(tag.tag)}
                  </span>
                  <span className="font-mono text-xs text-[var(--color-text-mid)] tabular w-10 text-right">
                    {tag.weight.toFixed(2)}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* ====================  TASTE CLUSTERS (cartridge cards)  ==================== */}
      <section>
        <div className="flex items-baseline gap-4 mb-6">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-accent)]">
            {t("taste.clusters.kicker")}
          </span>
          <h2
            className="text-xl sm:text-2xl text-[var(--color-text-hi)] tracking-tight"
            style={{ fontWeight: 600 }}
          >
            {t("taste.clusters.heading")}
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
                    {t("taste.clusters.profileNo")}{String(i + 1).padStart(2, "0")}
                  </div>
                  <h3
                    className="text-base sm:text-lg text-[var(--color-text-hi)] leading-tight tracking-tight"
                    style={{ fontWeight: 600 }}
                  >
                    {c.dominant_tags.length > 0
                      ? c.dominant_tags.slice(0, 2).map(tagLabel).join(" / ")
                      : c.name}
                  </h3>
                </div>
                <div className="text-right font-mono text-xs tabular shrink-0">
                  <div className="text-[var(--color-accent)]">
                    {c.total_hours.toFixed(0)}h
                  </div>
                  <div className="text-[var(--color-text-dim)]">
                    {c.game_count} {t("result.games")}
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
                {c.dominant_tags.slice(0, 4).map((tag) => (
                  <span
                    key={tag}
                    className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 bg-[var(--color-surface-2)] text-[var(--color-text-mid)]"
                  >
                    {tagLabel(tag)}
                  </span>
                ))}
                {c.is_regret && (
                  <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-coral)]">
                    ◆ {t(`regret.subtabs.${c.regret_kind === "mixed" ? "mixed" : "pure"}`)}
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
          {t("taste.footer.nextLabel")}
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
                className="text-base sm:text-lg text-[var(--color-text-hi)] leading-tight"
                style={{ fontWeight: 600 }}
              >
                {t("taste.footer.nextHeading")}
              </div>
              <div className="text-xs text-[var(--color-text-lo)] mt-0.5">
                {t("taste.footer.nextHint")}
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
                className="text-base sm:text-lg text-[var(--color-text-hi)] leading-tight"
                style={{ fontWeight: 600 }}
              >
                {t("taste.footer.regretHeading")}
              </div>
              <div className="text-xs text-[var(--color-text-lo)] mt-0.5">
                {t("taste.footer.regretHint")}
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
