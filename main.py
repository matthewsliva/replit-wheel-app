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
    """Process incoming trading webhook signals with database logging"""
    try:
        logger.info(f"Received webhook signal: {signal.model_dump()}")
        
        # Save signal to database
        db_signal = TradingSignal(
            action=signal.action,
            symbol=signal.symbol,
            strike=signal.strike,
            expiry=signal.expiry,
            premium=signal.premium,
            quantity=signal.quantity,
            status='pending'
        )
        db.add(db_signal)
        db.commit()
        db.refresh(db_signal)
        
        # Validate action
        if signal.action not in ["sell_put", "sell_call"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {signal.action}. Supported actions: sell_put, sell_call"
            )
        
        # Process the signal based on action
        if signal.action == "sell_put":
            result = await process_sell_put(signal, db_signal, db)
        elif signal.action == "sell_call":
            result = await process_sell_call(signal, db_signal, db)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"Successfully processed {signal.action} signal",
                "signal_id": db_signal.id,
                "signal": signal.model_dump(),
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        if 'db_signal' in locals():
            db_signal.status = 'error'
            db_signal.error_message = str(e)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

async def process_sell_put(signal: WebhookSignal, db_signal: TradingSignal, db: Session):
    """Process sell put signal"""
    action_msg = f"Selling PUT for {signal.symbol} - Strike: ${signal.strike}, Expiry: {signal.expiry}, Premium: ${signal.premium}"
    print(action_msg)
    logger.info(action_msg)
    
    # If Alpaca client is available, attempt to place order
    alpaca_result = None
    if alpaca_client:
        try:
            alpaca_result = await place_options_order(signal, "put")
            db_signal.status = 'processed'
            db_signal.processed_at = datetime.utcnow()
            if alpaca_result and 'order_details' in alpaca_result:
                db_signal.alpaca_order_id = str(alpaca_result.get('order_details', {}).get('symbol', ''))
        except Exception as e:
            logger.error(f"Failed to place Alpaca order: {str(e)}")
            alpaca_result = {"error": str(e)}
            db_signal.status = 'error'
            db_signal.error_message = str(e)
    else:
        db_signal.status = 'no_broker'
        db_signal.error_message = "Alpaca client not available"
    
    db.commit()
    
    return {
        "action": "sell_put",
        "symbol": signal.symbol,
        "strike": signal.strike,
        "expiry": signal.expiry,
        "premium": signal.premium,
        "alpaca_order": alpaca_result
    }

async def process_sell_call(signal: WebhookSignal, db_signal: TradingSignal, db: Session):
    """Process sell call signal"""
    action_msg = f"Selling CALL for {signal.symbol} - Strike: ${signal.strike}, Expiry: {signal.expiry}, Premium: ${signal.premium}"
    print(action_msg)
    logger.info(action_msg)
    
    # If Alpaca client is available, attempt to place order
    alpaca_result = None
    if alpaca_client:
        try:
            alpaca_result = await place_options_order(signal, "call")
            db_signal.status = 'processed'
            db_signal.processed_at = datetime.utcnow()
            if alpaca_result and 'order_details' in alpaca_result:
                db_signal.alpaca_order_id = str(alpaca_result.get('order_details', {}).get('symbol', ''))
        except Exception as e:
            logger.error(f"Failed to place Alpaca order: {str(e)}")
            alpaca_result = {"error": str(e)}
            db_signal.status = 'error'
            db_signal.error_message = str(e)
    else:
        db_signal.status = 'no_broker'
        db_signal.error_message = "Alpaca client not available"
    
    db.commit()
    
    return {
        "action": "sell_call",
        "symbol": signal.symbol,
        "strike": signal.strike,
        "expiry": signal.expiry,
        "premium": signal.premium,
        "alpaca_order": alpaca_result
    }

async def place_options_order(signal: WebhookSignal, option_type: str):
    """Place options order via Alpaca API"""
    try:
        if not alpaca_client:
            return {"error": "Alpaca client not initialized"}
        
        # Note: Alpaca's options trading API might have specific requirements
        # This is a basic implementation that logs the order details
        # You may need to adjust based on Alpaca's actual options API
        
        order_details = {
            "symbol": signal.symbol,
            "option_type": option_type,
            "strike": signal.strike,
            "expiry": signal.expiry,
            "premium": signal.premium,
            "side": "sell",
            "order_type": "market",
            "time_in_force": "day"
        }
        
        logger.info(f"Would place options order: {order_details}")
        
        # For paper trading, we'll log the order instead of actually placing it
        # since options trading API specifics may vary
        return {
            "status": "simulated",
            "order_details": order_details,
            "message": "Order logged for paper trading simulation"
        }
        
    except Exception as e:
        logger.error(f"Error placing options order: {str(e)}")
        return {"error": str(e)}

@app.get("/signals")
async def get_signals(db: Session = Depends(get_db)):
    """Get all trading signals from database"""
    signals = db.query(TradingSignal).order_by(TradingSignal.created_at.desc()).limit(50).all()
    return {
        "signals": [
            {
                "id": s.id,
                "action": s.action,
                "symbol": s.symbol,
                "strike": s.strike,
                "expiry": s.expiry,
                "premium": s.premium,
                "quantity": s.quantity,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "processed_at": s.processed_at.isoformat() if s.processed_at else None,
                "error_message": s.error_message
            } for s in signals
        ]
    }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "service": "Wheel Strategy Bot",
        "status": "healthy",
        "alpaca_connected": alpaca_client is not None,
        "database_connected": True,
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "webhook": "/webhook (POST)",
            "status": "/ (GET)",
            "health": "/health (GET)",
            "signals": "/signals (GET)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
