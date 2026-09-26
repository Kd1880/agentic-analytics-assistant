import { motion } from "framer-motion";
import type { DbId } from "@/lib/databases";

/** Idle illustration per world: film reel, parcel, football pitch. */
export function EmptyState({ db }: { db: DbId }) {
  return (
    <motion.div
      key={db}
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center justify-center rounded-3xl border px-6 py-16 text-center backdrop-blur-xl"
      style={{ borderColor: "var(--line)", background: "var(--surface)" }}
    >
      <motion.div
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
      >
        <svg width="132" height="132" viewBox="0 0 120 120" fill="none">
          {db === "movielens" && (
            <g>
              <circle cx="60" cy="60" r="38" stroke="var(--primary)" strokeWidth="3" opacity="0.9" />
              <circle cx="60" cy="60" r="7" fill="var(--accent)" />
              {[0, 72, 144, 216, 288].map((a) => (
                <circle
                  key={a}
                  cx={60 + 22 * Math.cos((a * Math.PI) / 180)}
                  cy={60 + 22 * Math.sin((a * Math.PI) / 180)}
                  r="7"
                  fill="var(--primary)"
                  opacity="0.55"
                />
              ))}
              <path
                d="M60 8l4.8 9.7 10.7 1.6-7.7 7.5 1.8 10.7L60 32.4l-9.6 5.1 1.8-10.7-7.7-7.5 10.7-1.6z"
                fill="var(--accent)"
                opacity="0.75"
              />
            </g>
          )}
          {db === "olist" && (
            <g>
              <rect x="30" y="46" width="60" height="54" rx="10" stroke="var(--primary)" strokeWidth="3" />
              <path d="M30 62h60" stroke="var(--primary)" strokeWidth="3" opacity="0.6" />
              <path d="M60 46v54" stroke="var(--accent)" strokeWidth="3" opacity="0.8" />
              <path
                d="M44 46c0-9 7-16 16-16s16 7 16 16"
                stroke="var(--accent)"
                strokeWidth="3"
                fill="none"
              />
              <circle cx="60" cy="24" r="5" fill="var(--accent)" opacity="0.8" />
            </g>
          )}
          {db === "soccer" && (
            <g>
              <rect x="18" y="26" width="84" height="68" rx="6" stroke="var(--primary)" strokeWidth="3" />
              <path d="M60 26v68" stroke="var(--primary)" strokeWidth="2" opacity="0.6" />
              <circle cx="60" cy="60" r="14" stroke="var(--primary)" strokeWidth="2" opacity="0.6" fill="none" />
              <path d="M18 46h14v28H18M102 46H88v28h14" stroke="var(--accent)" strokeWidth="2.5" fill="none" />
              <circle cx="60" cy="60" r="6" fill="var(--accent)" />
            </g>
          )}
        </svg>
      </motion.div>
      <p
        className="mt-6 text-lg font-semibold"
        style={{ color: "var(--text)", fontFamily: "var(--display)" }}
      >
        Ask your first question
      </p>
      <p className="mt-2 max-w-sm text-sm" style={{ color: "var(--muted)" }}>
        Type a question above, or tap one of the examples. The agent reads the live schema before
        writing any SQL.
      </p>
    </motion.div>
  );
}
