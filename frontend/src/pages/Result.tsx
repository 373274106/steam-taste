import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type { ProfileSummary, TasteProfile, RegretReport, RecommendResponse } from "../lib/types";
import TasteProfileTab from "../components/TasteProfileTab";
import RecommendationsTab from "../components/RecommendationsTab";
import RegretTab from "../components/RegretTab";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";

type Tab = "taste" | "recs" | "regret";

type LoadStep = "library" | "taste" | "recs" | "regret" | "done";

export default function Result() {
  const [params] = useSearchParams();
  const steamidParam = params.get("steamid");
  const isDemo = params.get("demo") === "1" || steamidParam === "-1";
  const steamid = steamidParam ?? "-1";

  const [tab, setTab] = useState<Tab>("taste");

  const [summary, setSummary] = useState<ProfileSummary | null>(null);
  const [taste, setTaste] = useState<TasteProfile | null>(null);
  const [recsBest, setRecsBest] = useState<RecommendResponse | null>(null);
  const [recsOwned, setRecsOwned] = useState<RecommendResponse | null>(null);
  const [regret, setRegret] = useState<RegretReport | null>(null);

  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState<LoadStep>("library");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setStep("library");

    (async () => {
      try {
        // Fetch in stages so the loading screen can advance through steps.
        // Library + summary first (depends on Steam API, slowest)
        const s = await api.profileSummary(steamid);
        if (cancelled) return;
        setSummary(s);
        setStep("taste");

        const t = await api.tasteProfile(steamid);
        if (cancelled) return;
        setTaste(t);
        setStep("recs");

        const [rb, ro] = await Promise.all([
          api.recommendNew(steamid, "best_fit", 10),
          api.recommendOwned(steamid, 10),
        ]);
        if (cancelled) return;
        setRecsBest(rb);
        setRecsOwned(ro);
        setStep("regret");

        const rg = await api.regret(steamid);
        if (cancelled) return;
        setRegret(rg);
        setStep("done");
      } catch (err: any) {
        if (cancelled) return;
        setError(err.message || "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [steamid]);

  if (loading) {
    return <LoadingState step={step} />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!summary || !taste) return null;

  return (
    <div className="min-h-full">
      {/* Top bar */}
      <div className="sticky top-0 z-10 bg-slate-950/90 backdrop-blur border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center gap-3 sm:gap-4">
          {summary.avatar_url && (
            <img
              src={summary.avatar_url}
              alt=""
              className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg flex-shrink-0"
            />
          )}
          <div className="flex-1 min-w-0">
            <div className="font-semibold truncate">
              {summary.persona_name || (isDemo ? "Demo Player" : "Player")}
            </div>
            <div className="text-xs text-slate-400">
              {summary.library_size} games · {summary.total_hours.toLocaleString()} hours
              {isDemo && <span className="ml-2 text-blue-400">DEMO</span>}
            </div>
          </div>
          <Link to="/" className="text-sm text-slate-400 hover:text-slate-200 flex-shrink-0">
            换一个 →
          </Link>
        </div>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex gap-2 -mb-px overflow-x-auto scrollbar-thin">
          {([
            ["taste", "📊 Taste"],
            ["recs", "💎 Recommendations"],
            ["regret", "💀 Library Regret"],
          ] as const).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`px-3 sm:px-4 py-2 text-sm border-b-2 transition whitespace-nowrap ${
                tab === k
                  ? "border-[var(--color-steam-blue)] text-white"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content — key on tab so React unmounts/remounts → fresh fade-in */}
      <div key={tab} className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8 fade-in">
        {tab === "taste" && <TasteProfileTab taste={taste} onSelectTab={setTab} />}
        {tab === "recs" && (
          <RecommendationsTab recsNew={recsBest!} recsOwned={recsOwned!} />
        )}
        {tab === "regret" && <RegretTab regret={regret!} />}
      </div>
    </div>
  );
}
