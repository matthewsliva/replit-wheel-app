import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
import alpaca_trade_api as tradeapi
from models import WebhookSignal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Wheel Strategy Bot",
    description="Options trading webhook processor with Alpaca integration",
    version="1.0.0"
)

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
async def process_webhook(signal: WebhookSignal):
    """Process incoming trading webhook signals"""
    try:
        logger.info(f"Received webhook signal: {signal.dict()}")
        
        # Validate action
        if signal.action not in ["sell_put", "sell_call"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {signal.action}. Supported actions: sell_put, sell_call"
            )
        
        # Process the signal based on action
        if signal.action == "sell_put":
            result = await process_sell_put(signal)
        elif signal.action == "sell_call":
            result = await process_sell_call(signal)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"Successfully processed {signal.action} signal",
                "signal": signal.dict(),
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

async def process_sell_put(signal: WebhookSignal):
    """Process sell put signal"""
    action_msg = f"Selling PUT for {signal.symbol} - Strike: ${signal.strike}, Expiry: {signal.expiry}, Premium: ${signal.premium}"
    print(action_msg)
    logger.info(action_msg)
    
    # If Alpaca client is available, attempt to place order
    alpaca_result = None
    if alpaca_client:
        try:
            alpaca_result = await place_options_order(signal, "put")
        except Exception as e:
            logger.error(f"Failed to place Alpaca order: {str(e)}")
            alpaca_result = {"error": str(e)}
    
    return {
        "action": "sell_put",
        "symbol": signal.symbol,
        "strike": signal.strike,
        "expiry": signal.expiry,
        "premium": signal.premium,
        "alpaca_order": alpaca_result
    }

async def process_sell_call(signal: WebhookSignal):
    """Process sell call signal"""
    action_msg = f"Selling CALL for {signal.symbol} - Strike: ${signal.strike}, Expiry: {signal.expiry}, Premium: ${signal.premium}"
    print(action_msg)
    logger.info(action_msg)
    
    # If Alpaca client is available, attempt to place order
    alpaca_result = None
    if alpaca_client:
        try:
            alpaca_result = await place_options_order(signal, "call")
        except Exception as e:
            logger.error(f"Failed to place Alpaca order: {str(e)}")
            alpaca_result = {"error": str(e)}
    
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

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "service": "Wheel Strategy Bot",
        "status": "healthy",
        "alpaca_connected": alpaca_client is not None,
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "webhook": "/webhook (POST)",
            "status": "/ (GET)",
            "health": "/health (GET)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
