import { Link } from "react-router-dom";
import Masthead from "./Masthead";

interface Props {
  message: string;
}

interface Diagnosis {
  marker: string;
  title: string;
  body: React.ReactNode;
  cta?: { label: string; href: string };
}

function diagnose(message: string): Diagnosis {
  const m = message.toLowerCase();

  if (
    m.includes("private") ||
    m.includes("no library data") ||
    m.includes("profile may be private")
  ) {
    return {
      marker: "err.privacy",
      title: "your library is private",
      body: (
        <>
          <p>
            Steam keeps your library hidden by default. We can't read what we
            can't see.
          </p>
          <p className="mt-3">Two switches both need to be on:</p>
          <ul className="mt-2 space-y-1 text-[var(--color-text-mid)]">
            <li className="font-mono text-sm">
              <span className="text-[var(--color-accent)]">▸</span> my profile{" "}
              <span className="text-[var(--color-text-dim)]">→ public</span>
            </li>
            <li className="font-mono text-sm">
              <span className="text-[var(--color-accent)]">▸</span> game details{" "}
              <span className="text-[var(--color-text-dim)]">→ public</span>
              <span className="text-[var(--color-text-lo)] ml-2 text-xs">
                (easy to miss — separate toggle)
              </span>
            </li>
          </ul>
        </>
      ),
      cta: {
        label: "steam privacy settings",
        href: "https://steamcommunity.com/my/edit/settings",
      },
    };
  }

  if (
    m.includes("vanity") ||
    m.includes("not found") ||
    m.includes("cannot interpret")
  ) {
    return {
      marker: "err.404",
      title: "no player by that name",
      body: (
        <>
          <p>We couldn't resolve that SteamID, vanity name, or profile URL.</p>
          <p className="mt-3">Common reasons:</p>
          <ul className="mt-2 space-y-1 text-[var(--color-text-mid)] font-mono text-sm">
            <li>
              <span className="text-[var(--color-accent)]">▸</span> vanity name
              typo
            </li>
            <li>
              <span className="text-[var(--color-accent)]">▸</span> account
              deleted or locked
            </li>
            <li>
              <span className="text-[var(--color-accent)]">▸</span> not a valid
              17-digit SteamID64
            </li>
          </ul>
        </>
      ),
    };
  }

  if (
    m.includes("network") ||
    m.includes("503") ||
    m.includes("502") ||
    m.includes("timeout") ||
    m.includes("fetch")
  ) {
    return {
      marker: "err.net",
      title: "the line went quiet",
      body: (
        <>
          <p>The backend or Steam didn't answer in time. Could be:</p>
          <ul className="mt-2 space-y-1 text-[var(--color-text-mid)] font-mono text-sm">
            <li>
              <span className="text-[var(--color-accent)]">▸</span> render free
              tier cold start (30s warm-up)
            </li>
            <li>
              <span className="text-[var(--color-accent)]">▸</span> steam web
              api rate limit
            </li>
            <li>
              <span className="text-[var(--color-accent)]">▸</span> your network
              can't reach steampowered.com
            </li>
          </ul>
          <p className="mt-4 text-xs text-[var(--color-text-lo)] font-mono break-all">
            <span className="text-[var(--color-text-dim)] uppercase tracking-wider">
              raw:{" "}
            </span>
            {message}
          </p>
        </>
      ),
    };
  }

  return {
    marker: "err.unknown",
    title: "something went sideways",
    body: (
      <>
        <p>
          An unexpected error. Paste this somewhere so we can diagnose:
        </p>
        <pre className="mt-4 p-4 bg-[var(--color-surface-1)] border border-[var(--color-border)] text-xs text-[var(--color-text-mid)] font-mono whitespace-pre-wrap overflow-x-auto">
          {message}
        </pre>
      </>
    ),
  };
}

export default function ErrorState({ message }: Props) {
  const d = diagnose(message);

  return (
    <main className="min-h-full flex flex-col">
      <Masthead meta={`iss. ${d.marker}`} />

      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 py-12">
        <div className="w-full max-w-2xl">
          <div className="anim-fade-up delay-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--color-coral)] mb-4 flex items-center gap-3">
              <span aria-hidden>▰▰</span>
              <span>{d.marker}</span>
              <span aria-hidden>▰▰</span>
            </p>
            <h1
              className="font-display text-[var(--color-text-hi)] mb-6"
              style={{
                fontSize: "clamp(1.875rem, 5.5vw, 3rem)",
                lineHeight: 1,
                letterSpacing: "0.01em",
                fontWeight: 600,
              }}
            >
              {d.title}
            </h1>
            <div className="text-[var(--color-text-mid)] text-base sm:text-lg leading-relaxed max-w-[52ch]">
              {d.body}
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-5 py-3 bg-[var(--color-surface-1)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent-soft)] font-mono text-sm uppercase tracking-[0.15em] text-[var(--color-text-mid)] hover:text-[var(--color-text-hi)] transition-colors"
              >
                <span>←</span> new entry
              </Link>
              {d.cta && (
                <a
                  href={d.cta.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-3 bg-[var(--color-accent)] hover:bg-[var(--color-accent-deep)] text-[var(--color-bg)] font-mono uppercase tracking-[0.15em] tabular transition-colors"
                  style={{ fontSize: "0.875rem", fontWeight: 600 }}
                >
                  {d.cta.label} <span>↗</span>
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
