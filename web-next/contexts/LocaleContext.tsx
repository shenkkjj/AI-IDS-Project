"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

type Locale = "zh" | "en";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (path: string) => string;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: "zh",
  setLocale: () => {},
  t: (p: string) => p,
});

let _messagesCache: Record<string, Record<string, string>> = {};

async function loadMessages(locale: Locale) {
  if (_messagesCache[locale]) return _messagesCache[locale];
  const mod = await import(`@/locales/${locale}.json`);
  _messagesCache[locale] = flattenMessages(mod.default || mod);
  return _messagesCache[locale];
}

function flattenMessages(
  nested: Record<string, unknown>,
  prefix = ""
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(nested)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      Object.assign(result, flattenMessages(value as Record<string, unknown>, fullKey));
    } else if (typeof value === "string") {
      result[fullKey] = value;
    }
  }
  return result;
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");
  const [messages, setMessages] = useState<Record<string, string>>({});

  useEffect(() => {
    const stored = localStorage.getItem("cyber-locale") as Locale | null;
    if (stored === "zh" || stored === "en") {
      setLocaleState(stored);
    }
  }, []);

  useEffect(() => {
    loadMessages(locale).then(setMessages);
    localStorage.setItem("cyber-locale", locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((l: Locale) => setLocaleState(l), []);

  const t = useCallback(
    (path: string) => messages[path] || path,
    [messages]
  );

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}
