import { pool } from "../config/db.js";

export async function partnerApply(req, res) {
  try {
    const { name, phone, carModel, description } = req.body || {};
    if (!name) return res.status(400).json({ success: false, message: "Missing name" });
    const ins = await pool.query(
      "INSERT INTO partner_applications(name, phone, car_model, description) VALUES($1,$2,$3,$4) RETURNING id,name,phone,car_model,description,status,created_at",
      [name, phone || null, carModel || null, description || null]
    );
    return res.status(201).json({ success: true, message: "Application submitted", data: ins.rows[0] });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}

export async function driverApply(req, res) {
  try {
    const { full_name, email, phone, license_no, vehicle_plate, city, description } = req.body || {};
    if (!full_name) return res.status(400).json({ success: false, message: "Missing full_name" });
    const ins = await pool.query(
      "INSERT INTO driver_applications(name, phone, license_type, experience, description) VALUES($1,$2,$3,$4,$5) RETURNING id,name,phone,license_type,experience,description,status,created_at",
      [full_name, phone || null, license_no || null, vehicle_plate || null, description || null]
    );
    return res.status(201).json({ success: true, message: "Application submitted", data: ins.rows[0] });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}

// Partner başvurularını listele
export async function listPartnerApplications(req, res) {
  const result = await pool.query("SELECT * FROM partner_applications ORDER BY created_at DESC");
  return res.json(result.rows);
}

// Driver başvurularını listele
export async function listDriverApplications(req, res) {
  const result = await pool.query("SELECT * FROM driver_applications ORDER BY created_at DESC");
  return res.json(result.rows);
}