import { Router } from "express";
import { createBid, getBid } from "../controllers/bids.controller.js";

const r = Router();
r.post("/", createBid);
r.get("/:id", getBid);

export default r;