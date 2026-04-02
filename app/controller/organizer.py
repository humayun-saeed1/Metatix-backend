from app.models.database import get_db
from app import schema
from app.services import admin_services
from app.api import deps
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session 
from sqlalchemy import func
from app.models import models
from sqlalchemy.orm import Session, joinedload

router = APIRouter()

@router.get("/my-sales", response_model=schema.OrganizerSalesResponse)
def get_my_sales(db: Session = Depends(get_db), current_user = Depends(deps.get_current_user)):
    
    # 1. Fetch all events owned by this specific organizer
    events = db.query(models.Event).filter(models.Event.organizer_id == current_user.user_id).all()
    
    total_organizer_net_revenue = 0
    total_platform_tickets = 0
    events_response = []

    for event in events:
        event_net_revenue = 0
        event_tickets = 0
        tiers_response = []
        
        for tier in event.tiers:
            # 🚨 THE FIX: Query the Booking table for BOTH quantity and fees
            # We only count "Confirmed" bookings so we don't show fake money from abandoned carts
            stats = db.query(
                func.sum(models.Booking.quantity).label("sold"),
                func.sum(models.Booking.total_amount).label("gross"),
                func.sum(models.Booking.platform_fee).label("fees")
            ).filter(
                models.Booking.tier_id == tier.tier_id,
                models.Booking.status == "Confirmed" 
            ).first()

            # Safely handle None values if no tickets are sold yet
            sold_count = stats.sold or 0
            gross_revenue = float(stats.gross or 0.0)
            platform_fees = float(stats.fees or 0.0)
            
            # 💰 THE MATH: What the organizer actually gets
            tier_net_profit = gross_revenue - platform_fees
            
            # Debugging - This will now DEFINITELY show up in your terminal
            

            event_tickets += sold_count
            event_net_revenue += tier_net_profit
            
            tiers_response.append({
                "tier_name": tier.tier_name,
                "price": tier.current_price,
                "total_capacity": tier.available_quantity + sold_count, 
                "tickets_sold": sold_count
            })

        total_organizer_net_revenue += event_net_revenue
        total_platform_tickets += event_tickets
        
        events_response.append({
            "event_id": event.event_id,
            "name": event.title,
            "status": event.status, 
            "tickets_sold": event_tickets,
            "revenue": event_net_revenue, # Now sending the true NET profit
            "tiers": tiers_response
        })

    return {
        "total_events_created": len(events),
        "total_revenue": total_organizer_net_revenue,
        "total_tickets_sold": total_platform_tickets,
        "events": events_response
    }

@router.post("/scan/{qr_hash}")
def scan_ticket(
    qr_hash: str, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(deps.get_current_user)
):
    clean_hash = qr_hash.strip()

    # 1. Authorization
    if current_user.role not in [models.UserRole.ORGANIZER, models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="You do not have permission to scan tickets.")

    # 2. Find the ticket safely
    ticket = db.query(models.Ticket).filter(models.Ticket.qr_code_hash == clean_hash).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Unrecognized QR Code. Ticket not found in the system.")

    # 3. 🚨 THE PERFECT FIX: Follow your models.py structure exactly 🚨
    # Jump straight from Ticket -> TicketTier
    tier = db.query(models.TicketTier).filter(models.TicketTier.tier_id == ticket.tier_id).first()
    
    # Jump straight from TicketTier -> Event
    event = db.query(models.Event).filter(models.Event.event_id == tier.event_id).first()

    # 4. Security: Ensure the organizer actually owns this event
    if current_user.role == models.UserRole.ORGANIZER:
        if event.organizer_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Invalid Access. This ticket belongs to an event you do not manage.")

    # 5. Check the Ticket Status
    if ticket.status == "Scanned":
        raise HTTPException(status_code=400, detail="ALREADY SCANNED: This ticket has already been used!")
        
    if ticket.status in ["Cancelled", "Refunded"]:
        raise HTTPException(status_code=400, detail="VOID TICKET: This ticket was cancelled or refunded.")

    # 6. Success! Mark it as scanned and save to the database
    ticket.status = "Scanned"
    db.commit()
    
    # 7. Return the data to React!
    return {
        "ticket_id": ticket.ticket_id,
        "event_title": event.title,
        "tier_name": tier.tier_name,
        "status": ticket.status
    }