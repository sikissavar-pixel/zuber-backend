# Railway Deployment Configuration

## Environment Variables Required for Railway

### Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database
RAILWAY_DATABASE_URL=postgresql://username:password@host:port/database
POSTGRES_URL=postgresql://username:password@host:port/database
POSTGRES_PRISMA_URL=postgresql://username:password@host:port/database
PG_CONNECTION_STRING=postgresql://username:password@host:port/database

### CORS Configuration (CRITICAL for Frontend)
CORS_ORIGINS=https://zuber-37e2.vercel.app,http://localhost:3000
SOCKET_CORS_ORIGINS=https://zuber-37e2.vercel.app,http://localhost:3000

### JWT Configuration
JWT_SECRET=your-jwt-secret-key-here

### Google Maps API (Optional)
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

### Port Configuration (Railway will set this automatically)
PORT=3001

## Railway Deployment Steps

1. Connect your GitHub repository to Railway
2. Add the above environment variables in Railway dashboard
3. Railway will automatically detect the Dockerfile
4. Deploy will start automatically on git push

## Health Check Endpoint
The application exposes:
- GET /status - Simple health check
- GET /health - Detailed health check with timestamp

## Database SSL Configuration
The application automatically handles SSL for Railway PostgreSQL:
- SSL is enabled by default (DATABASE_SSL=true)
- rejectUnauthorized is set to false for Railway compatibility