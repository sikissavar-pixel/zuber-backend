import { Router } from "express";
import { register, login } from "../controllers/auth.controller.js";

const r = Router();
// Frontend expects /api/users/login and /api/users/register
// Since app.js mounts this at /api, we use /users prefix here
r.post("/users/login", login);
r.post("/users/register", register);

export default r;