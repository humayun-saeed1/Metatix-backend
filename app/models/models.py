from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Numeric, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.database import Base
import enum

# --- ENUMS --- 
class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    ORGANIZER = "Organizer"
    CUSTOMER = "Customer"

class EventStatus(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"

# --- TABLES ---

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    
    # 🚨 CHANGED: nullable=True (Google users don't have passwords!)
    password_hash = Column(String(255), nullable=True) 
    
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER)
    created_at = Column(DateTime, server_default=func.now())
    is_organizer_pending = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # --- NEW COLUMNS FOR ROADMAP ---
    profile_pic_url = Column(String(500), nullable=True) # Profile Pic
    auth_provider = Column(String(50), default="local")  # "local" or "google"
    
    phone_number = Column(String(20), nullable=True) 

    # 🚨 NEW: Stripe Integration Columns
    stripe_customer_id = Column(String(255), unique=True, nullable=True) # For Buyers
    stripe_connect_id = Column(String(255), unique=True, nullable=True)  # For Organizer payouts

    # Relationship to Events
    events = relationship("Event", back_populates="organizer")


class Venue(Base):
    __tablename__ = "venues"
    venue_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    address = Column(Text)
    total_capacity = Column(Integer, nullable=False)

    # Relationship to Events (Venue hosts many events)
    events = relationship("Event", back_populates="venue")


class Event(Base):
    __tablename__ = "events"
    event_id = Column(Integer, primary_key=True)
    organizer_id = Column(Integer, ForeignKey("users.user_id")) # Explicit Integer type is safer
    venue_id = Column(Integer, ForeignKey("venues.venue_id"))   # Explicit Integer type is safer
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(EventStatus), default=EventStatus.PENDING)
    rejection_reason = Column(Text)
    isactive = Column(Boolean, default=True)

    # --- RELATIONSHIPS (The Fix!) ---
    organizer = relationship("User", back_populates="events")
    venue = relationship("Venue", back_populates="events")
    
    # Children relationships (One-to-Many)
    schedules = relationship("EventSchedule", back_populates="event", cascade="all, delete-orphan")
    tiers = relationship("TicketTier", back_populates="event", cascade="all, delete-orphan")


class EventSchedule(Base):
    __tablename__ = "event_schedules"
    schedule_id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.event_id"))
    schedule_name = Column(String(100))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    # Relationship back to Event
    event = relationship("Event", back_populates="schedules")


class TicketTier(Base):
    __tablename__ = "ticket_tiers"
    tier_id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.event_id"))
    tier_name = Column(String(100), nullable=False)
    
    # 🚨 THE FIX: Immutable original price
    base_price = Column(Numeric(10, 2), nullable=False, server_default="0.00") 
    
    current_price = Column(Numeric(10, 2), nullable=False) # The dynamic sale price
    available_quantity = Column(Integer, nullable=False)

    # Relationship back to Event
    event = relationship("Event", back_populates="tiers")


class Booking(Base):
    __tablename__ = "bookings"
    booking_id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.user_id"))
    tier_id = Column(Integer, ForeignKey("ticket_tiers.tier_id")) 
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    # 🚨 ONLY adding the Platform Fee for your financial dashboard
    platform_fee = Column(Numeric(10, 2), default=0.00) 
    
    status = Column(Enum("Pending", "Confirmed", "Cancelled", name="booking_status"), default="Pending")
    created_at = Column(DateTime, server_default=func.now())

    payout_status = Column(String(50), default="Pending")
    
    tickets = relationship("Ticket", back_populates="booking")
    tier = relationship("TicketTier")


    @property
    def event(self):
        if self.tier and self.tier.event:
            return {
                "title": self.tier.event.title,
                "venue_name": self.tier.event.venue.name if self.tier.event.venue else "TBA"
            }
        return None

class Payment(Base):
    __tablename__ = "payments"
    payment_id = Column(Integer, primary_key=True)
    booking_id = Column(ForeignKey("bookings.booking_id"), unique=True)
    
    # We will store the Stripe "pi_xxxxxx" (Payment Intent ID) here
    transaction_id = Column(String(255), unique=True) 
    
    payment_method = Column(String(50), default="Card")
    
    # 🚨 THE FIX: Added "Pending" and "Refunded" to handle Stripe's real-time flow
    status = Column(Enum("Pending", "Successful", "Failed", "Refunded", name="payment_status"), default="Pending")
    
    timestamp = Column(DateTime, server_default=func.now())
    


class Ticket(Base):
    __tablename__ = "tickets"
    ticket_id = Column(Integer, primary_key=True)
    booking_id = Column(ForeignKey("bookings.booking_id"))
    tier_id = Column(ForeignKey("ticket_tiers.tier_id"))
    purchased_price = Column(Numeric(10, 2), nullable=False)
    seat_identifier = Column(String(50))
    qr_code_hash = Column(String(255), unique=True, nullable=False)
    status = Column(Enum("Valid", "Scanned", "Cancelled", name="ticket_status"), default="Valid")
    booking = relationship("Booking", back_populates="tickets")