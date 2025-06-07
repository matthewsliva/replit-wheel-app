import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import JSONResponse
import alpaca_trade_api as tradeapi
from models import WebhookSignal, TradingSignal, Base, create_db_engine, get_db_session
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Wheel Strategy Bot",
    description="Options trading webhook processor with Alpaca integration and database logging",
    version="1.0.0"
)

# Initialize database
try:
    engine = create_db_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {str(e)}")

# Initialize Alpaca API client
def get_alpaca_client():
    """Initialize and return Alpaca trading client"""
    try:
        api_key = os.getenv("APCA_API_KEY_ID")
        secret_key = os.getenv("APCA_API_SECRET_KEY")
        
        if not api_key or not secret_key:
            logger.error("Alpaca API credentials not found in environment variables")
            return None
            
        # Use paper trading environment
        api = tradeapi.REST(
            api_key,
            secret_key,
            base_url='https://paper-api.alpaca.markets',  # Paper trading URL
            api_version='v2'
        )
        
        # Test connection
        account = api.get_account()
        logger.info(f"Connected to Alpaca paper trading - Account Status: {account.status}")
        return api
        
    except Exception as e:
        logger.error(f"Failed to initialize Alpaca client: {str(e)}")
        return None

# Global Alpaca client
alpaca_client = get_alpaca_client()

def get_db():
    """Database dependency"""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    """Health check endpoint"""
    alpaca_status = "Connected" if alpaca_client else "Disconnected"
    return {
        "message": "Wheel Strategy Bot is running",
        "status": "active",
        "alpaca_connection": alpaca_status,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/webhook")
async def process_webhook(signal: WebhookSignal, db: Session = Depends(get_db)):
    data = await request.json()
    action = data.get("action")
    symbol = data.get("symbol")
    strike = float(data.get("strike"))
    expiry = data.get("expiry")  # Format: "2024-07-19"
    premium = float(data.get("premium", 1.0))

    if not all([action, symbol, strike, expiry]):
        return {"error": "Missing parameters."}

    # Build OCC-compliant option symbol
    expiry_code = expiry.replace("-", "")[2:]  # "2024-07-19" → "240719"
    strike_formatted = f"{int(strike * 1000):08d}"
    right = "P" if action == "sell_put" else "C"
    occ_symbol = f"{symbol}{expiry_code}{right}{strike_formatted}"

    print(f"[INFO] Action: {action} | OCC Symbol: {occ_symbol}")

    try:
        # Submit Alpaca order
        order = api.submit_order(
            symbol=occ_symbol,
            qty=1,
            side="sell",
            type="limit",
            limit_price=premium,
            time_in_force="gtc",
            order_class="simple",
            order_type="option"
        )
        print(f"Order submitted: {order}")
        return {"status": "success", "order": order._raw}
    except Exception as e:
        print(f"[ERROR] {e}")
        return {"status": "error", "message": str(e)}
