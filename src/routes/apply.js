import { Router } from "express";
import { driverApplyGet, driverApplyPost } from "../controllers/driver.controller.js";
import { partnerApplyGet, partnerApplyPost } from "../controllers/partner.controller.js";

const r = Router();

r.get("/driver/apply", driverApplyGet);
r.post("/driver/apply", driverApplyPost);

r.get("/partner/apply", partnerApplyGet);
r.post("/partner/apply", partnerApplyPost);

export default r;