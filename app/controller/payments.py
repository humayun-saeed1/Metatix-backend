import stripe
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import models
from app.api import deps
from app.core.config import settings
from app.services import booking_services
import traceback

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter()

# --- SCHEMA FOR CHECKOUT ---
class StripeCheckoutRequest(BaseModel):
    booking_ids: List[int]

# ==========================================
# 1. CUSTOMER CHECKOUT (MONEY IN)
# ==========================================
@router.post("/create-cart-session")
def create_cart_checkout(
    request: StripeCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    line_items = []
    
    for booking_id in request.booking_ids:
        booking = db.query(models.Booking).filter(
            models.Booking.booking_id == booking_id,
            models.Booking.user_id == current_user.user_id,
            models.Booking.status == "Pending"
        ).first()
        
        if not booking:
            raise HTTPException(status_code=404, detail=f"Pending booking {booking_id} not found.")

        unit_price_cents = int((booking.total_amount / booking.quantity) * 100)

        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"{booking.tier.event.title} - {booking.tier.tier_name}",
                    "description": f"Metatix Booking #{booking.booking_id}",
                },
                "unit_amount": unit_price_cents,
            },
            "quantity": booking.quantity,
        })

    if not line_items:
        raise HTTPException(status_code=400, detail="No valid items to checkout.")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url="https://metatix-frontend.vercel.app/mytickets?success=true&session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://metatix-frontend.vercel.app/cart",
            metadata={
                "user_id": current_user.user_id,
                "booking_ids": ",".join(map(str, request.booking_ids)) 
            }
        )
        return {"url": session.url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ==========================================
# 2. STRIPE WEBHOOK (CONFIRMATION)
# ==========================================
@router.post("/webhook")
async def stripe_webhook(
    request: Request, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print(f"⚠️ Webhook signature failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        booking_ids = session["metadata"]["booking_ids"].split(",")

        print(f"💰 Payment confirmed for User ID: {user_id}")

        for b_id in booking_ids:
            try:
                booking_services.process_payment_and_generate_tickets(
                    db=db,
                    booking_id=int(b_id),
                    user_id=user_id,
                    payment_method="Stripe Card", 
                    background_tasks=background_tasks,
                    # 🚨 THE FIX: Pass the real Stripe ID!
                    stripe_id=session.payment_intent 
                )
                print(f"🎫 Tickets generated for Booking #{b_id}")
            except Exception as e:
                print(f"❌ Error processing booking {b_id}: {str(e)}")

    return {"status": "success"}

# ==========================================
# 3. VERIFY CHECKOUT (FRONTEND REDIRECT)
# ==========================================
@router.post("/verify-checkout/{session_id}")
def verify_checkout(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    try:
        # 1. Ask Stripe if this session was actually paid
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status != "paid":
            raise HTTPException(status_code=400, detail="Payment not completed.")

        # 2. Extract metadata safely
        metadata = getattr(session, "metadata", None)
        booking_ids_str = ""
        
        if metadata:
            if hasattr(metadata, "booking_ids"):
                booking_ids_str = metadata.booking_ids
            elif hasattr(metadata, "get"):
                booking_ids_str = metadata.get("booking_ids", "")
            elif hasattr(metadata, "to_dict"):
                booking_ids_str = metadata.to_dict().get("booking_ids", "")

        booking_ids = [b_id.strip() for b_id in str(booking_ids_str).split(",") if b_id.strip()]
        
        if not booking_ids:
            return {"status": "success", "message": "No bookings to process in metadata."}

        verified_bookings = []
        
        # 3. Check the database
        for b_id in booking_ids:
            booking = db.query(models.Booking).filter(
                models.Booking.booking_id == int(b_id),
                models.Booking.user_id == current_user.user_id
            ).first()
            
            if not booking or booking.status == "Confirmed":
                if booking: verified_bookings.append(booking.booking_id)
                continue
                
            if booking.status == "Pending":
                try:
                    booking_services.process_payment_and_generate_tickets(
                        db=db,
                        booking_id=int(b_id),
                        user_id=current_user.user_id,
                        payment_method="Stripe Card - Verified Sync", 
                        background_tasks=background_tasks,
                        # 🚨 THE FIX: Pass the real Stripe ID!
                        stripe_id=session.payment_intent 
                    )
                    verified_bookings.append(booking.booking_id)
                except HTTPException as e:
                    if "duplicate key" in str(e.detail) or "UniqueViolation" in str(e.detail):
                        verified_bookings.append(booking.booking_id)
                    else:
                        raise e

        return {"status": "success", "verified_bookings": verified_bookings}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))