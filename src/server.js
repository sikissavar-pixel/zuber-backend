import { createServer } from "http";
import app from "./app.js";
import { initDb, ensureAdmin } from "./config/db.js";
import { initSocket } from "./sockets/index.js";

const PORT = parseInt(process.env.PORT || "3001", 10);

const httpServer = createServer(app);
const io = initSocket(httpServer);
app.set("io", io);

// Route'lar app.js içinde bağlanır

initDb()
  .then(() => ensureAdmin())
  .then(() => {
    httpServer.listen(PORT, () => {
      console.log("🚀 Zuber Backend running on PORT:", PORT);
    });
  })
  .catch(console.error);