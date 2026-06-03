import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import type {
  ProfileSummary,
  TasteProfile,
  RegretReport,
  RecommendResponse,
} from "../lib/types";
import Masthead from "../components/Masthead";
import TasteProfileTab from "../components/TasteProfileTab";
import RecommendationsTab from "../components/RecommendationsTab";
import RegretTab from "../components/RegretTab";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";

type Tab = "taste" | "recs" | "regret";
type LoadStep = "library" | "taste" | "recs" | "regret" | "done";
type DiscoverMode = "best_fit" | "fresh_fit";

const ACTS: { key: Tab; roman: "i" | "ii" | "iii" }[] = [
  { key: "taste", roman: "i" },
  { key: "recs", roman: "ii" },
  { key: "regret", roman: "iii" },
];

export default function Result() {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage || "en";
  const [params] = useSearchParams();
  const steamidParam = params.get("steamid");
  const isDemo = params.get("demo") === "1" || steamidParam === "-1";
  const steamid = steamidParam ?? "-1";

  const [tab, setTab] = useState<Tab>("taste");
  const [discoverMode, setDiscoverMode] = useState<DiscoverMode>("best_fit");

  const [summary, setSummary] = useState<ProfileSummary | null>(null);
  const [taste, setTaste] = useState<TasteProfile | null>(null);
  const [recsBest, setRecsBest] = useState<RecommendResponse | null>(null);
  const [recsOwned, setRecsOwned] = useState<RecommendResponse | null>(null);
  const [recsRefreshing, setRecsRefreshing] = useState(false);
  const [regret, setRegret] = useState<RegretReport | null>(null);

  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState<LoadStep>("library");
  const [error, setError] = useState<string | null>(null);

  // Initial pipeline — taste / recs / regret in sequence. Uses the current
  // discoverMode for the *new* recs call. Mode flips after this resolves are
  // handled by the lightweight refetch effect below.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setStep("library");

    (async () => {
      try {
        const s = await api.profileSummary(steamid);
        if (cancelled) return;
        setSummary(s);
        setStep("taste");

        const t = await api.tasteProfile(steamid);
        if (cancelled) return;
        setTaste(t);
        setStep("recs");

        const [rb, ro] = await Promise.all([
          api.recommendNew(steamid, discoverMode, 10),
          api.recommendOwned(steamid, 10),
        ]);
        if (cancelled) return;
        setRecsBest(rb);
        setRecsOwned(ro);
        setStep("regret");

        const rg = await api.regret(steamid, lang);
        if (cancelled) return;
        setRegret(rg);
        setStep("done");
      } catch (err: any) {
        if (cancelled) return;
        setError(err.message || "loading failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // discoverMode intentionally excluded — toggling it should NOT re-run the
    // full pipeline, only refresh the discover-new list. See effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steamid]);

  // Lightweight refetch when the user toggles discover mode after initial
  // load. Skips on first render (recsBest is null) so it doesn't double-fire
  // with the pipeline above.
  useEffect(() => {
    if (recsBest === null) return;
    let cancelled = false;
    setRecsRefreshing(true);
    api
      .recommendNew(steamid, discoverMode, 10)
      .then((r) => {
        if (!cancelled) setRecsBest(r);
      })
      .catch(() => {
        // Silent: keep existing recs visible if the toggle fetch fails.
      })
      .finally(() => {
        if (!cancelled) setRecsRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discoverMode]);

  // Refetch the regret report when the user switches UI language — the
  // diagnosis text is rendered server-side, so a frontend swap alone would
  // leave the regret prose in the old language.
  useEffect(() => {
    if (regret === null) return;
    let cancelled = false;
    api
      .regret(steamid, lang)
      .then((r) => {
        if (!cancelled) setRegret(r);
      })
      .catch(() => {
        // Silent: keep existing regret visible if the refetch fails.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  if (loading) return <LoadingState step={step} />;
  if (error) return <ErrorState message={error} />;
  if (!summary || !taste) return null;

  const personaShort = (summary.persona_name || (isDemo ? "Demo Player" : "Player"))
    .toUpperCase();
  const hoursStr = summary.total_hours.toLocaleString(undefined, {
    maximumFractionDigits: 0,
  });

  return (
    <main className="min-h-full">
      <Masthead meta={isDemo ? "iss. demo · pp-r1" : "iss. live · pp-r1"} />

      {/* Player profile spread */}
      <section className="border-b border-[var(--color-border)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
          <div className="anim-fade-up delay-1">
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--color-accent)] mb-5 flex items-center gap-3">
              <span aria-hidden>▰▰</span>
              <span>
                {t("result.playerProfile")}{isDemo && (
                  <span className="text-[var(--color-coral)]"> {t("result.demoTag")}</span>
                )}
              </span>
              <span aria-hidden>▰▰</span>
            </p>
            <div className="flex items-start gap-5 sm:gap-7">
              {summary.avatar_url && (
                <img
                  src={summary.avatar_url}
                  alt=""
                  className="w-16 h-16 sm:w-20 sm:h-20 shrink-0 border border-[var(--color-border-strong)] grayscale-[15%]"
                />
              )}
              <div className="min-w-0 flex-1">
                <h1
                  className="font-display text-[var(--color-text-hi)] mb-3 truncate"
                  style={{
                    fontSize: "clamp(2rem, 6vw, 3.75rem)",
                    lineHeight: 0.95,
                    letterSpacing: "0.01em",
                    fontWeight: 600,
                  }}
                  title={personaShort}
                >
                  {personaShort}
                </h1>
                <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1.5">
                  <span className="font-mono text-base sm:text-lg text-[var(--color-text-mid)] tabular">
                    <span className="text-[var(--color-text-hi)]">
                      {summary.library_size.toLocaleString()}
                    </span>
                    <span className="text-[var(--color-text-dim)]"> {t("result.games")}</span>
                  </span>
                  <span className="font-mono text-base sm:text-lg text-[var(--color-text-mid)] tabular">
                    <span className="text-[var(--color-text-hi)]">{hoursStr}</span>
                    <span className="text-[var(--color-text-dim)]"> {t("result.hours")}</span>
                  </span>
                  <span className="font-mono text-xs text-[var(--color-text-dim)] uppercase tracking-[0.18em] ml-auto hidden sm:inline">
                    {t("result.sidLabel")} · ····{summary.steam_id.slice(-6)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Act navigator — sticky */}
      <nav className="sticky top-0 z-10 bg-[var(--color-bg)]/95 backdrop-blur-sm border-b border-[var(--color-border)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-stretch overflow-x-auto">
            {ACTS.map((a) => {
              const isActive = tab === a.key;
              return (
                <button
                  key={a.key}
                  onClick={() => setTab(a.key)}
                  className={`flex-1 min-w-[160px] py-4 sm:py-5 px-3 text-left border-b-2 transition-colors whitespace-nowrap ${
                    isActive
                      ? "border-[var(--color-accent)]"
                      : "border-transparent hover:bg-[var(--color-surface-1)]"
                  }`}
                >
                  <div
                    className={`font-mono text-[10px] uppercase tracking-[0.25em] mb-1 ${
                      isActive
                        ? "text-[var(--color-accent)]"
                        : "text-[var(--color-text-dim)]"
                    }`}
                  >
                    {t(`result.acts.${a.roman}.kicker`)}
                  </div>
                  <div
                    className={`text-base sm:text-lg tracking-tight ${
                      isActive
                        ? "text-[var(--color-text-hi)]"
                        : "text-[var(--color-text-mid)]"
                    }`}
                    style={{ fontWeight: 600 }}
                  >
                    {t(`result.acts.${a.roman}.label`)}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Act content */}
      <section
        key={tab}
        className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12 anim-fade-up"
      >
        {tab === "taste" && <TasteProfileTab taste={taste} onSelectTab={setTab} />}
        {tab === "recs" && (
          <RecommendationsTab
            recsNew={recsBest!}
            recsOwned={recsOwned!}
            discoverMode={discoverMode}
            onDiscoverModeChange={setDiscoverMode}
            recsRefreshing={recsRefreshing}
          />
        )}
        {tab === "regret" && <RegretTab regret={regret!} />}
      </section>
    </main>
  );
}
