import { Router } from "express";
import { register, login } from "../controllers/auth.controller.js";

const r = Router();
r.post("/login", login);
r.post("/register", register);
r.post("/api/users/login", login);
r.post("/api/users/register", register);

export default r;