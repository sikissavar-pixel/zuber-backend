import pg from "pg";
import bcrypt from "bcryptjs";

const { Pool } = pg;

const connectionString =
  process.env.DATABASE_URL ||
  process.env.RAILWAY_DATABASE_URL ||
  process.env.POSTGRES_URL ||
  process.env.POSTGRES_PRISMA_URL ||
  process.env.PG_CONNECTION_STRING;
if (!connectionString) {
  throw new Error("DATABASE_URL not found");
}

const sslEnv = (process.env.DATABASE_SSL ?? "true").toString().toLowerCase();
const useSsl = sslEnv !== "false";

export const pool = new Pool({ connectionString, ssl: useSsl ? { rejectUnauthorized: false } : false });

export async function initDb() {
  await pool.query(
    "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255), password TEXT NOT NULL, role VARCHAR(32) NOT NULL, created_at TIMESTAMP DEFAULT NOW())"
  );
  await pool.query(
    "CREATE TABLE IF NOT EXISTS reservations (id SERIAL PRIMARY KEY, partner_id INTEGER NOT NULL REFERENCES users(id), pickup TEXT, dropoff TEXT, scheduled_at TIMESTAMP, status VARCHAR(32) DEFAULT 'open', created_at TIMESTAMP DEFAULT NOW())"
  );
  await pool.query(
    "CREATE TABLE IF NOT EXISTS bids (id SERIAL PRIMARY KEY, reservation_id INTEGER NOT NULL REFERENCES reservations(id), driver_id INTEGER NOT NULL REFERENCES users(id), amount INTEGER NOT NULL, created_at TIMESTAMP DEFAULT NOW())"
  );
  await pool.query(
    "CREATE TABLE IF NOT EXISTS driver_applications (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, phone VARCHAR(64), license_type VARCHAR(64), experience VARCHAR(64), description TEXT, status VARCHAR(32) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())"
  );
  await pool.query(
    "CREATE TABLE IF NOT EXISTS partner_applications (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, phone VARCHAR(64), car_model VARCHAR(64), description TEXT, status VARCHAR(32) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())"
  );
}

export async function ensureAdmin() {
  const email = "ysr@gmail.com";
  const password = "Aslan123";
  const role = "admin";

  const check = await pool.query("SELECT id FROM users WHERE email = $1 LIMIT 1", [email]);
  const hashed = await bcrypt.hash(password, 10);
  if (check.rows.length === 0) {
    await pool.query("INSERT INTO users (email, name, password, role) VALUES ($1,$2,$3,$4)", [email, "Admin", hashed, role]);
    console.log("🔥 Admin user created:", email);
  } else {
    await pool.query("UPDATE users SET password=$1, role=$2, name=$3 WHERE email=$4", [hashed, role, "Admin", email]);
    console.log("✔ Admin password reset and role ensured:", email);
  }
}