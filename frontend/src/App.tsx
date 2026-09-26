import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Moon, Sun } from "lucide-react";
import {
  getDatabase,
  neutralLight,
  neutralTheme,
  themeStyle,
  type DbId,
} from "@/lib/databases";
import { getDatabases, USE_MOCK, type DatabaseMeta } from "@/lib/api";
import { Landing } from "@/components/askdb/Landing";
import { Workspace } from "@/components/askdb/Workspace";
import { ThemeIntro } from "@/components/askdb/ThemeIntro";

type Mode = "light" | "dark";

export default function App() {
  const [selected, setSelected] = useState<DbId | null>(null);
  const [intro, setIntro] = useState(false);
  const [mode, setMode] = useState<Mode>("dark");
  const [meta, setMeta] = useState<Record<string, DatabaseMeta>>({});

  // follow the system preference, but remember an explicit choice
  useEffect(() => {
    const saved = localStorage.getItem("askdb-mode");
    if (saved === "light" || saved === "dark") setMode(saved);
    else if (window.matchMedia("(prefers-color-scheme: light)").matches) setMode("light");
  }, []);

  // live table/row counts from the backend (skipped in mock mode)
  useEffect(() => {
    if (USE_MOCK) return;
    void getDatabases()
      .then((list) => {
        const byId: Record<string, DatabaseMeta> = {};
        list.forEach((d) => {
          const id = d.id ?? d.name;
          if (id) byId[id] = d;
        });
        setMeta(byId);
      })
      .catch(() => setMeta({}));
  }, []);

  const toggleMode = () => {
    const next: Mode = mode === "dark" ? "light" : "dark";
    setMode(next);
    localStorage.setItem("askdb-mode", next);
  };

  const base = selected ? getDatabase(selected) : null;
  const theme = base
    ? mode === "light"
      ? base.light
      : base.theme
    : mode === "light"
      ? neutralLight
      : neutralTheme;
  const db = base ? { ...base, theme } : null;

  const pick = (id: DbId) => {
    setSelected(id);
    setIntro(true);
    setTimeout(() => setIntro(false), 1100);
  };

  const toggle = (
    <button
      onClick={toggleMode}
      aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className="grid size-9 shrink-0 place-items-center rounded-xl border transition-transform hover:scale-105"
      style={{ borderColor: "var(--line)", background: "var(--surface)", color: "var(--text)" }}
    >
      {mode === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );

  return (
    <div
      className="relative min-h-screen overflow-hidden transition-colors duration-500"
      style={{
        ...themeStyle(theme),
        background: theme.bg,
        color: theme.text,
        fontFamily: '"Inter", system-ui, sans-serif',
      }}
    >
      {/* the per-world texture, cross-faded on every theme change */}
      <AnimatePresence mode="sync">
        <motion.div
          key={`${selected ?? "neutral"}-${mode}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: "easeInOut" }}
          className="pointer-events-none absolute inset-0"
          style={{ background: theme.texture }}
        />
      </AnimatePresence>

      {/* film-grain overlay */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.16] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E\")",
        }}
      />

      {!db && <div className="absolute top-4 right-4 z-30 sm:top-6 sm:right-6">{toggle}</div>}

      <div className="relative">
        <AnimatePresence mode="wait">
          {db && intro ? (
            <ThemeIntro key={`intro-${db.id}`} db={db} />
          ) : db ? (
            <motion.div
              key={db.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <Workspace db={db} onSwitch={() => setSelected(null)} toggle={toggle} />
            </motion.div>
          ) : (
            <motion.div
              key="landing"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <Landing onPick={pick} mode={mode} meta={meta} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
