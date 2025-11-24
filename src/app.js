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

app.use("/", authRoutes);
app.use("/", applyRoutes);
app.use("/bids", bidsRouter);
app.use("/admin", adminRouter);

export default app;