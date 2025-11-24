import { pool } from "../config/db.js";

export async function partnerApplyGet(req, res) {
  try {
    const q = await pool.query("SELECT id,user_email,name,status,created_at FROM partner_applications ORDER BY created_at DESC LIMIT 50");
    return res.status(200).json({ success: true, message: "Partner applications", data: q.rows });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}

export async function partnerApplyPost(req, res) {
  try {
    const { email, name } = req.body || {};
    if (!email) return res.status(400).json({ success: false, message: "Missing email" });
    const ins = await pool.query(
      "INSERT INTO partner_applications(user_email,name) VALUES($1,$2) RETURNING id,user_email,name,status,created_at",
      [email, name || null]
    );
    return res.status(201).json({ success: true, message: "Application submitted", data: ins.rows[0] });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}