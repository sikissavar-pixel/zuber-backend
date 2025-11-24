import { Router } from "express";
import { adminStats } from "../controllers/admin.controller.js";

const r = Router();
r.get("/stats", adminStats);

export default r;