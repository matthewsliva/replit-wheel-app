from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import re

class WebhookSignal(BaseModel):
    """Pydantic model for webhook signal validation"""
    
    action: str = Field(
        ...,
        description="Trading action: sell_put or sell_call",
        example="sell_put"
    )
    
    symbol: str = Field(
        ...,
        description="Stock symbol (e.g., AAPL, MSFT)",
        example="AAPL",
        min_length=1,
        max_length=10
    )
    
    strike: float = Field(
        ...,
        description="Strike price of the option",
        example=150.00,
        gt=0
    )
    
    expiry: str = Field(
        ...,
        description="Option expiry date in YYYY-MM-DD format",
        example="2024-01-19"
    )
    
    premium: float = Field(
        ...,
        description="Premium price for the option",
        example=2.50,
        gt=0
    )
    
    quantity: Optional[int] = Field(
        default=1,
        description="Number of contracts (default: 1)",
        example=1,
        gt=0
    )
    
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
        schema_extra = {
            "example": {
                "action": "sell_put",
                "symbol": "AAPL",
                "strike": 150.00,
                "expiry": "2024-03-15",
                "premium": 3.25,
                "quantity": 1
            }
        }
