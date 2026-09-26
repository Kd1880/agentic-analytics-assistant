import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Package } from "lucide-react";
import type { DatabaseConfig } from "@/lib/databases";

/**
 * The per-database transition that plays when a world is selected.
 * Each animation uses only theme CSS variables, so it is automatically
 * rendered in that database's palette.
 */

const ease = [0.22, 1, 0.36, 1] as const;

/** MovieLens — a film leader countdown. */
function Countdown() {
  const [n, setN] = useState(3);
  useEffect(() => {
    const a = setTimeout(() => setN(2), 330);
    const b = setTimeout(() => setN(1), 660);
    return () => {
      clearTimeout(a);
      clearTimeout(b);
    };
  }, []);
  return (
    <div className="relative size-40">
      <svg viewBox="0 0 100 100" className="absolute inset-0">
        <circle cx="50" cy="50" r="46" fill="none" stroke="var(--line)" strokeWidth="2" />
        <circle cx="50" cy="50" r="36" fill="none" stroke="var(--line)" strokeWidth="1" />
        <line x1="50" y1="0" x2="50" y2="100" stroke="var(--line)" strokeWidth="1" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="var(--line)" strokeWidth="1" />
        <motion.circle
          cx="50"
          cy="50"
          r="46"
          fill="none"
          stroke="var(--primary)"
          strokeWidth="4"
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1, ease: "linear" }}
        />
      </svg>
      <motion.span
        key={n}
        initial={{ scale: 1.4, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="absolute inset-0 grid place-items-center text-6xl font-bold"
        style={{ color: "var(--accent)", fontFamily: "var(--display)" }}
      >
        {n}
      </motion.span>
    </div>
  );
}

/** Olist — a parcel dropping in and being scanned. */
function Parcel() {
  return (
    <div className="relative grid size-40 place-items-center">
      <motion.div
        initial={{ y: -140, rotate: -12, opacity: 0 }}
        animate={{ y: 0, rotate: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 320, damping: 14 }}
        className="relative grid size-24 place-items-center overflow-hidden rounded-2xl"
        style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
      >
        <Package className="size-12" />
        <motion.span
          className="absolute inset-x-0 h-1"
          style={{ background: "var(--accent)", boxShadow: "0 0 16px var(--accent)" }}
          initial={{ top: "0%" }}
          animate={{ top: ["0%", "100%", "0%"] }}
          transition={{ delay: 0.4, duration: 0.6, ease: "easeInOut" }}
        />
      </motion.div>
      <motion.span
        className="absolute bottom-4 h-2 w-24 rounded-full"
        style={{ background: "var(--glow)" }}
        initial={{ scaleX: 0.3, opacity: 0 }}
        animate={{ scaleX: 1, opacity: 1 }}
        transition={{ delay: 0.25 }}
      />
    </div>
  );
}

/** European Soccer — a ball struck into the net. */
function Goal() {
  return (
    <div className="relative h-40 w-64">
      <svg viewBox="0 0 160 100" className="absolute inset-0">
        <defs>
          <pattern id="net" width="8" height="8" patternUnits="userSpaceOnUse">
            <path d="M8 0L0 8M0 0l8 8" stroke="var(--muted)" strokeWidth="0.6" />
          </pattern>
        </defs>
        <motion.rect
          x="100"
          y="20"
          width="50"
          height="70"
          fill="url(#net)"
          animate={{ x: [100, 100, 104, 100] }}
          transition={{ duration: 1, times: [0, 0.7, 0.8, 1] }}
        />
        <path d="M100 90V20h50v70" fill="none" stroke="var(--text)" strokeWidth="3" />
        <line x1="0" y1="90" x2="160" y2="90" stroke="var(--primary)" strokeWidth="2" />
      </svg>
      <motion.div
        className="absolute size-8 rounded-full"
        style={{
          top: "calc(90% - 2rem)",
          background:
            "radial-gradient(circle at 35% 35%, var(--text) 0 40%, var(--primary) 41% 55%, var(--text) 56%)",
          boxShadow: "0 4px 10px var(--glow)",
        }}
        initial={{ left: "0%", rotate: 0 }}
        animate={{ left: "76%", rotate: 540 }}
        transition={{ duration: 0.75, ease: "easeOut" }}
      />
    </div>
  );
}

export function ThemeIntro({ db }: { db: DatabaseConfig }) {
  const label =
    db.id === "movielens" ? "Now showing" : db.id === "olist" ? "Order confirmed" : "Kick-off";
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 1.04 }}
      transition={{ duration: 0.25 }}
      className="flex min-h-screen flex-col items-center justify-center gap-6"
    >
      {db.id === "movielens" ? <Countdown /> : db.id === "olist" ? <Parcel /> : <Goal />}
      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, ease }}
        className="text-sm font-semibold tracking-[0.3em] uppercase"
        style={{ color: "var(--text)", fontFamily: "var(--display)" }}
      >
        {label}
      </motion.p>
    </motion.div>
  );
}
