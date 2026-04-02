from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal
from app.models import models

def get_organizer_financials(db: Session, organizer_id: int):
    """
    Calculates the 4 financial buckets for an Organizer.
    Includes logic for 48-hour event escrow and handles legacy test data.
    """
    bookings = db.query(models.Booking).options(
        joinedload(models.Booking.tier)
        .joinedload(models.TicketTier.event)
        .joinedload(models.Event.schedules)
    ).join(
        models.TicketTier, models.Booking.tier_id == models.TicketTier.tier_id
    ).join(
        models.Event, models.TicketTier.event_id == models.Event.event_id
    ).filter(
        models.Event.organizer_id == organizer_id,
        models.Booking.status == "Confirmed"
    ).all()

    finances = {
        "gross_sales": Decimal("0.0"),
        "platform_fees_paid": Decimal("0.0"),
        "pending_escrow": Decimal("0.0"),
        "available_to_withdraw": Decimal("0.0"),
        "already_withdrawn": Decimal("0.0")
    }

    now = datetime.utcnow()

    for booking in bookings:
        gross = Decimal(str(booking.total_amount))
        fee = Decimal(str(booking.platform_fee or 0.0))
        net_profit = gross - fee
        
        finances["gross_sales"] += gross
        finances["platform_fees_paid"] += fee

        # THE GHOST DATA FIX
        current_payout_status = booking.payout_status or "Pending"

        if current_payout_status == "Paid":  
            finances["already_withdrawn"] += net_profit
        
        elif current_payout_status == "Pending":
            event = booking.tier.event
            
            if not event.schedules:
                finances["pending_escrow"] += net_profit
                continue

            latest_end_time = max(schedule.end_time for schedule in event.schedules)
            event_cleared_time = latest_end_time + timedelta(hours=48)
            
            if now >= event_cleared_time:
                finances["available_to_withdraw"] += net_profit
            else:
                finances["pending_escrow"] += net_profit

    return {k: round(float(v), 2) for k, v in finances.items()}