const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');

// Services
const { bufferService } = require('./services/bufferService');

// Routes
const collectRouter = require('./routes/collect');

const app = express();
const PORT = process.env.PORT || 8080;

// Security middleware
app.use(helmet({
  crossOriginResourcePolicy: { policy: "cross-origin" }
}));

// Compression middleware
app.use(compression());

// CORS configuration
app.use(cors({
  origin: [
    'http://localhost:3000',           // 개발환경 Frontend
    'https://witple.kro.kr'               // 운영환경 (실제 도메인으로 변경 필요)
  ],
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true
}));

// Rate limiting - 1분에 최대 100개 요청
const limiter = rateLimit({
  windowMs: 1 * 60 * 1000, // 1분
  max: 100, // 최대 100개 요청
  message: {
    error: 'Too many requests from this IP, please try again later.',
    retryAfter: '1 minute'
  },
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(limiter);

// Body parsing middleware
app.use(express.json({ 
  limit: '10mb',
  verify: (req, res, buf) => {
    try {
      JSON.parse(buf);
    } catch (e) {
      res.status(400).json({ error: 'Invalid JSON format' });
      throw new Error('Invalid JSON');
    }
  }
}));

// Request logging middleware
app.use((req, res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${req.method} ${req.path} - IP: ${req.ip}`);
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    version: require('./package.json').version
  });
});

// API routes
app.use('/collect', collectRouter);

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({ 
    error: 'Endpoint not found',
    path: req.originalUrl,
    method: req.method
  });
});

// Global error handler
app.use((error, req, res, next) => {
  console.error('Global error handler:', error);
  
  if (error.message === 'Invalid JSON') {
    return; // Already handled in body parser
  }
  
  res.status(500).json({ 
    error: 'Internal server error',
    timestamp: new Date().toISOString()
  });
});

// 5분마다 버퍼를 S3로 플러시
const FLUSH_INTERVAL = 5 * 60 * 1000; // 5분
setInterval(() => {
  bufferService.flushToS3()
    .then((result) => {
      if (result && result.count > 0) {
        console.log(`[BUFFER] Scheduled flush completed: ${result.count} actions uploaded`);
      }
    })
    .catch((error) => {
      console.error('[BUFFER] Scheduled flush failed:', error);
    });
}, FLUSH_INTERVAL);

// Graceful shutdown handling
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');
  
  // 남은 버퍼 데이터를 S3로 플러시
  try {
    const result = await bufferService.flushToS3();
    if (result && result.count > 0) {
      console.log(`[SHUTDOWN] Final flush completed: ${result.count} actions uploaded`);
    }
  } catch (error) {
    console.error('[SHUTDOWN] Final flush failed:', error);
  }
  
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully...');
  
  // 남은 버퍼 데이터를 S3로 플러시
  try {
    const result = await bufferService.flushToS3();
    if (result && result.count > 0) {
      console.log(`[SHUTDOWN] Final flush completed: ${result.count} actions uploaded`);
    }
  } catch (error) {
    console.error('[SHUTDOWN] Final flush failed:', error);
  }
  
  process.exit(0);
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Collection Server running on port ${PORT}`);
  console.log(`🏥 Health check: http://localhost:${PORT}/health`);
  console.log(`📡 Data collection: http://localhost:${PORT}/collect`);
  console.log(`⏰ Buffer flush interval: ${FLUSH_INTERVAL / 1000}s`);
  console.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
});