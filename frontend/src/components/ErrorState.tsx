import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Masthead from "./Masthead";

interface Props {
  message: string;
}

type DiagnosisKind = "privacy" | "notFound" | "network" | "unknown";

interface Diagnosis {
  kind: DiagnosisKind;
  marker: string;
}

function diagnose(message: string): Diagnosis {
  const m = message.toLowerCase();

  if (
    m.includes("private") ||
    m.includes("no library data") ||
    m.includes("profile may be private")
  ) {
    return { kind: "privacy", marker: "err.privacy" };
  }

  if (
    m.includes("vanity") ||
    m.includes("not found") ||
    m.includes("cannot interpret")
  ) {
    return { kind: "notFound", marker: "err.404" };
  }

  if (
    m.includes("network") ||
    m.includes("503") ||
    m.includes("502") ||
    m.includes("timeout") ||
    m.includes("fetch")
  ) {
    return { kind: "network", marker: "err.net" };
  }

  return { kind: "unknown", marker: "err.unknown" };
}

const PRIVACY_CTA_HREF = "https://steamcommunity.com/my/edit/settings";

export default function ErrorState({ message }: Props) {
  const { t } = useTranslation();
  const d = diagnose(message);

  const title = t(`errorState.${d.kind}.title`);

  const body = (() => {
    if (d.kind === "privacy") {
      return (
        <>
          <p>{t("errorState.privacy.body")}</p>
          <p className="mt-3">{t("errorState.privacy.togglesIntro")}</p>
          <ul className="mt-2 space-y-1 text-[var(--color-text-mid)]">
            <li className="font-mono text-sm">
              <span className="text-[var(--color-accent)]">▸</span>{" "}
              {t("errorState.privacy.toggleProfileLabel")}{" "}
              <span className="text-[var(--color-text-dim)]">
                {t("errorState.privacy.toggleProfileValue")}
              </span>
            </li>
            <li className="font-mono text-sm">
              <span className="text-[var(--color-accent)]">▸</span>{" "}
              {t("errorState.privacy.toggleDetailsLabel")}{" "}
              <span className="text-[var(--color-text-dim)]">
                {t("errorState.privacy.toggleDetailsValue")}
              </span>
              <span className="text-[var(--color-text-lo)] ml-2 text-xs">
                {t("errorState.privacy.toggleDetailsNote")}
              </span>
            </li>
          </ul>
        </>
      );
    }

    if (d.kind === "notFound") {
      const reasonKeys = [
        "errorState.notFound.reasonVanity",
        "errorState.notFound.reasonDeleted",
        "errorState.notFound.reasonInvalid",
      ];
      return (
        <>
          <p>{t("errorState.notFound.body")}</p>
          <p className="mt-3">{t("errorState.notFound.reasonsIntro")}</p>
          <ul className="mt-2 space-y-1 text-[var(--color-text-mid)] font-mono text-sm">
            {reasonKeys.map((k) => (
              <li key={k}>
                <span className="text-[var(--color-accent)]">▸</span> {t(k)}
              </li>
            ))}
          </ul>
        </>
      );
    }

    if (d.kind === "network") {
      const reasonKeys = [
        "errorState.network.reasonCold",
        "errorState.network.reasonRate",
        "errorState.network.reasonReach",
      ];
      return (
        <>
          <p>{t("errorState.network.body")}</p>
          <ul className="mt-2 space-y-1 text-[var(--color-text-mid)] font-mono text-sm">
            {reasonKeys.map((k) => (
              <li key={k}>
                <span className="text-[var(--color-accent)]">▸</span> {t(k)}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-[var(--color-text-lo)] font-mono break-all">
            <span className="text-[var(--color-text-dim)] uppercase tracking-wider">
              {t("errorState.network.rawLabel")}{" "}
            </span>
            {message}
          </p>
        </>
      );
    }

    return (
      <>
        <p>{t("errorState.unknown.body")}</p>
        <pre className="mt-4 p-4 bg-[var(--color-surface-1)] border border-[var(--color-border)] text-xs text-[var(--color-text-mid)] font-mono whitespace-pre-wrap overflow-x-auto">
          {message}
        </pre>
      </>
    );
  })();

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
              {title}
            </h1>
            <div className="text-[var(--color-text-mid)] text-base sm:text-lg leading-relaxed max-w-[52ch]">
              {body}
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-5 py-3 bg-[var(--color-surface-1)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent-soft)] font-mono text-sm uppercase tracking-[0.15em] text-[var(--color-text-mid)] hover:text-[var(--color-text-hi)] transition-colors"
              >
                <span>←</span> {t("masthead.back")}
              </Link>
              {d.kind === "privacy" && (
                <a
                  href={PRIVACY_CTA_HREF}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-3 bg-[var(--color-accent)] hover:bg-[var(--color-accent-deep)] text-[var(--color-bg)] font-mono uppercase tracking-[0.15em] tabular transition-colors"
                  style={{ fontSize: "0.875rem", fontWeight: 600 }}
                >
                  {t("errorState.privacy.ctaLabel")} <span>↗</span>
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
