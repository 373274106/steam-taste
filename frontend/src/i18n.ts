import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./locales/en.json";
import zh from "./locales/zh.json";

/**
 * Playprint i18n bootstrap.
 *
 * Detection order: ?lang= URL param → localStorage → <html lang> → browser.
 * Resources are bundled (small), so there's no runtime fetch.
 *
 * Locale keys are organized by surface (home / result / taste / recs /
 * regret / loading / error / common). New strings go in BOTH json files;
 * en is the source of truth — if a key is missing in zh, en renders.
 */
void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, zh: { translation: zh } },
    fallbackLng: "en",
    supportedLngs: ["en", "zh"],
    interpolation: { escapeValue: false },
    detection: {
      order: ["querystring", "localStorage", "htmlTag", "navigator"],
      lookupQuerystring: "lang",
      lookupLocalStorage: "playprint.lang",
      caches: ["localStorage"],
    },
  });

export default i18n;
