import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

interface Props {
  /** Top-right metadata — catalog number, edition, etc. */
  meta?: string;
  /** Show "back to home" link on the right. Defaults true. */
  showBack?: boolean;
}

const LANGS = ["en", "zh"] as const;
type Lang = (typeof LANGS)[number];

/**
 * Cartridge-style masthead used at the top of every page.
 * Matches the design language established on Home.
 */
export default function Masthead({ meta, showBack = true }: Props) {
  const { t, i18n } = useTranslation();
  const active: Lang = (i18n.resolvedLanguage as Lang) || "en";

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
            <span className="text-[var(--color-text-dim)]">· {t("masthead.brandSuffix")}</span>
          </span>
        </Link>
        <div className="flex items-center gap-4 sm:gap-5">
          {meta && (
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-dim)] tabular hidden sm:inline">
              {meta}
            </span>
          )}
          {/* Language toggle — small pill set, no labels needed; uppercase only */}
          <div
            role="group"
            aria-label="language"
            className="flex items-center font-mono text-[10px] tracking-[0.18em] tabular border border-[var(--color-border)]"
          >
            {LANGS.map((lng) => {
              const isActive = active === lng;
              return (
                <button
                  key={lng}
                  type="button"
                  onClick={() => i18n.changeLanguage(lng)}
                  className={`px-2 py-0.5 transition-colors ${
                    isActive
                      ? "bg-[var(--color-accent)] text-[var(--color-bg)]"
                      : "text-[var(--color-text-mid)] hover:text-[var(--color-text-hi)]"
                  }`}
                  aria-pressed={isActive}
                >
                  {t(`masthead.lang.${lng}`)}
                </button>
              );
            })}
          </div>
          {showBack && (
            <Link
              to="/"
              className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-mid)] hover:text-[var(--color-accent)] transition-colors"
            >
              ← {t("masthead.back")}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
