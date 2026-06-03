import { Link } from "react-router-dom";

interface Props {
  /** Top-right metadata — catalog number, edition, etc. */
  meta?: string;
  /** Show "back to home" link on the right. Defaults true. */
  showBack?: boolean;
}

/**
 * Cartridge-style masthead used at the top of every page.
 * Matches the design language established on Home.
 */
export default function Masthead({ meta, showBack = true }: Props) {
  return (
    <header className="border-b border-[var(--color-border)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between gap-4">
        <Link
          to="/"
          className="flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-text-mid)] hover:text-[var(--color-text-hi)] transition-colors"
        >
          <span className="text-[var(--color-accent)] text-sm leading-none">▣</span>
          <span>
            playprint{" "}
            <span className="text-[var(--color-text-dim)]">· steam edition</span>
          </span>
        </Link>
        <div className="flex items-center gap-5">
          {meta && (
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] tabular hidden sm:inline">
              {meta}
            </span>
          )}
          {showBack && (
            <Link
              to="/"
              className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-mid)] hover:text-[var(--color-accent)] transition-colors"
            >
              ← new entry
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
