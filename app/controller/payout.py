import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal
from datetime import datetime, timedelta

from app.models.database import get_db
from app.models import models
from app.api import deps
from app.core.config import settings
from app.services.payout_services import get_organizer_financials
from app.schema import RefundRequest

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter()

# ==========================================
# 1. ORGANIZER FINANCIAL OVERVIEW
# ==========================================
@router.get("/financial-overview")
def get_financial_overview(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role != models.UserRole.ORGANIZER:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Get money buckets from our service
    finances = get_organizer_financials(db, current_user.user_id)

    # Check Stripe Status dynamically
    stripe_status = "NOT_STARTED"
    payouts_enabled = False

    if current_user.stripe_connect_id:
        try:
           account = stripe.Account.retrieve(current_user.stripe_connect_id)
        
        # Direct dot-notation for both! No .get() and no getattr()
           stripe_status = "COMPLETED" if account.details_submitted else "INCOMPLETE"
           payouts_enabled = account.payouts_enabled
        
        except Exception as e:
        # If it crashes, it defaults to ERROR and keeps payouts locked
          print(f"Stripe Error: {e}")
          stripe_status = "ERROR"
          payouts_enabled = False

    return {
        "finances": finances,
        "stripe_status": stripe_status,
        "payouts_enabled": payouts_enabled,
        "has_stripe_id": bool(current_user.stripe_connect_id)
    }

# ==========================================
# 2. ORGANIZER ONBOARDING (CONNECT BANK)
# ==========================================
@router.post("/onboard")
def onboard_organizer(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role != models.UserRole.ORGANIZER:
        raise HTTPException(status_code=403, detail="Only organizers can set up payouts.")

    # Create account if they don't have one
    if not current_user.stripe_connect_id:
        try:
            # 🚨 THE FIX: Removed the strict "capabilities" dictionary. 
            # We will just let Stripe apply your dashboard defaults!
            account = stripe.Account.create(
                type="express",
                email=current_user.email,
            )
            current_user.stripe_connect_id = account.id
            db.commit()
        except Exception as e:
            # This prints the EXACT error in your terminal so we aren't guessing!
            print(f"🚨 STRIPE ERROR: {str(e)}") 
            raise HTTPException(status_code=500, detail=f"Stripe account creation failed: {str(e)}")

    # Generate the setup link
    try:
        account_link = stripe.AccountLink.create(
            account=current_user.stripe_connect_id,
            refresh_url="http://localhost:5173/organizer-dashboard?stripe=refresh", 
            return_url="http://localhost:5173/organizer-dashboard?stripe=success",  
            type="account_onboarding",
        )
        return {"url": account_link.url}
    except Exception as e:
        print(f"🚨 STRIPE LINK ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Link generation failed: {str(e)}")
# ==========================================
# 3. EXECUTE PAYOUT (MONEY OUT)
# ==========================================
@router.post("/withdraw")
def request_withdrawal(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(deps.get_current_user)
):
    if not current_user.stripe_connect_id:
        raise HTTPException(status_code=400, detail="Stripe account not linked.")

    finances = get_organizer_financials(db, current_user.user_id)
    amount_to_transfer = finances["available_to_withdraw"]

    if amount_to_transfer <= 0:
        raise HTTPException(status_code=400, detail="No funds available for withdrawal.")

    amount_in_cents = int(Decimal(str(amount_to_transfer)) * 100)

    try:
        transfer = stripe.Transfer.create(
            amount=amount_in_cents,
            currency="usd",
            destination=current_user.stripe_connect_id,
            description=f"Payout for Organizer #{current_user.user_id}"
        )

        now = datetime.utcnow()
        bookings_to_update = db.query(models.Booking).options(
            joinedload(models.Booking.tier).joinedload(models.TicketTier.event).joinedload(models.Event.schedules)
        ).join(
            models.TicketTier, models.Booking.tier_id == models.TicketTier.tier_id
        ).join(
            models.Event, models.TicketTier.event_id == models.Event.event_id
        ).filter(
            models.Event.organizer_id == current_user.user_id,
            models.Booking.status == "Confirmed",
            (models.Booking.payout_status == "Pending") | (models.Booking.payout_status.is_(None)) 
        ).all()

        for booking in bookings_to_update:
            event = booking.tier.event
            if event.schedules:
                latest_end_time = max(schedule.end_time for schedule in event.schedules)
                if now >= (latest_end_time + timedelta(hours=48)):
                    booking.payout_status = "Paid"

        db.commit()
        return {"status": "success", "transfer_id": transfer.id, "amount_transferred": amount_to_transfer}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Payout failed: {str(e)}")
    
@router.post("/refund")
def process_refund(
    request: RefundRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    # 1. Grab booking, tier, event, schedules, AND the individual tickets
    booking = db.query(models.Booking).options(
        joinedload(models.Booking.tier)
            .joinedload(models.TicketTier.event)
            .joinedload(models.Event.schedules),
        joinedload(models.Booking.tickets)
    ).filter(
        models.Booking.booking_id == request.booking_id,
        models.Booking.user_id == current_user.user_id 
    ).first()

    if not booking or booking.status != "Confirmed":
        raise HTTPException(status_code=400, detail="Invalid booking or already cancelled/refunded.")

    # 2. THE TIME CHECK LOGIC (Commented out for your testing)
    event = booking.tier.event
    if not event.schedules:
        raise HTTPException(status_code=400, detail="Event has no schedule.")
    
    earliest_start_time = min(schedule.start_time for schedule in event.schedules)
    refund_cutoff = earliest_start_time - timedelta(hours=24)
    now = datetime.utcnow() 

    # if now >= refund_cutoff:
    #     raise HTTPException(
    #         status_code=400, 
    #         detail="Refund window has closed. Refunds are only allowed up to 24 hours before the event."
    #     )

    # 3. GET THE PAYMENT RECORD (Where the Stripe ID actually lives)
    payment_record = db.query(models.Payment).filter(
        models.Payment.booking_id == booking.booking_id
    ).first()

    if not payment_record or not payment_record.transaction_id:
        raise HTTPException(status_code=404, detail="No Stripe transaction ID found in payments table.")

    # 4. Process the Stripe Refund
    try:
        stripe_id = payment_record.transaction_id
        
        # If it's a checkout session (cs_...), we must fetch the Payment Intent (pi_...)
        if stripe_id.startswith("cs_"):
            session = stripe.checkout.Session.retrieve(stripe_id)
            stripe_id = session.payment_intent

        # Trigger the actual refund on Stripe
        stripe.Refund.create(payment_intent=stripe_id)

        # 5. UPDATE DATABASE
        
        # A. Update Booking status to "Cancelled"
        booking.status = "Cancelled"
        
        # B. Update Payment status to "Refunded"
        payment_record.status = "Refunded"
        
        # C. Restore Capacity to the Ticket Tier
        booking.tier.available_quantity += booking.quantity
        
        # D. Void the individual tickets
        for ticket in booking.tickets:
            ticket.status = "Cancelled"

        db.commit()
        return {"status": "success", "message": "Refund processed and inventory restored."}

    except stripe.error.StripeError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Stripe Error: {str(e)}")
    except Exception as e:
        db.rollback()
        print("🚨 REFUND CRASH:")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error during refund.")