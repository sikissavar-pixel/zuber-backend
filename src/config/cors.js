const envOrigins = (process.env.ALLOWED_ORIGINS || process.env.CORS_ORIGINS || process.env.CORS_ORIGIN || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

const staticOrigins = [
  "http://localhost:3000",
  "https://zuber-gules.vercel.app",
  "https://www.zuber-gules.vercel.app",
];

export const allowedOrigins = Array.from(new Set([...envOrigins, ...staticOrigins]));

const allowedPatterns = [
  /^https?:\/\/localhost(?::\d+)?$/,
  /^https?:\/\/127\.0\.0\.1(?::\d+)?$/,
  /^https:\/\/zuber-[a-z0-9-]+\.vercel\.app$/,
  /^https:\/\/www\.zuber-[a-z0-9-]+\.vercel\.app$/,
];

export const corsOptions = {
  origin(origin, callback) {
    const ok = !origin || allowedOrigins.includes(origin) || allowedPatterns.some((p) => p.test(origin));
    if (ok) {
      return callback(null, true);
    }
    console.error("❌ BLOCKED ORIGIN:", origin);
    return callback(new Error("CORS Not Allowed"));
  },
  credentials: true,
};
