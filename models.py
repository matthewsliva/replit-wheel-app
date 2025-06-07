from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import re
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

class TradingSignal(Base):
    """SQLAlchemy model for storing trading signals in database"""
    __tablename__ = 'trading_signals'
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(20), nullable=False)
    symbol = Column(String(10), nullable=False)
    strike = Column(Float, nullable=False)
    expiry = Column(String(20), nullable=False)
    premium = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    status = Column(String(20), default='pending')
    alpaca_order_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)

class WebhookSignal(BaseModel):
    """Pydantic model for webhook signal validation"""
    
    action: str = Field(description="Trading action: sell_put or sell_call")
    symbol: str = Field(description="Stock symbol (e.g., AAPL, MSFT)", min_length=1, max_length=10)
    strike: float = Field(description="Strike price of the option", gt=0)
    expiry: str = Field(description="Option expiry date in YYYY-MM-DD format")
    premium: float = Field(description="Premium price for the option", gt=0)
    quantity: Optional[int] = Field(default=1, description="Number of contracts (default: 1)", gt=0)
    
    @validator('action')
    def validate_action(cls, v):
        """Validate trading action"""
        allowed_actions = ['sell_put', 'sell_call']
        if v.lower() not in allowed_actions:
            raise ValueError(f'Action must be one of: {", ".join(allowed_actions)}')
        return v.lower()
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate stock symbol format"""
        if not re.match(r'^[A-Za-z]{1,10}$', v):
            raise ValueError('Symbol must contain only letters and be 1-10 characters long')
        return v.upper()
    
    @validator('expiry')
    def validate_expiry(cls, v):
        """Validate expiry date format and ensure it's in the future"""
        try:
            expiry_date = datetime.strptime(v, '%Y-%m-%d').date()
            today = datetime.now().date()
            
            if expiry_date <= today:
                raise ValueError('Expiry date must be in the future')
                
            return v
        except ValueError as e:
            if 'does not match format' in str(e):
                raise ValueError('Expiry date must be in YYYY-MM-DD format')
            raise e
    
    @validator('strike')
    def validate_strike(cls, v):
        """Validate strike price"""
        if v <= 0:
            raise ValueError('Strike price must be greater than 0')
        if v > 10000:  # Reasonable upper limit
            raise ValueError('Strike price seems unreasonably high')
        return round(v, 2)
    
    @validator('premium')
    def validate_premium(cls, v):
        """Validate premium price"""
        if v <= 0:
            raise ValueError('Premium must be greater than 0')
        if v > 1000:  # Reasonable upper limit
            raise ValueError('Premium seems unreasonably high')
        return round(v, 2)
    
    class Config:
        """Pydantic model configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "action": "sell_put",
                "symbol": "AAPL",
                "strike": 150.00,
                "expiry": "2024-03-15",
                "premium": 3.25,
                "quantity": 1
            }
        }

# Database setup
def get_database_url():
    """Get database URL from environment variables"""
    return os.getenv("DATABASE_URL")

def create_db_engine():
    """Create database engine"""
    database_url = get_database_url()
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return create_engine(database_url)

def get_db_session():
    """Get database session"""
    engine = create_db_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()
