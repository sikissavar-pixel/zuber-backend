import { pool } from "../config/db.js";

export async function adminStats(req, res) {
  try {
    const [{ rows: u }, { rows: da }, { rows: pa }, { rows: b }] = await Promise.all([
      pool.query("SELECT COUNT(*)::int AS count FROM users"),
      pool.query("SELECT COUNT(*)::int AS count FROM driver_applications"),
      pool.query("SELECT COUNT(*)::int AS count FROM partner_applications"),
      pool.query("SELECT COUNT(*)::int AS count FROM bids"),
    ]);
    return res.status(200).json({ success: true, message: "Stats", data: { users: u[0].count, driverApplications: da[0].count, partnerApplications: pa[0].count, bids: b[0].count } });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}