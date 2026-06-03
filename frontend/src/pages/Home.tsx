import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

export default function Home() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const errorParam = params.get("error");

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(
    errorParam === "auth_failed"
      ? "Steam login didn't come back. Try paste mode or the sample below."
      : null,
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.resolveProfile(input.trim());
      navigate(`/result?steamid=${r.steam_id}`);
    } catch (err: any) {
      setError(err.message || "Couldn't resolve that profile.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-full flex flex-col">
      {/* Masthead — cartridge-style top bar */}
      <header className="border-b border-[var(--color-border)]">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-text-mid)]">
            <span className="text-[var(--color-accent)] text-sm leading-none">▣</span>
            <span>playprint <span className="text-[var(--color-text-dim)]">· steam edition</span></span>
          </div>
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-text-dim)]">
            vol.001 · 2026
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 flex flex-col">
        <div className="w-full max-w-4xl mx-auto px-6 py-12 sm:py-16">
          {/* Hero */}
          <section className="anim-fade-up delay-1 mb-14 sm:mb-20">
            <div className="flex items-baseline justify-between gap-4 mb-6">
              <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--color-accent)] flex items-center gap-3">
                <span aria-hidden>▰▰</span>
                <span>a player profile, in three acts</span>
                <span aria-hidden>▰▰</span>
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] tabular hidden sm:block">
                cat. №&nbsp;pp-01
              </p>
            </div>
            <h1
              className="font-display text-[var(--color-text-hi)] mb-7 flex flex-wrap items-end gap-x-3"
              style={{
                fontSize: "clamp(3.25rem, 11vw, 7rem)",
                lineHeight: 0.9,
                letterSpacing: "0.01em",
                fontWeight: 600,
              }}
            >
              <span>
                PLAY
                <br />
                PRINT
              </span>
              <span
                aria-hidden
                className="text-[var(--color-accent)] anim-blink"
                style={{ fontSize: "0.7em", lineHeight: 1 }}
              >
                ▮
              </span>
            </h1>
            <p className="text-[var(--color-text-mid)] text-lg sm:text-xl leading-relaxed max-w-[58ch]">
              Read your Steam library the way a friend who actually plays would.
              Three quiet chapters — what you love, what's been waiting, and the
              types you've quietly outgrown.
            </p>
          </section>

          {/* Divider — bookended ornament */}
          <div className="anim-fade-up delay-2 flex items-center gap-4 mb-10">
            <div className="h-px flex-1 bg-[var(--color-border)]" />
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--color-text-mid)] flex items-center gap-3">
              <span aria-hidden className="text-[var(--color-accent)]">◇</span>
              <span>choose entry</span>
              <span aria-hidden className="text-[var(--color-accent)]">◇</span>
            </span>
            <div className="h-px flex-1 bg-[var(--color-border)]" />
          </div>

          {/* Entry options — editorial table-of-contents style */}
          <section className="space-y-3">
            {/* 01 — OpenID */}
            <a
              href={api.steamLoginUrl()}
              className="anim-fade-up delay-3 group flex items-center gap-5 sm:gap-7 p-5 sm:p-6 bg-[var(--color-surface-1)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent-soft)] transition-colors"
            >
              <span className="font-mono text-3xl sm:text-4xl text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] transition-colors tabular shrink-0 w-12">
                01
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className="font-display text-[var(--color-text-hi)] mb-1.5"
                  style={{ fontSize: "1.625rem", lineHeight: 1.1, fontWeight: 500 }}
                >
                  sign in with steam
                </div>
                <div className="text-sm text-[var(--color-text-lo)]">
                  via OpenID — your browser's current Steam session decides who.
                </div>
              </div>
              <span className="font-mono text-xl text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] group-hover:translate-x-1 transition-all shrink-0">
                →
              </span>
            </a>

            {/* 02 — paste */}
            <form
              onSubmit={handleSubmit}
              className="anim-fade-up delay-4 p-5 sm:p-6 bg-[var(--color-surface-1)] border border-[var(--color-border)] focus-within:border-[var(--color-accent-soft)] transition-colors"
            >
              <div className="flex items-start gap-5 sm:gap-7">
                <span className="font-mono text-3xl sm:text-4xl text-[var(--color-text-dim)] tabular shrink-0 w-12 pt-0.5">
                  02
                </span>
                <div className="flex-1 min-w-0">
                  <label
                    htmlFor="sid"
                    className="font-display text-[var(--color-text-hi)] block mb-1.5"
                    style={{ fontSize: "1.625rem", lineHeight: 1.1, fontWeight: 500 }}
                  >
                    enter a steam id
                  </label>
                  <div className="text-sm text-[var(--color-text-lo)] mb-4">
                    profile URL, SteamID64, or vanity name — must be public.
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input
                      id="sid"
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="steamcommunity.com/id/..."
                      className="flex-1 bg-[var(--color-bg)] border border-[var(--color-border)] focus:border-[var(--color-accent)] px-4 py-3 text-sm text-[var(--color-text-hi)] placeholder:text-[var(--color-text-dim)] outline-none font-mono"
                      disabled={loading}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <button
                      type="submit"
                      disabled={loading || !input.trim()}
                      className="px-6 py-3 bg-[var(--color-accent)] hover:bg-[var(--color-accent-deep)] disabled:bg-[var(--color-surface-2)] disabled:text-[var(--color-text-dim)] disabled:cursor-not-allowed text-[var(--color-bg)] font-display tabular transition-colors shrink-0"
                      style={{ fontSize: "1.125rem", fontWeight: 600 }}
                    >
                      {loading ? "..." : "go ▸"}
                    </button>
                  </div>
                </div>
              </div>
            </form>

            {/* 03 — demo */}
            <button
              onClick={() => navigate("/result?steamid=-1&demo=1")}
              className="anim-fade-up delay-5 group w-full flex items-center gap-5 sm:gap-7 p-5 sm:p-6 bg-[var(--color-surface-1)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent-soft)] transition-colors text-left"
            >
              <span className="font-mono text-3xl sm:text-4xl text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] transition-colors tabular shrink-0 w-12">
                03
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className="font-display text-[var(--color-text-hi)] mb-1.5"
                  style={{ fontSize: "1.625rem", lineHeight: 1.1, fontWeight: 500 }}
                >
                  try a sample player
                </div>
                <div className="text-sm text-[var(--color-text-lo)]">
                  26 games · roguelite-leaning · a few buyer's-remorse picks · no
                  Steam account needed.
                </div>
              </div>
              <span className="font-mono text-xl text-[var(--color-text-dim)] group-hover:text-[var(--color-accent)] group-hover:translate-x-1 transition-all shrink-0">
                →
              </span>
            </button>
          </section>

          {/* Error */}
          {error && (
            <div
              role="alert"
              className="anim-fade-up mt-5 p-4 bg-[var(--color-danger-bg)] border border-[var(--color-danger)] font-mono text-sm text-[var(--color-text-hi)] flex gap-3"
            >
              <span className="text-[var(--color-coral)] shrink-0">⚠</span>
              <span>{error}</span>
            </div>
          )}

          {/* Masthead footer */}
          <footer className="anim-fade-up delay-6 mt-24 pt-8 border-t border-[var(--color-border)]">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-7">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-3">
                  privacy
                </div>
                <div className="text-sm text-[var(--color-text-lo)] leading-relaxed">
                  Profile and game details must be public. Libraries are fetched
                  live per request, never stored.
                </div>
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-3">
                  how it works
                </div>
                <div className="text-sm text-[var(--color-text-lo)] leading-relaxed">
                  TF-IDF tag similarity layered with a self-trained 50-d PPMI
                  embedding and HDBSCAN clustering. All numpy, no LLM.
                </div>
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-dim)] mb-3">
                  colophon
                </div>
                <div className="text-sm text-[var(--color-text-lo)] leading-relaxed">
                  Set in Pixelify Sans and Hanken Grotesk.{" "}
                  <a
                    href="https://github.com/373274106/steam-taste"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[var(--color-text-mid)] hover:text-[var(--color-accent)] underline underline-offset-2 decoration-[var(--color-border-strong)] hover:decoration-[var(--color-accent)] transition-colors"
                  >
                    Source on GitHub ↗
                  </a>
                </div>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </main>
  );
}
