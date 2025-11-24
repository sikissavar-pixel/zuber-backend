export function initSockets(io) {
  io.on("connection", (socket) => {
    socket.on("admin_join", () => {
      io.emit("reservationStatus", { ping: true });
    });
    socket.on("driver_location_update", (data) => {
      io.emit("driver_location_update", data);
    });
  });
}