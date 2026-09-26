import { Film, ShoppingBag, Trophy, type LucideIcon } from "lucide-react";
import type { CSSProperties } from "react";

/**
 * Per-database design system.
 *
 * Each database is a "world" with its own palette, display font and background
 * texture. themeStyle() writes these as CSS custom properties onto the app
 * wrapper, so selecting a database re-skins the entire UI.
 *
 * Design tokens (colours, fonts, textures, chart palettes) follow the Lovable
 * reference. Table/row counts and example questions are the REAL values from
 * this project's databases and gold question set.
 */

export type DbId = "movielens" | "olist" | "soccer";

export type ThemeTokens = {
  bg: string;
  surface: string;
  surfaceStrong: string;
  primary: string;
  primaryFg: string;
  accent: string;
  text: string;
  muted: string;
  border: string;
  glow: string;
  display: string;
  texture: string;
  chartColors: string[];
};

export type DatabaseConfig = {
  id: DbId;
  label: string;
  tagline: string;
  themeName: string;
  icon: LucideIcon;
  tables: number;
  rows: string;
  engine: string;
  chips: string[];
  placeholder: string;
  theme: ThemeTokens;
  light: ThemeTokens;
};

export const neutralTheme: ThemeTokens = {
  bg: "#08090C",
  surface: "rgba(255,255,255,0.04)",
  surfaceStrong: "rgba(255,255,255,0.07)",
  primary: "#8B8FF7",
  primaryFg: "#0B0B0F",
  accent: "#63E6BE",
  text: "#F4F5F7",
  muted: "#9AA0AA",
  border: "rgba(255,255,255,0.10)",
  glow: "rgba(139,143,247,0.35)",
  display: '"Sora", system-ui, sans-serif',
  texture:
    "radial-gradient(900px 500px at 50% -10%, rgba(139,143,247,0.20), transparent 70%)",
  chartColors: ["#8B8FF7", "#63E6BE", "#F5C518", "#FF8FA3", "#7FB3FF"],
};

export const neutralLight: ThemeTokens = {
  bg: "#F6F6F9",
  surface: "rgba(255,255,255,0.7)",
  surfaceStrong: "rgba(255,255,255,0.92)",
  primary: "#5157D9",
  primaryFg: "#FFFFFF",
  accent: "#0E9F74",
  text: "#14151A",
  muted: "#5D6270",
  border: "rgba(20,21,26,0.10)",
  glow: "rgba(81,87,217,0.25)",
  display: '"Sora", system-ui, sans-serif',
  texture:
    "radial-gradient(900px 500px at 50% -10%, rgba(139,143,247,0.22), transparent 70%)",
  chartColors: ["#5157D9", "#0E9F74", "#C99A06", "#E0506A", "#3A7BD5"],
};

export const databases: DatabaseConfig[] = [
  {
    id: "movielens",
    label: "MovieLens",
    tagline: "Movies, ratings & genres.",
    themeName: "Cinema",
    icon: Film,
    tables: 4,
    rows: "124K",
    engine: "PostgreSQL",
    chips: [
      "How many movies are there per genre?",
      "Which 10 movies have the most ratings?",
      "What is the average rating per genre?",
      "How many ratings were made in each year?",
    ],
    placeholder: "Ask about movies, ratings or genres…",
    light: {
      bg: "#FBF6EE",
      surface: "rgba(255,255,255,0.72)",
      surfaceStrong: "rgba(255,255,255,0.92)",
      primary: "#B01E32",
      primaryFg: "#FFF6F7",
      accent: "#9A6B00",
      text: "#1E1414",
      muted: "#6B5A55",
      border: "rgba(176,30,50,0.18)",
      glow: "rgba(176,30,50,0.25)",
      display: '"Playfair Display", Georgia, serif',
      texture:
        "radial-gradient(1000px 520px at 50% -15%, rgba(215,38,61,0.16), transparent 70%), radial-gradient(600px 300px at 90% 10%, rgba(245,197,24,0.18), transparent 70%)",
      chartColors: ["#B01E32", "#C99A06", "#E0603F", "#7A1424", "#8C7A3C"],
    },
    theme: {
      bg: "#0B0B0F",
      surface: "rgba(255,255,255,0.045)",
      surfaceStrong: "rgba(255,255,255,0.08)",
      primary: "#D7263D",
      primaryFg: "#FFF6F7",
      accent: "#F5C518",
      text: "#F7F3EE",
      muted: "#A79F98",
      border: "rgba(245,197,24,0.18)",
      glow: "rgba(215,38,61,0.40)",
      display: '"Playfair Display", Georgia, serif',
      texture:
        "radial-gradient(1000px 520px at 50% -15%, rgba(215,38,61,0.35), transparent 70%), radial-gradient(600px 300px at 90% 10%, rgba(245,197,24,0.16), transparent 70%), radial-gradient(1200px 700px at 50% 120%, rgba(0,0,0,0.85), transparent 60%)",
      chartColors: ["#D7263D", "#F5C518", "#FF7A5C", "#9B1B30", "#EAD9A0"],
    },
  },
  {
    id: "olist",
    label: "Olist",
    tagline: "Orders, sellers & deliveries.",
    themeName: "Marketplace",
    icon: ShoppingBag,
    tables: 9,
    rows: "1.55M",
    engine: "PostgreSQL",
    chips: [
      "What are the top 10 product categories by revenue, using the English category names?",
      "What is the average delivery time in days for delivered orders?",
      "How many orders are there per customer state?",
      "What is the distribution of payment types?",
    ],
    placeholder: "Ask about orders, sellers or deliveries…",
    light: {
      bg: "#F3FAF7",
      surface: "rgba(255,255,255,0.75)",
      surfaceStrong: "rgba(255,255,255,0.95)",
      primary: "#0B8577",
      primaryFg: "#F2FFFC",
      accent: "#A86F00",
      text: "#0E2623",
      muted: "#4F6E68",
      border: "rgba(11,133,119,0.20)",
      glow: "rgba(11,133,119,0.25)",
      display: '"Sora", system-ui, sans-serif',
      texture:
        "radial-gradient(900px 480px at 20% -10%, rgba(25,196,178,0.20), transparent 70%), radial-gradient(700px 400px at 85% 0%, rgba(255,201,74,0.22), transparent 70%)",
      chartColors: ["#0B8577", "#E0A21A", "#22A355", "#1E6E8A", "#E0763A"],
    },
    theme: {
      bg: "#0F1F1E",
      surface: "rgba(255,252,244,0.07)",
      surfaceStrong: "rgba(255,252,244,0.11)",
      primary: "#19C4B2",
      primaryFg: "#04211E",
      accent: "#FFC94A",
      text: "#F4FBF7",
      muted: "#9FC0B8",
      border: "rgba(25,196,178,0.22)",
      glow: "rgba(15,157,143,0.45)",
      display: '"Sora", system-ui, sans-serif',
      texture:
        "radial-gradient(900px 480px at 20% -10%, rgba(15,157,143,0.40), transparent 70%), radial-gradient(700px 400px at 85% 0%, rgba(255,201,74,0.20), transparent 70%), radial-gradient(800px 500px at 70% 110%, rgba(0,153,67,0.18), transparent 70%)",
      chartColors: ["#19C4B2", "#FFC94A", "#4ADE80", "#1E88A8", "#FF9F68"],
    },
  },
  {
    id: "soccer",
    label: "European Soccer",
    tagline: "Matches, goals & players.",
    themeName: "Stadium",
    icon: Trophy,
    tables: 7,
    rows: "222K",
    engine: "SQLite",
    chips: [
      "How many matches were played per league?",
      "Which are the top 10 teams by total goals scored (home and away combined)?",
      "How many matches ended in a home win, an away win, and a draw overall?",
      "Who are the top 10 players by average overall rating across their attribute records?",
    ],
    placeholder: "Ask about matches, goals or players…",
    light: {
      bg: "#EEF8F1",
      surface: "rgba(255,255,255,0.75)",
      surfaceStrong: "rgba(255,255,255,0.95)",
      primary: "#138A43",
      primaryFg: "#F2FFF6",
      accent: "#0A2E1B",
      text: "#0A2415",
      muted: "#4A6B56",
      border: "rgba(10,46,27,0.16)",
      glow: "rgba(19,138,67,0.25)",
      display: '"Oswald", "Archivo", system-ui, sans-serif',
      texture:
        "radial-gradient(1100px 500px at 50% -20%, rgba(59,224,122,0.22), transparent 65%), repeating-linear-gradient(90deg, rgba(19,138,67,0.05) 0 2px, transparent 2px 120px)",
      chartColors: ["#138A43", "#0A2E1B", "#3BB26A", "#6FAF86", "#1E5E3A"],
    },
    theme: {
      bg: "#0A2E1B",
      surface: "rgba(255,255,255,0.07)",
      surfaceStrong: "rgba(255,255,255,0.11)",
      primary: "#3BE07A",
      primaryFg: "#07230F",
      accent: "#FFFFFF",
      text: "#F2FFF6",
      muted: "#A6C9B2",
      border: "rgba(255,255,255,0.22)",
      glow: "rgba(255,255,255,0.35)",
      display: '"Oswald", "Archivo", system-ui, sans-serif',
      texture:
        "radial-gradient(1100px 500px at 50% -20%, rgba(255,255,255,0.22), transparent 65%), linear-gradient(180deg, rgba(18,79,44,0.85), rgba(10,46,27,0.95)), repeating-linear-gradient(90deg, rgba(255,255,255,0.045) 0 2px, transparent 2px 120px)",
      chartColors: ["#3BE07A", "#FFFFFF", "#9BE7B8", "#1FA75C", "#D7F5E3"],
    },
  },
];

export const getDatabase = (id: DbId) =>
  databases.find((d) => d.id === id) ?? databases[0];

export function themeStyle(t: ThemeTokens): CSSProperties {
  return {
    ["--bg" as string]: t.bg,
    ["--surface" as string]: t.surface,
    ["--surface-strong" as string]: t.surfaceStrong,
    ["--primary" as string]: t.primary,
    ["--primary-fg" as string]: t.primaryFg,
    ["--accent" as string]: t.accent,
    ["--text" as string]: t.text,
    ["--muted" as string]: t.muted,
    ["--line" as string]: t.border,
    ["--glow" as string]: t.glow,
    ["--display" as string]: t.display,
  } as CSSProperties;
}
