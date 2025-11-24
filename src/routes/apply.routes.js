import { Router } from "express";
import { partnerApply, driverApply } from "../controllers/apply.controller.js";
import { listPartnerApplications, listDriverApplications } from "../controllers/apply.controller.js";

const r = Router();

// Frontend expects these exact endpoints when mounted at `/api/applications`
// e.g. final paths: `/api/applications/partners/apply` and `/api/applications/drivers/apply`
r.post("/partners/apply", partnerApply);
r.post("/drivers/apply", driverApply);

// Also support alternate non-plural endpoints for forward compatibility
r.post("/partner/apply", partnerApply);
r.post("/driver/apply", driverApply);

// Admin listing endpoints (mounted -> `/api/applications/partners`, `/api/applications/drivers`)
r.get("/partners", listPartnerApplications);
r.get("/drivers", listDriverApplications);

export default r;