import { Router } from "express";
import { authMiddleware, requireRole } from "../middleware/auth.js";
import { listOpenReservations, placeBid, listMyBids } from "../controllers/driver.controller.js";

const r = Router();
r.use(authMiddleware, requireRole("driver"));
r.get("/open-reservations", listOpenReservations);
r.post("/bids/:reservationId", placeBid);
r.get("/bids/my", listMyBids);

export default r;