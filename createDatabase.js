import { initDb } from './src/config/db.js';

async function initializeDatabase() {
  try {
    await initDb();
    console.log('Database initialized successfully');
  } catch (error) {
    console.error('Error initializing database:', error.message);
  }
}

initializeDatabase();