from typing import List
from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.orm import Session
import stripe # 🚨 Added to make your sync endpoint work
from app.models.database import get_db
from app import schema
from app.models import models
from app.api import deps
from app.services import booking_services
from datetime import datetime

router = APIRouter()

@router.post("/reserve", response_model=schema.BookingResponse)
def reserve_ticket(
    request: schema.TicketPurchaseRequest, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Step 1: Reserve the ticket and get a Pending Booking ID.
    """
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")
    
    tier = db.query(models.TicketTier).filter(
        models.TicketTier.tier_id == request.tier_id
    ).first()
    
    if not tier:
        raise HTTPException(status_code=404, detail="Ticket tier not found.")

    event = tier.event 

    if not event or not event.schedules:
        raise HTTPException(status_code=400, detail="Event schedules not found.")

    now = datetime.now()
    event_start = min(s.start_time for s in event.schedules)

    if now >= event_start:
       raise HTTPException(
          status_code=400, 
          detail="Ticket sales are closed. This event has already started or passed."
       )
    
    return booking_services.process_reservation(
        db=db, 
        user_id=current_user.user_id, 
        request=request
    ) 


@router.post("/checkout")
def checkout_booking(
    payment_data: schema.PaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Step 2: Pay for the Pending Booking manually (Non-Stripe flow).
    """
    return booking_services.process_payment_and_generate_tickets(
        db=db, 
        booking_id=payment_data.booking_id, 
        user_id=current_user.user_id,
        payment_method=payment_data.payment_method,
        # 🚨 FIX: Pass None since there is no Stripe session here
        stripe_id=None 
    )


@router.get("/my_tickets", response_model=List[schema.BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    View all past and current bookings.
    """
    return booking_services.get_user_bookings(
        db=db, 
        user_id=current_user.user_id
    )


@router.post("/sync/{booking_id}")
def sync_booking_status(
    booking_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Failsafe endpoint to verify a payment if the webhook missed it.
    """
    # 1. Find the booking
    booking = db.query(models.Booking).filter(
        models.Booking.booking_id == booking_id,
        models.Booking.user_id == current_user.user_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    # 2. If it's already confirmed, just return it
    if booking.status == "Confirmed":
        return {"status": "already_confirmed", "booking_id": booking_id}

    # 🚨 FIX: 3. Check the Payment table for the Stripe Session ID, NOT the Booking table!
    payment_record = db.query(models.Payment).filter(
        models.Payment.booking_id == booking.booking_id
    ).first()

    if payment_record and payment_record.transaction_id:
        stripe_id = payment_record.transaction_id
        
        try:
            # If it's a checkout session, retrieve it
            if stripe_id.startswith("cs_"):
                session = stripe.checkout.Session.retrieve(stripe_id)
                
                if session.payment_status == "paid":
                    # 🔥 The payment went through! Generate the tickets.
                    # We pass the real Payment Intent ID to save it properly
                    booking_services.process_payment_and_generate_tickets(
                        db=db,
                        booking_id=booking.booking_id,
                        user_id=current_user.user_id,
                        payment_method="Stripe Card - Verified Sync",
                        stripe_id=session.payment_intent 
                    )
                    return {"status": "success", "message": "Payment verified and tickets generated."}
        
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Stripe sync failed: {str(e)}")

    raise HTTPException(status_code=400, detail="Payment still pending on Stripe's end, or no Stripe session found.")