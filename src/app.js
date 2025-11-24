import express from "express";
import dotenv from "dotenv";
import cors from "cors";
import { corsOptions } from "./config/cors.js";
import authRoutes from "./routes/auth.routes.js";
import applyRoutes from "./routes/apply.routes.js";
import bidsRouter from "./routes/bids.js";
import adminRouter from "./routes/admin.js";

dotenv.config();

const app = express();
app.use(cors(corsOptions));
app.options("*", cors(corsOptions));
app.use(express.json());

app.get("/", (req, res) => res.send("Zuber Backend OK"));
app.get("/health", (req, res) => res.json({ status: "ok", time: new Date().toISOString() }));
app.get("/status", (req, res) => res.json({ status: "ok" }));

// Mount routes with /api prefix to match frontend expectations
app.use("/api", authRoutes);
app.use("/api", applyRoutes);
app.use("/api/bids", bidsRouter);
app.use("/api/admin", adminRouter);

export default app;