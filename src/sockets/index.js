import { Server } from "socket.io";

export function initSocket(httpServer) {
  const allow = (process.env.CORS_ORIGINS || "http://localhost:3000")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean);

  const io = new Server(httpServer, {
    cors: { origin: allow, methods: ["GET", "POST"] },
    path: process.env.SOCKET_PATH || "/socket.io",
  });

  io.on("connection", (socket) => {
    socket.on("bid:update", (payload) => io.emit("bid:update", payload));
    socket.on("driver:position", (payload) => io.emit("driver:position", payload));
    socket.on("partner:notify", (payload) => io.emit("partner:notify", payload));
  });

  return io;
}