# 📈 NiveshAI — AI-Powered Market Intelligence

<div align="center">

![NiveshAI](https://img.shields.io/badge/NiveshAI-Live-22d3a0?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyTDIgN2wxMCA1IDEwLTVMMTIgMnpNMiAxN2wxMCA1IDEwLTV2LTVsLTEwIDUtMTAtNXY1eiIvPjwvc3ZnPg==)
[![Python](https://img.shields.io/badge/Python-3.11-4f9eff?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-22d3a0?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Railway](https://img.shields.io/badge/Deployed-Railway-a78bfa?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![License](https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge)](LICENSE)

**Smart Market Analysis for Indian & Global Stocks — No Jargon. No Confusion.**

[🌐 Live Demo](https://niveshai-production-3635.up.railway.app) · [📊 Dashboard](https://niveshai-production-3635.up.railway.app/dashboard) · [🔐 Sign Up](https://niveshai-production-3635.up.railway.app/auth?mode=signup)

</div>

---

## 🌟 What is NiveshAI?

NiveshAI is a full-stack AI-powered market analysis platform built for everyday investors — not just finance professionals. It turns complex stock data (RSI, MACD, Bollinger Bands, momentum indicators) into plain-English insights so anyone can understand what the market is doing and why.

**The core problem it solves:** Every free trading tool gives you data. None of them tell you what the data *means*. NiveshAI bridges that gap.

### Key Capabilities

| Feature | Description |
|---|---|
| 🔍 **Deep Stock Analysis** | 12 technical indicators computed and explained in plain English |
| ⚡ **AI Momentum Score** | Single 0–100 composite score across Trend + RSI + MACD + Rate-of-Change |
| 🔮 **Price Predictions** | ML-powered 1-week and 1-month targets with bull/base/bear scenarios |
| 📰 **Daily Narrative** | "What happened today" — auto-generated plain-English market summary |
| 🕐 **Live Intraday** | Real-time 15-minute candlestick chart with VWAP for today's session |
| 💼 **Portfolio Tracker** | Add holdings manually, see live P&L + regime for every position |
| 🔔 **Smart Alerts** | Trigger on price levels, RSI crossings, or regime changes |
| 🇮🇳 **Full NSE Coverage** | All 2,000+ NSE-listed Indian stocks + BSE + global markets |

---

## 🖥️ Screenshots

| Landing Page | Dashboard | Auth |
|---|---|---|
| Three.js 3D currency sphere | Glassmorphism dark UI | Split-panel auth |

---

## 🏗️ Architecture

```
NiveshAI/
├── web/                          # FastAPI web application
│   ├── app.py                    # Application entry point (routes + static)
│   ├── models.py                 # Pydantic request/response models
│   ├── auth/                     # Authentication system
│   │   ├── database.py           # SQLAlchemy ORM (User, Holding, Alert)
│   │   ├── security.py           # bcrypt + JWT token management
│   │   └── email_service.py      # OTP email via SMTP / console fallback
│   ├── routes/                   # API route modules (one file per domain)
│   │   ├── analyze.py            # /api/analyze, /api/intraday
│   │   ├── portfolio.py          # /api/portfolio CRUD
│   │   ├── alerts.py             # /api/alerts CRUD + check
│   │   ├── narrative.py          # /api/narrative, /api/market-summary
│   │   ├── search.py             # /api/search autocomplete
│   │   └── auth.py               # /api/auth/* (signup, signin, verify)
│   ├── api/                      # Core analysis engine
│   │   ├── analysis.py           # Master analysis pipeline
│   │   ├── realtime.py           # Live quotes + intraday data
│   │   ├── prediction.py         # ML price prediction (GBM)
│   │   ├── narrative.py          # Template + Claude AI summaries
│   │   ├── portfolio.py          # Portfolio enrichment
│   │   ├── alerts.py             # Alert checking engine
│   │   └── india_stocks.py       # NSE symbol database + resolver
│   └── static/                   # Frontend (HTML/CSS/JS)
│       ├── landing.html          # Landing page (Three.js sphere)
│       ├── auth.html             # Sign In / Sign Up (Three.js orbs)
│       ├── index.html            # Main dashboard (4 tabs)
│       ├── css/
│       │   ├── style.css         # Dashboard design system
│       │   ├── landing.css       # Landing page styles
│       │   └── auth.css          # Auth page styles
│       └── js/
│           ├── app.js            # Dashboard logic + Plotly charts
│           └── auth.js           # Auth flow (signup/verify/login)
├── agents/                       # RL trading agents (research component)
│   └── policy_network.py         # Actor-Critic network (PPO)
├── envs/                         # Multi-agent trading environment
│   └── trading_env.py            # PettingZoo AEC environment
├── training/                     # PPO training pipeline
│   └── ppo_trainer.py            # Independent learners MARL
├── evaluation/                   # Backtesting + strategy analysis
│   └── backtest.py               # Sharpe, drawdown, strategy classification
├── visualization/                # Offline chart generation
│   └── dashboard.py              # Plotly HTML dashboards
├── data/                         # Downloaded market data (gitignored)
├── results/                      # Training outputs (gitignored)
├── requirements.txt              # Python dependencies
├── Procfile                      # Railway/Heroku start command
├── railway.toml                  # Railway deployment config
└── runtime.txt                   # Python version specification
```

---

## 🛠️ Tech Stack

### Backend
| Layer | Technology | Why |
|---|---|---|
| **Web Framework** | FastAPI 0.121 | Async, auto-docs, Pydantic validation |
| **Server** | Uvicorn | ASGI, production-grade |
| **Database** | SQLite + SQLAlchemy | Zero-config, file-based, portable |
| **Auth** | JWT (python-jose) + bcrypt | Stateless tokens, secure password hashing |
| **Market Data** | yfinance + yahooquery | Free, reliable OHLCV data |
| **Indicators** | ta (Technical Analysis) | RSI, MACD, Bollinger Bands in one line |
| **ML Predictions** | scikit-learn GBM | Fast training, no heavy dependencies |
| **Indian Stocks** | NSE CSV + symbol resolver | All 2,000+ NSE stocks with restructuring handling |
| **AI Narratives** | Template engine + Claude API (optional) | Works without API key, upgrades with one |

### Frontend
| Layer | Technology | Why |
|---|---|---|
| **Charts** | Plotly.js 2.27 | Interactive, zero build step, financial-grade |
| **3D Graphics** | Three.js r128 | Landing page sphere + auth page orbs |
| **Styling** | Vanilla CSS (glassmorphism) | No framework overhead, full control |
| **Auth flow** | Vanilla JS + Fetch API | No dependencies, fast |

### RL Research Component
| Layer | Technology | Why |
|---|---|---|
| **Framework** | Custom PPO (PyTorch) | Full control over the training loop |
| **Environment** | PettingZoo AEC | Standard MARL API |
| **Hardware** | Apple MPS (M1/M2/M3) | Native Metal GPU acceleration |

### Infrastructure
| Component | Technology |
|---|---|
| **Deployment** | Railway (auto-deploy from GitHub) |
| **Persistent Storage** | Railway Volume (SQLite on /data) |
| **SSL** | Automatic via Railway |
| **CI/CD** | Push to `main` → auto-deploy |

---

## 🚀 Running Locally

### Prerequisites
- Python 3.11+
- pip

### 1. Clone the repository
```bash
git clone https://github.com/Akashkr28/Nivesh_AI.git
cd Nivesh_AI
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the server
```bash
python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8000
```

### 4. Open in browser
```
http://localhost:8000
```

That's it. No database setup, no environment variables required for local development.

### Optional: Enable AI-powered narratives
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```
Without this, the narrative feature uses a smart template engine that works without any API key.

---

## 🌐 API Reference

All endpoints are documented at `/docs` (Swagger UI) when running.

### Core Endpoints

```
POST /api/analyze              Full technical analysis for any ticker
GET  /api/search?q=reliance    Search stocks by name or symbol
GET  /api/intraday?ticker=...  Today's 15-min OHLCV + VWAP
GET  /api/market-status        Current session status (NSE/NYSE)
POST /api/narrative            Plain-English "what happened today"
GET  /api/market-summary       Nifty + Sensex + S&P 500 overview
```

### Auth Endpoints

```
POST /api/auth/signup          Create account (sends OTP)
POST /api/auth/verify          Verify email with 6-digit OTP
POST /api/auth/signin          Login → returns JWT token
GET  /api/auth/me              Get current user profile
PUT  /api/auth/profile         Update name / risk profile
PUT  /api/auth/change-password Change password
DELETE /api/auth/account       Delete account (requires password)
```

### Portfolio Endpoints

```
GET    /api/portfolio           All holdings with live P&L + momentum
POST   /api/portfolio/add       Add or update a holding
DELETE /api/portfolio/{ticker}  Remove a holding
DELETE /api/portfolio           Reset entire portfolio
```

### Alerts Endpoints

```
GET    /api/alerts              List all alerts + trigger history
POST   /api/alerts/add          Create alert (price/RSI/regime/momentum)
DELETE /api/alerts/{id}         Delete an alert
GET    /api/alerts/check        Check all alerts against live data
```

### Example: Analyze a stock
```bash
curl -X POST https://niveshai-production-3635.up.railway.app/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "RELIANCE.NS", "period_years": 1}'
```

Response includes: regime, metrics, momentum_score, predictions, intraday, chart_data, strategy.

---

## 🔬 The RL Research Component

Beyond the web app, this project contains a complete **Multi-Agent Reinforcement Learning** trading system — the research foundation that motivated building NiveshAI.

### What it does
Trains 3 competing agents in a shared stock market environment. Each agent independently learns to trade using PPO (Proximal Policy Optimization). The key finding: **identical architectures trained in competition diverge into qualitatively different strategies** — one becomes a momentum trader, others become mean-reversion traders. This emergent specialization mirrors real market dynamics.

### Architecture
```
3 PPO Agents (independent learners)
    ↓
PettingZoo AEC Environment
    ↓
State: [12 market features] + [own position] + [other agents' positions]
Action: HOLD / BUY / SELL (discrete)
Reward: % change in portfolio value
```

### Key components
- **`envs/trading_env.py`** — Multi-agent PettingZoo environment with transaction costs
- **`agents/policy_network.py`** — Actor-Critic with LayerNorm and orthogonal init
- **`training/ppo_trainer.py`** — Full PPO with GAE, clipped surrogate, entropy bonus
- **`evaluation/backtest.py`** — Sharpe, Sortino, drawdown + strategy classification

### Running the RL system
```bash
# Download data and train agents
python3 run_all.py

# Quick demo (50k steps)
python3 run_all.py --quick

# Just regenerate charts from saved results
python3 run_all.py --viz-only
```

Results saved to `results/charts/dashboard.html` — open in any browser.

---

## 🇮🇳 Indian Stock Market Support

NiveshAI has the most comprehensive Indian market coverage of any free tool:

- **All 2,000+ NSE-listed stocks** via auto-downloaded NSE CSV
- **Handles restructured companies** automatically (e.g. Tata Motors → TMCV.NS, Zomato → ETERNAL.NS)
- **Full NSE symbol resolver** with 120+ manual overrides for renamed/split companies
- **Prices in ₹** for Indian stocks, **$** for global
- **NSE session detection** — knows if NSE is open, pre-market, or after-hours
- **Indices** — Nifty 50 (^NSEI), Sensex (^BSESN), Bank Nifty (^NSEBANK)

### Supported ticker formats
```
RELIANCE.NS     # NSE
RELIANCE.BO     # BSE
^NSEI           # Nifty 50 index
^BSESN          # Sensex index
TATAMOTORS      # Auto-resolves to TMCV.NS
ZOMATO          # Auto-resolves to ETERNAL.NS (rebranded 2025)
MAHINDRA        # Auto-resolves to M&M.NS
```

---

## 🔐 Authentication System

- **Sign up** with name, email, password
- **Email OTP verification** (6-digit code)
  - With SMTP configured: sends real email
  - Without SMTP (local dev): prints OTP to terminal
- **JWT tokens** (7-day expiry)
- **Risk profile** — Conservative / Moderate / Aggressive
- **Account settings** — update profile, change password
- **Account deletion** — two-step confirmation with password verification

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NIVESHAI_SECRET` | Production | JWT signing secret (generate with `secrets.token_hex(32)`) |
| `DATABASE_URL` | Production | SQLite path e.g. `sqlite:////data/niveshai.db` |
| `SMTP_EMAIL` | Optional | Gmail address for sending OTP emails |
| `SMTP_PASSWORD` | Optional | Gmail App Password |
| `ANTHROPIC_API_KEY` | Optional | Enables Claude AI narratives (falls back to template) |

---

## 📦 Deployment

### Deploy to Railway (recommended)

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add Volume → Mount path: `/data`
4. Add Variables: `DATABASE_URL`, `NIVESHAI_SECRET`
5. Deploy → get your live URL

### Deploy to Render (free tier)

```yaml
# render.yaml
services:
  - type: web
    name: niveshai
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn web.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: NIVESHAI_SECRET
        generateValue: true
```

### Deploy with Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📊 Performance Notes

- **Analysis time:** ~8–12 seconds per ticker (fetches live data + runs ML model)
- **Intraday data:** 15-minute intervals, fetched fresh each time
- **Database:** SQLite handles thousands of users on Railway's free tier
- **Memory:** ~150MB baseline, no GPU required for the web app
- **M1/M2/M3 Mac:** Full MPS (Metal) GPU acceleration for RL training

---

## ⚠️ Disclaimer

NiveshAI is built for **educational purposes only**. It does not constitute financial advice. Price predictions are statistical projections based on historical patterns and may not reflect future performance. The AI momentum scores and regime classifications are technical analysis tools — not buy/sell recommendations.

Always do your own research. Consult a SEBI-registered financial advisor before making investment decisions. Past performance does not guarantee future results.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [yfinance](https://github.com/ranaroussi/yfinance) — Market data
- [PettingZoo](https://pettingzoo.farama.org/) — MARL environment API
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [Plotly](https://plotly.com/javascript/) — Interactive charts
- [Three.js](https://threejs.org/) — 3D graphics
- [Railway](https://railway.app/) — Deployment platform
- [NSE India](https://www.nseindia.com/) — Indian market data

---

<div align="center">

Built with ❤️ for Indian investors

**[🚀 Try NiveshAI Live](https://niveshai-production-3635.up.railway.app)**

</div>
