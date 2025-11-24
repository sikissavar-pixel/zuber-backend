import { Router } from "express";
import { authMiddleware, requireRole } from "../middleware/auth.js";
import { listReservations, createReservation, getReservation, patchReservation, deleteReservation } from "../controllers/partner.controller.js";

const r = Router();
r.use(authMiddleware, requireRole("partner"));
r.get("/reservations", listReservations);
r.post("/reservations", createReservation);
r.get("/reservations/:id", getReservation);
r.patch("/reservations/:id", patchReservation);
r.delete("/reservations/:id", deleteReservation);

export default r;