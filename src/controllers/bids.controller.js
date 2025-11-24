import { pool } from "../config/db.js";

export async function createBid(req, res) {
  try {
    const { reservation_ref, driver_id, amount } = req.body || {};
    if (!reservation_ref || !amount) return res.status(400).json({ success: false, message: "Missing fields" });
    const ins = await pool.query(
      "INSERT INTO bids(reservation_ref,driver_id,amount) VALUES($1,$2,$3) RETURNING id,reservation_ref,driver_id,amount,created_at",
      [reservation_ref, driver_id || null, amount]
    );
    const io = req.app.get("io");
    if (io) io.emit("bid:new", ins.rows[0]);
    return res.status(201).json({ success: true, message: "Bid created", data: ins.rows[0] });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}

export async function getBid(req, res) {
  try {
    const { id } = req.params;
    const r = await pool.query("SELECT id,reservation_ref,driver_id,amount,created_at FROM bids WHERE id=$1", [id]);
    if (!r.rows.length) return res.status(404).json({ success: false, message: "Not found" });
    return res.status(200).json({ success: true, message: "Bid", data: r.rows[0] });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}