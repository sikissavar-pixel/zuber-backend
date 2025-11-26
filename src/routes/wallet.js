import { Router } from "express";
import { pool } from "../config/db.js";
import { authMiddleware } from "../middleware/auth.js";

const router = Router();

async function ensureWalletRecord(userId) {
  await pool.query("INSERT INTO wallets (user_id, balance) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING", [userId]);
}

router.post("/add-test-balance", authMiddleware, async (req, res) => {
  try {
    const userId = req.user?.id;
    if (!userId) return res.status(401).json({ success: false, message: "Unauthorized" });

    await ensureWalletRecord(userId);
    const update = await pool.query(
      "UPDATE wallets SET balance = balance + $1 WHERE user_id = $2 RETURNING balance",
      [500, userId]
    );
    return res.json({ success: true, message: "Balance added", data: { balance: update.rows[0].balance } });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
});

export default router;
