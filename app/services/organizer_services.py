from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import models
from app import schema
from fastapi import HTTPException, status
from datetime import datetime, timedelta

def get_organizer_sales(db: Session, organizer_id: int):
    # 1. Fetch all events owned by this specific organizer
    events = db.query(models.Event).filter(models.Event.organizer_id == organizer_id).all()
    
    event_list = []
    grand_total_revenue = 0.0
    grand_total_tickets = 0
    total_events_counts = len(events)

    for event in events:
        # 2. 🚨 THE FIX: Query the Booking table for CONFIRMED money only
        stats = db.query(
            func.sum(models.Booking.quantity).label("sold"),
            func.sum(models.Booking.total_amount).label("gross"),
            func.sum(models.Booking.platform_fee).label("fees")
        ).join(
            models.TicketTier, models.Booking.tier_id == models.TicketTier.tier_id
        ).filter(
            models.TicketTier.event_id == event.event_id,
            models.Booking.status == "Confirmed"  # Ignore abandoned carts!
        ).first()

        sold = stats.sold or 0
        gross = float(stats.gross if stats.gross is not None else 0.0)
        fees = float(stats.fees if stats.fees is not None else 0.0)


        
        # 3. 🚨 THE SUBTRACTION: Organizer Gross minus Your Cut
        net_profit = gross - fees
        
        grand_total_revenue += net_profit
        grand_total_tickets += sold
        
        print(f"DEBUG: Event: {event.title} | Gross: {gross} | Fees: {fees} | Net: {net_profit}")
        
        event_list.append({
            "event_id": event.event_id,
            "name": event.title,
            "tickets_sold": sold,
            "revenue": net_profit  # Now sending the true NET profit
        })

    return {
        "total_events_created": total_events_counts,
        "total_revenue": grand_total_revenue,
        "total_tickets_sold": grand_total_tickets,
        "events": event_list
    }