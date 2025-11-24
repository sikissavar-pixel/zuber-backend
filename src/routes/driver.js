import { Router } from "express";
import { driverApplyGet, driverApplyPost } from "../controllers/driver.controller.js";

const r = Router();
r.get("/apply", driverApplyGet);
r.post("/apply", driverApplyPost);

export default r;