const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

const { connectDB } = require('./config/database');
const documentRoutes = require('./routes/documents');
const screeningRoutes = require('./routes/screening');
const healthRoutes = require('./routes/health');

const app = express();

const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: 'Too many requests. Please wait a few minutes before retrying.',
  },
});

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ limit: '2mb', extended: true }));
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');
  next();
});
app.use('/api', apiLimiter);

// Connect to MongoDB
connectDB();

// Routes
app.use('/api/documents', documentRoutes);
app.use('/api/screening', screeningRoutes);
app.use('/api/health', healthRoutes);

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Error:', err);
  const clientError = err.code === 'LIMIT_FILE_SIZE' || /invalid file type/i.test(err.message || '');
  res.status(clientError ? 400 : (err.status || 500)).json({
    error: clientError ? 'Invalid upload. Use a JPEG, PNG, or PDF no larger than 10 MB.' : 'Internal server error',
  });
});

module.exports = app;
