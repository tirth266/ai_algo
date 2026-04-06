# Algorithmic Trading Platform

A comprehensive local algorithmic trading platform with Zerodha Kite Connect and Angel One SmartAPI integration, built with Flask (Backend) and React (Frontend). Features institutional-grade backtesting, parameter optimization, walk-forward analysis, and production-ready web trading capabilities.

## 🚀 Features

- **Strategy Engine**: Multiple trading strategies with automated execution using 6-in-1 Combined Power Strategy
- **Live Trading**: Real-time market monitoring and order execution with risk management
- **Backtesting**: Institutional-level historical data testing with performance analytics
- **Parameter Optimization**: Grid search with heatmap visualization and overfitting detection
- **Walk-Forward Analysis**: Scientific validation on unseen data to eliminate overfitting bias
- **Multi-Broker Support**: Zerodha Kite Connect and Angel One SmartAPI integration
- **Web UI Control**: Modern React interface for complete platform control
- **Database Persistence**: PostgreSQL storage for trades, positions, and logs
- **Risk Management**: Built-in risk controls, position limits, and kill-switch functionality
- **Real-time Updates**: Live system monitoring with WebSocket streaming
- **Docker Support**: Containerized deployment with docker-compose orchestration

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis for session management and real-time data
- **Broker APIs**: Zerodha Kite Connect, Angel One SmartAPI
- **Indicators**: TA-Lib, pandas-ta for technical analysis
- **Authentication**: JWT tokens with secure session management

### Frontend
- **Framework**: React 18 + Vite with TypeScript
- **UI Library**: Material-UI + Tailwind CSS
- **Charts**: Recharts for data visualization
- **State Management**: React Hooks with Context API
- **HTTP Client**: Axios for API communication
- **Real-time**: WebSocket integration for live updates

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Process Manager**: Gunicorn for production deployment
- **Environment**: Python 3.9+, Node.js 18+
- **Web Server**: Nginx reverse proxy with SSL support

## ⚡ Quick Start

### Prerequisites
- Python 3.9 or higher
- Node.js 18 or higher
- PostgreSQL 13 or higher
- Redis 6 or higher
- Docker & Docker Compose (recommended)

### 1. Clone & Install

```bash
cd algo-trading-platform

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install
```

### 2. Configure Environment

Create `.env` file in project root:

```env
# Zerodha Credentials
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_USER_ID=your_user_id

# Angel One Credentials (Alternative)
ANGEL_ONE_API_KEY=your_api_key
ANGEL_ONE_SECRET_KEY=your_secret_key
ANGEL_ONE_CLIENT_ID=your_client_id
ANGEL_ONE_TOTP_SEED=your_totp_seed

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/trading_platform

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Flask
SECRET_KEY=your-secret-key
FLASK_ENV=development
FLASK_PORT=5000

# Frontend
FRONTEND_URL=http://localhost:3000
```

### 3. Start Services

**Option A: Docker (Recommended)**
```bash
docker-compose up --build
```

**Option B: Manual Setup**
```bash
# Terminal 1 - Backend:
cd backend
python app.py

# Terminal 2 - Frontend:
cd frontend
npm run dev
```

Backend runs on: `http://localhost:5000`
Frontend runs on: `http://localhost:3000`

### 4. Open Application

Navigate to: `http://localhost:3000`

## 🏗️ System Architecture

### The "6-in-1" Combined Power Strategy
The platform uses a voting mechanism across 6 distinct sub-strategies:
- **Trend Following (2x)**: Supertrend & LuxAlgo Trendlines
- **Momentum (2x)**: RSI Crossover & VWAP Deviation  
- **Mean Reversion (2x)**: Bollinger Band Squeeze & Scalping Oscillator

**Signal Execution Logic:**
- **Paper Trading**: Requires `min_votes = 1` for diagnostic visibility
- **Production Mode**: Requires `min_votes = 3` (minimum 3 strategies must agree)

## 🔐 Authentication

### Zerodha Setup
You have two options for the Redirect URL in Zerodha Kite Console:

**Option A (Simpler):** `http://localhost:5000`
**Option B (Original):** `http://localhost:5000/api/broker/callback`

Both work perfectly! The system handles OAuth flow automatically with daily token renewal.

### Angel One Setup
1. Get your API credentials from Angel One developer console
2. Configure TOTP seed for automated authentication
3. Use the migration guide for seamless broker switching

## 📊 Key Features Deep Dive

### Parameter Optimization Engine
- **Grid Search**: Test hundreds of parameter combinations in parallel
- **Heatmap Visualization**: Interactive 2D parameter performance matrix
- **Robust Zone Detection**: Identify stable parameter ranges (not isolated peaks)
- **Overfitting Analysis**: Quantify curve-fitting risk with statistical metrics
- **Export Results**: CSV/JSON output for further analysis

### Walk-Forward Analysis
- **Scientific Validation**: Test strategy on truly unseen data
- **Rolling Windows**: Optimize on IS data, test on OOS data
- **Walk-Forward Efficiency (WFE)**: Measure strategy adaptability
- **Parameter Stability**: Track how optimal parameters drift over time
- **Trading Recommendations**: Color-coded go/no-go decisions

**WFE Interpretation:**
- **WFE > 0.8**: Excellent - Strategy adapts perfectly
- **WFE 0.5-0.8**: Good - Professional-grade robustness  
- **WFE < 0.5**: Poor - Strategy is overfit, do not trade

### Backtesting Engine
- **Institutional-Level**: Candle-by-candle execution with realistic slippage
- **Performance Metrics**: 15+ indicators including Sharpe ratio, max drawdown
- **Trade Simulation**: Slippage (0.05%), brokerage (₹20/trade), realistic fills
- **Equity Curve Tracking**: Visual performance analysis
- **Results Export**: JSON/CSV output with detailed metrics

### Risk Management
- **Hard-Coded Stop Loss**: 2% (auto-triggered upon fill)
- **Daily Loss Limit**: ₹2,000 (based on ₹100k capital)
- **Position Limit**: Maximum 5 active symbols
- **First-Trade Protocol**: First 3 trades limited to 1 lot for verification
- **Kill-Switch**: Emergency stop accessible via dashboard UI

## 🔗 API Endpoints

### Authentication
- `GET /api/broker/login` - Initiate broker login
- `GET /api/broker/callback` - OAuth callback handler
- `GET /api/broker/status` - Check connection status
- `POST /api/broker/logout` - Disconnect broker

### Trading Control
- `POST /api/trading/start` - Start trading engine
- `POST /api/trading/stop` - Stop trading engine
- `GET /api/trading/status` - Get engine status

### Orders & Positions
- `GET /api/orders` - Fetch all orders
- `POST /api/order/place` - Place new order
- `GET /api/positions` - Fetch open positions

### Backtesting & Optimization
- `POST /api/backtest/run` - Run backtest
- `POST /api/backtest/optimize` - Parameter optimization
- `POST /api/backtest/walk-forward` - Walk-forward analysis

### Market Data
- `GET /api/ltp/<symbol>` - Last traded price
- `GET /api/historical/<symbol>` - Historical candles
- `GET /api/portfolio` - Portfolio summary

## 📁 Project Structure

```
algo-trading-platform/
├── backend/                    # Flask backend
│   ├── api/                   # REST API routes
│   ├── engine/                # Trading engine core
│   ├── strategies/            # Trading strategies
│   ├── indicators/            # Technical indicators
│   ├── database/              # DB connection & models
│   ├── trading/               # Broker integration
│   ├── backtest/              # Backtesting engine
│   ├── config/                # Configuration files
│   └── app.py                 # Main Flask application
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Application pages
│   │   ├── services/          # API service layer
│   │   └── types/             # TypeScript types
│   └── package.json
├── webapp/                    # Alternative web platform
│   ├── app.py                 # Flask application
│   ├── auth/                  # Authentication
│   ├── api/                   # Trading APIs
│   ├── engine/                # Engine controller
│   ├── dashboard/             # Dashboard service
│   └── frontend/              # React frontend
├── docker-compose.yml         # Container orchestration
├── .env                       # Environment variables
└── README.md                  # This file
```

## ⚙️ Configuration

### Trading Settings
Configure in `.env`:

```env
TRADING_MODE=paper              # paper or live
MAX_RISK_PER_TRADE=0.02         # 2% of capital
MAX_DAILY_LOSS=0.05            # 5% daily loss limit
MAX_OPEN_POSITIONS=5           # Maximum concurrent positions
CAPITAL_PER_TRADE=50000        # Capital per trade
STOP_LOSS_PERCENTAGE=2.0       # 2% stop loss
TARGET_PERCENTAGE=4.0          # 4% target profit
```

### Broker Settings

```env
ZERODHA_PRODUCT_TYPE=MIS         # Default product type
ZERODHA_EXCHANGE=NSE            # Default exchange
MARKET_DATA_TIMEFRAME=5m        # Candle timeframe
```

### Production Deployment Settings

```env
FLASK_ENV=production
DEBUG=false
LOG_LEVEL=INFO
REDIS_MAX_CONNECTIONS=100
DATABASE_POOL_SIZE=20
```

## 🚀 Production Deployment

### Docker Deployment (Recommended)
```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Scale web workers
docker-compose -f docker-compose.prod.yml up -d --scale web=4
```

### Manual VPS Deployment
1. **Provision Server**: Ubuntu 20.04 LTS, 4GB RAM, 2 CPU cores
2. **Install Dependencies**: PostgreSQL, Redis, Nginx, Python 3.9+
3. **Setup SSL**: Let's Encrypt for HTTPS
4. **Configure Nginx**: Reverse proxy with WebSocket support
5. **Deploy with Gunicorn**: Multi-worker production server

### Cloud Platform Deployment
- **Heroku**: Git-based deployment with add-ons
- **Railway**: Automatic scaling and monitoring
- **AWS EC2**: Full control with load balancing
- **DigitalOcean**: Simple VPS with managed databases

## 🔒 Security Notes

- Never commit `.env` file to version control
- Keep API credentials secure and rotate periodically
- Use HTTPS in production with proper SSL certificates
- Session tokens stored encrypted in Redis
- CORS configured for specific origins only
- Rate limiting on all API endpoints
- Input validation to prevent injection attacks

## 🐛 Troubleshooting

### Backend Won't Start
- Check PostgreSQL is running and accessible
- Verify database URL in `.env` configuration
- Ensure port 5000 is available (or change FLASK_PORT)
- Check Redis connection and authentication

### Frontend Won't Load
- Verify Node.js version (18+ required)
- Delete `node_modules` and reinstall dependencies
- Ensure backend is running on correct port
- Check CORS configuration matches frontend URL

### Broker Connection Fails
- Verify API credentials in `.env` file
- Check redirect URL configuration in broker console
- Ensure ngrok is running for HTTPS callbacks (development)
- Test broker API connectivity separately

### Database Issues
- Verify PostgreSQL service is running
- Check database credentials and permissions
- Ensure database `trading_platform` exists
- Run database migration if schema changed

## 📊 Monitoring & Analytics

### Real-time Metrics
- **API Response Time**: < 100ms target
- **WebSocket Latency**: < 50ms for tick updates
- **Database Query Time**: < 50ms for complex queries
- **System Health**: Memory, CPU, disk usage monitoring

### Performance Optimization
- Redis caching for frequently accessed data
- Database indexing on query columns
- Connection pooling for database connections
- Async WebSocket communication
- CDN for static assets in production

## 🎯 Success Criteria

### Development Complete
✅ All API endpoints functional and tested
✅ WebSocket real-time updates working
✅ Database migrations successful
✅ Authentication flow with brokers working
✅ Docker containers running without errors

### Frontend Ready
✅ React app connected to backend API
✅ Dashboard displaying live market data
✅ Manual order placement working
✅ Strategy start/stop controls functional
✅ Real-time portfolio updates

### Integration Verified
✅ Broker login and authentication working
✅ Portfolio data fetching from broker
✅ Order placement via API successful
✅ Real-time price updates flowing
✅ Engine control commands responsive

### Production Ready
✅ HTTPS configured with SSL certificates
✅ Environment variables properly secured
✅ Database backup strategy implemented
✅ Monitoring and logging active
✅ Error tracking and alerting setup

## 📈 Advanced Features

### Multi-Strategy Portfolio
- Combine 3-5 uncorrelated strategies
- Automated portfolio rebalancing
- Risk-adjusted position sizing
- Performance attribution analysis

### Machine Learning Integration
- Feature engineering for market data
- Model training and validation pipelines
- Real-time prediction serving
- Model performance monitoring

### Institutional Features
- Multiple user account management
- Role-based access control
- Audit trail and compliance reporting
- Advanced risk analytics
- Custom strategy development framework

## 📚 Additional Documentation

### Strategy Development
- Custom strategy creation guide
- Technical indicator implementation
- Backtesting workflow documentation
- Parameter optimization best practices

### API Reference
- Complete endpoint documentation
- WebSocket event specifications
- Error code reference
- Rate limiting details

### Deployment Guides
- Docker deployment strategies
- Cloud platform setup instructions
- SSL certificate configuration
- Monitoring setup procedures

---

**Version**: 2.0.0  
**Last Updated**: April 5, 2026  
**Status**: Production Ready ✅  
**Platform Completion**: 98% - Ready for live paper trading validation

**🎉 Congratulations!** You now have a complete institutional-grade algorithmic trading platform with scientific validation, professional risk management, and production-ready deployment capabilities.

**Next Steps**: Start with paper trading to validate your strategies, then gradually move to live trading with proper risk controls. Always remember: *Past performance does not guarantee future results.* Trade responsibly! 📈