import Masthead from "./Masthead";

type Step = "library" | "taste" | "recs" | "regret" | "done";

const STEPS: { key: Step; label: string; detail: string }[] = [
  { key: "library", label: "fetching steam library", detail: "GetOwnedGames · steam web api" },
  { key: "taste", label: "computing taste vector", detail: "playtime-weighted · TF-IDF over 5,000 games" },
  { key: "recs", label: "generating recommendations", detail: "cosine sim · exclude owned · quality filter" },
  { key: "regret", label: "detecting library regret", detail: "HDBSCAN clusters · pure / mixed classification" },
];

export default function LoadingState({ step }: { step: Step }) {
  const currentIdx = STEPS.findIndex((s) => s.key === step);
  const pct = ((currentIdx + 1) / STEPS.length) * 100;

  return (
    <main className="min-h-full flex flex-col">
      <Masthead meta="iss. loading · pp-r1" />

      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 py-12">
        <div className="w-full max-w-2xl">
          {/* Hero */}
          <div className="anim-fade-up delay-1 mb-10">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-accent)] mb-4 flex items-center gap-3">
              <span aria-hidden>▰▰</span>
              <span>developing</span>
              <span className="anim-blink" aria-hidden>▮</span>
            </p>
            <h1
              className="font-display text-[var(--color-text-hi)] mb-3"
              style={{
                fontSize: "clamp(2rem, 6vw, 3.5rem)",
                lineHeight: 0.95,
                letterSpacing: "0.01em",
                fontWeight: 600,
              }}
            >
              READING<br />YOUR LIBRARY
            </h1>
            <p className="text-[var(--color-text-mid)] text-base sm:text-lg leading-relaxed max-w-[52ch]">
              First read takes 5-10 seconds. After that, repeat visits to the same
              account are cached and return immediately.
            </p>
          </div>

          {/* Step list */}
          <ol className="space-y-1 mb-8">
            {STEPS.map((s, i) => {
              const status: "done" | "active" | "pending" =
                i < currentIdx ? "done" : i === currentIdx ? "active" : "pending";
              return (
                <li
                  key={s.key}
                  className={`grid items-baseline gap-4 py-3 border-b transition-colors ${
                    status === "active"
                      ? "border-[var(--color-accent-soft)]"
                      : "border-[var(--color-border)]/40"
                  }`}
                  style={{ gridTemplateColumns: "auto 1fr auto" }}
                >
                  <span
                    className={`font-mono text-sm tabular w-9 ${
                      status === "active"
                        ? "text-[var(--color-accent)]"
                        : status === "done"
                        ? "text-[var(--color-text-mid)]"
                        : "text-[var(--color-text-dim)]"
                    }`}
                  >
                    #{String(i + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <div
                      className={`text-base sm:text-lg ${
                        status === "active"
                          ? "text-[var(--color-text-hi)]"
                          : status === "done"
                          ? "text-[var(--color-text-mid)]"
                          : "text-[var(--color-text-dim)]"
                      }`}
                    >
                      {s.label}
                    </div>
                    <div className="text-xs text-[var(--color-text-lo)] font-mono mt-0.5">
                      {s.detail}
                    </div>
                  </div>
                  <div className="shrink-0 font-mono text-sm">
                    {status === "done" && (
                      <span className="text-[var(--color-moss)]">[✓]</span>
                    )}
                    {status === "active" && (
                      <span className="text-[var(--color-accent)]">
                        <span className="anim-blink">▮</span>
                      </span>
                    )}
                    {status === "pending" && (
                      <span className="text-[var(--color-text-dim)]">[ ]</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>

          {/* Pixel progress bar */}
          <div className="font-mono text-sm tabular flex items-center gap-3">
            <span className="text-[var(--color-text-dim)] text-[10px] uppercase tracking-[0.2em]">
              progress
            </span>
            <div
              aria-hidden
              className="flex-1 text-[var(--color-text-dim)] tracking-[-0.05em] overflow-hidden whitespace-nowrap text-sm"
              style={{ letterSpacing: 0 }}
            >
              <span className="text-[var(--color-accent)]">
                {"█".repeat(Math.max(0, Math.round(pct / 2.5)))}
              </span>
              {"░".repeat(Math.max(0, 40 - Math.round(pct / 2.5)))}
            </div>
            <span className="text-[var(--color-text-mid)] tabular w-12 text-right">
              {pct.toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
    </main>
  );
}
