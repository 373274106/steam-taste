import { useTranslation } from "react-i18next";
import tagMap from "../locales/tag_i18n.json";

const MAP = tagMap as Record<string, string>;

/**
 * Returns a function that maps a SteamSpy tag (always English in our corpus)
 * to its localized label for the active UI language. Falls through to the
 * raw English tag for any name not in the map (long-tail / brand-name tags
 * Steam doesn't localize, ~10% of the vocab).
 */
export function useTagLabel(): (tag: string) => string {
  const { i18n } = useTranslation();
  const lang = i18n.resolvedLanguage || "en";
  if (lang === "zh") {
    return (tag) => MAP[tag] || tag;
  }
  return (tag) => tag;
}
