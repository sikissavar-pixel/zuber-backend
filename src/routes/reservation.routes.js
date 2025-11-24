import { Router } from "express";
import { authMiddleware } from "../middleware/auth.js";
import { pool } from "../config/db.js";

const r = Router();
r.use(authMiddleware);
r.get("/:id", async (req, res) => {
  const { id } = req.params;
  const row = await pool.query("SELECT * FROM reservations WHERE id=$1", [id]);
  if (row.rowCount === 0) return res.status(404).json({ ok: false, detail: "Not found" });
  return res.json(row.rows[0]);
});

export default r;