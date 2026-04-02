from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import models
from app import schema
from fastapi import HTTPException
from datetime import datetime, timedelta
from app.models import models

def get_venue_by_address(db: Session, address: str):
    return db.query(models.Venue).filter(func.lower(models.Venue.name + " " + models.Venue.city) == address.lower()).first()

def create_venue(db: Session, venue: schema.VenueCreate):
    db_venue = models.Venue(
        name=venue.name,
        city=venue.city,
        address=venue.address,
        total_capacity=venue.total_capacity,
    )
    db.add(db_venue)
    db.commit()
    db.refresh(db_venue)
    return db_venue


def get_pending_org_req(db: Session):
    return db.query(models.User).filter(models.User.is_organizer_pending == True).all()

def approve_org_req(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if user:
        user.role = models.UserRole.ORGANIZER
        user.is_organizer_pending = False
        db.commit()
        db.refresh(user)
        return user
def reject_org_req(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if user:
        user.is_organizer_pending = False
        db.commit()
        db.refresh(user)
        return user

# app/services/admin_services.py

def get_global_platform_stats(db: Session):
    # (Keep your existing queries for total_users, total_events, etc. here)
    total_users = db.query(models.User).count()
    total_organizers = db.query(models.User).filter(models.User.role == "Organizer").count()
    total_events = db.query(models.Event).count()
    
    # Get all confirmed bookings
    confirmed_bookings = db.query(models.Booking).filter(models.Booking.status == "Confirmed").all()
    
    total_revenue = sum([float(b.total_amount) for b in confirmed_bookings])
    total_tickets = sum([b.quantity for b in confirmed_bookings])

    # 🚨 THE REAL DATA FIX: Group revenue by month for the Bar Chart!
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly_totals = {}
    
    for booking in confirmed_bookings:
        if booking.created_at >= six_months_ago:
            month_name = booking.created_at.strftime("%b") # Turns date into "Jan", "Feb"
            if month_name not in monthly_totals:
                monthly_totals[month_name] = 0.0
            monthly_totals[month_name] += float(booking.total_amount)

    # Build the array for the last 6 months (even if a month had $0 in sales)
    revenue_trend = []
    for i in range(5, -1, -1):
        target_month = datetime.now() - timedelta(days=30 * i)
        month_name = target_month.strftime("%b")
        revenue_trend.append({
            "month": month_name,
            "revenue": monthly_totals.get(month_name, 0.0)
        })

    # Return exactly what your Pydantic schema expects
    return {
        "total_revenue": total_revenue,
        "total_tickets_sold": total_tickets,
        "total_events": total_events,
        "total_users": total_users,
        "total_organizers": total_organizers,
        "revenue_trend": revenue_trend # Real data leaves the server here!
    }

def get_pending_event_requests(db: Session):
    return db.query(models.Event).filter(models.Event.status == models.EventStatus.PENDING).all()

def approve_event(db: Session, event_id: int):
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if event:
        event.status = models.EventStatus.APPROVED
        db.commit()
        db.refresh(event)
        return event


def reject_event(db: Session, event_id: int, reason: str = None):
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if event:   
        event.status = models.EventStatus.REJECTED
        event.isactive = False  # Also mark as inactive to hide from listings
        if reason:
            event.rejection_reason = reason
        else:
            event.rejection_reason = "No reason provided"
        db.commit()
        db.refresh(event)
        return event



def get_organizer_sales(db: Session, organizer_id: int):
    # Get all events for this organizer
    events = db.query(models.Event).filter(models.Event.organizer_id == organizer_id).all()
    event_sales = []
    grand_total_revenue = 0
    grand_total_tickets = 0     
    total_events_counts = len(events)

    for event in events:
        # Join Tickets through TicketTiers to calculate sales for this event
        stats = db.query(
            func.count(models.Ticket.ticket_id).label("tickets_sold"),
            func.sum(models.Ticket.purchased_price).label("revenue")
        ).join(models.TicketTier).filter(models.TicketTier.event_id == event.event_id, models.Ticket.status == "Valid").first()   
        tickets_sold = stats.tickets_sold or 0
        revenue = float(stats.revenue or 0)
        
        grand_total_revenue += revenue
        grand_total_tickets += tickets_sold     
        event_sales.append({
            "event_id": event.event_id,
            "name": event.title,
            "tickets_sold": tickets_sold,
            "revenue": revenue
        })

    return {
        "total_events_created": total_events_counts,
        "total_revenue": grand_total_revenue,
        "total_tickets_sold": grand_total_tickets,
        "events": event_sales
    }      


def toggle_user_ban(db: Session, target_user_id: int, ban_status: bool):
    """
    ban_status = True means the user is BANNED (is_active = False).
    ban_status = False means the user is UNBANNED (is_active = True).
    """
    user = db.query(models.User).filter(models.User.user_id == target_user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.role == models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You cannot ban another Admin!")

    # If ban_status is True, is_active becomes False
    user.is_active = not ban_status

    # THE NUKE: If we are banning an Organizer, shut down all their events
    if ban_status is True and user.role == models.UserRole.ORGANIZER:
        active_events = db.query(models.Event).filter(
            models.Event.organizer_id == target_user_id,
            models.Event.isactive == True
        ).all()
        
        for event in active_events:
            event.isactive = False
            event.status = models.EventStatus.CANCELLED
            event.rejection_reason = "Organizer account suspended by Administrator."

    db.commit()
    db.refresh(user)
    return user
def promote_to_admin(db: Session, target_user_id: int):
    """
    Promotes a normal Customer or Organizer to an Admin.
    """
    user = db.query(models.User).filter(models.User.user_id == target_user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.role == models.UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="User is already an Admin!")

    # Grant God Mode
    user.role = models.UserRole.ADMIN
    
    db.commit()
    db.refresh(user)
    return user

def demote_admin(db: Session, target_user_id: int):
    """
    Strips Admin privileges and returns the user to a normal Customer.
    """
    user = db.query(models.User).filter(models.User.user_id == target_user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 🛑 THE SHIELD: No one can ever demote the original creator
    if target_user_id == 1:
        raise HTTPException(status_code=403, detail="The Root Admin can never be demoted.")

    if user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="This user is not an Admin.")

    # Strip the privileges and make them a Customer again
    user.role = models.UserRole.CUSTOMER
    
    db.commit()
    db.refresh(user)
    return user