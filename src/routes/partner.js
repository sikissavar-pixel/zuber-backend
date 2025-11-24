import { Router } from "express";
import { partnerApplyGet, partnerApplyPost } from "../controllers/partner.controller.js";

const r = Router();
r.get("/apply", partnerApplyGet);
r.post("/apply", partnerApplyPost);

export default r;