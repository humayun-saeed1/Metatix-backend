from pydantic import BaseModel, EmailStr,Field
from typing import Optional, List
from datetime import datetime
from app.models.models import EventStatus, UserRole 

# --- USER SCHEMAS ---
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone_number: Optional[str] = None


class UserResponse(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    role: str
    is_organizer_pending: bool
    is_active: bool
    profile_pic_url: Optional[str] = None
    auth_provider: Optional[str] = None
    class Config:
        from_attributes = True 

# Add this near your UserCreate / UserResponse schemas
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# --- VENUE SCHEMAS ---
class VenueCreate(BaseModel):
    name: str
    city: str
    address: Optional[str] = None
    total_capacity: int

class VenueResponse(BaseModel):
    venue_id: int
    name: str
    city: str
    address: Optional[str] = None
    total_capacity: int
    class Config:
        from_attributes = True

# --- NESTED EVENT SCHEMAS (Helpers) ---
class EventScheduleCreate(BaseModel):
    schedule_name: Optional[str] = "Main Event"
    start_time: datetime
    end_time: datetime

class TicketTierCreate(BaseModel):
    tier_name: str
    current_price: float
    available_quantity: int

# --- EVENT SCHEMAS ---
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    venue_id: int 
    

class EventCreate(EventBase):
    # Nested lists for creating everything in one go
    schedules: List[EventScheduleCreate] 
    tiers: List[TicketTierCreate]

class EventResponse(EventBase):
    event_id: int
    organizer_id: int
    status: EventStatus 
    rejection_reason: Optional[str] = None
    isactive: bool 

    # Return nested data for the Detail View
    schedules: List[EventScheduleCreate] = []
    tiers: List[TicketTierCreate] = []

    class Config:
        from_attributes = True

class EventLandingPageResponse(BaseModel):
    event_id: int
    title: str
    description: Optional[str] = None
    schedules: List[EventScheduleCreate] = []
    venue_name: str
    city: str
    status: EventStatus 
    class Config:
        from_attributes = True

class EventRejectRequest(BaseModel):
    reason: Optional[str] = "No reason provided"

class TierSales(BaseModel):
    tier_name: str
    price: float = 0.0
    total_capacity: int = 0
    tickets_sold: int = 0
    
    class Config:
        from_attributes = True

# --- BOOKING & TICKET SCHEMAS ---

class TicketPurchaseRequest(BaseModel):
    event_id: int
    tier_id: int
    quantity: int
    payment_amount: float

class TicketResponse(BaseModel):
    ticket_id: int
    seat_identifier: Optional[str] = None
    qr_code_hash: str
    status: str
    class Config:
        from_attributes = True

class EventMinimal(BaseModel):
    title: str
    venue_name: str

class BookingResponse(BaseModel):
    booking_id: int
    total_amount: float
    status: str
    # Includes the generated tickets so the user sees them immediately
    tickets: List[TicketResponse] = []

    event: Optional[EventMinimal] = None
    
    class Config:
        from_attributes = True


# Sales analysis schemas

class EventSales(BaseModel):
    event_id: int
    name: str
    status: Optional[str] = "Unknown"   # 🚨 Made Optional so Admin doesn't crash!
    tickets_sold: int = 0               # 🚨 Added defaults to prevent 500 errors
    revenue: float = 0.0
    tiers: List[TierSales] = []
    
    class Config:
        from_attributes = True


class OrganizerStats(BaseModel):
    total_events_created: int
    total_revenue: float
    total_tickets_sold: int
    events: List[EventSales]
    
    class Config:
        from_attributes = True

# For the Organizer Dashboard:
class OrganizerSalesResponse(BaseModel):
    total_events_created: int
    total_revenue: float
    total_tickets_sold: int
    events: List[EventSales]
    
    class Config:
        from_attributes = True

class MonthlyRevenue(BaseModel):
    month: str
    revenue: float

class PlatformStats(BaseModel):
    total_revenue: float
    total_tickets_sold: int
    total_events: int
    total_users: int
    total_organizers: int
    revenue_trend: List[MonthlyRevenue] = [] # 🚨 ADD THIS FOR THE BAR CHART!

    class Config:
        from_attributes = True

# app/schema.py



class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=4, description="Current password")
    new_password: str = Field(..., min_length=6, description="New strong password")

class PaymentRequest(BaseModel):
    booking_id: int
    payment_method: str = "Credit Card"

class DiscountPayload(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime
    percentage: float

class RefundRequest(BaseModel):
    booking_id: int


