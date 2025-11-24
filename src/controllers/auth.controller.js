import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { pool } from "../config/db.js";

export async function register(req, res) {
  try {
    const { email, name, password, role } = req.body || {};
    if (!email || !name || !password) return res.status(400).json({ success: false, message: "Missing fields" });

    const exists = await pool.query("SELECT id FROM users WHERE email=$1", [email]);
    if (exists.rows.length) return res.status(400).json({ success: false, message: "Email already exists" });

    const hash = await bcrypt.hash(password, 10);
    const ins = await pool.query(
      "INSERT INTO users(email,name,password,role) VALUES($1,$2,$3,$4) RETURNING id,email,name,role",
      [email, name, hash, role || "driver"]
    );
    return res.status(201).json({ success: true, message: "Registered", data: ins.rows[0] });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}

export async function login(req, res) {
  try {
    const { email, password } = req.body || {};
    if (!email || !password) return res.status(400).json({ success: false, message: "Missing fields" });

    const q = await pool.query("SELECT id,email,password,role FROM users WHERE email=$1", [email]);
    if (!q.rows.length) return res.status(401).json({ success: false, message: "Invalid credentials" });

    const user = q.rows[0];
    const match = await bcrypt.compare(password, user.password);
    if (!match) return res.status(401).json({ success: false, message: "Invalid credentials" });

    const minutes = parseInt(process.env.ACCESS_TOKEN_EXPIRE_MINUTES || "60", 10);
    const token = jwt.sign({ id: user.id, email: user.email, role: user.role }, process.env.JWT_SECRET_KEY || "secret", {
      algorithm: "HS256",
      expiresIn: `${minutes}m`,
    });
    return res.status(200).json({ success: true, message: "Login successful", data: { token } });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}