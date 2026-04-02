from sqlalchemy.orm import Session
from app.models import models
from app import schema
from datetime import datetime, timedelta
from fastapi import HTTPException, BackgroundTasks
from app.services import email_services, sms_services
import stripe
from app.models.database import SessionLocal
import traceback

# --- 1. THE MASS REFUND BACKGROUND TASK ---
def process_mass_refunds(event_id: int):
    """
    Runs in the background. Refunds Stripe payments and processes
    manual TXN- payments locally.
    """
    # 🚨 Open a fresh DB session because this runs in the background!
    db = SessionLocal()
    
    try:
        print(f"💸 Starting Mass Refund for Event #{event_id}...")
        
        # Find all Confirmed bookings for this event
        bookings = db.query(models.Booking).join(models.TicketTier).filter(
            models.TicketTier.event_id == event_id, 
            models.Booking.status == "Confirmed"
        ).all()

        refund_count = 0

        for booking in bookings:
            payment_record = db.query(models.Payment).filter(
                models.Payment.booking_id == booking.booking_id
            ).first()

            if not payment_record or not payment_record.transaction_id:
                continue 

            stripe_id = payment_record.transaction_id

            try:
                # --- STRIPE REFUND LOGIC ---
                if stripe_id.startswith("pi_") or stripe_id.startswith("cs_"):
                    if stripe_id.startswith("cs_"):
                        session = stripe.checkout.Session.retrieve(stripe_id)
                        stripe_id = session.payment_intent

                    # Tell Stripe to return the money
                    stripe.Refund.create(payment_intent=stripe_id)
                    print(f"✅ Stripe Refunded: {stripe_id}")
                else:
                    # --- MANUAL DB REFUND LOGIC ---
                    print(f"✅ Manual DB Refunded: {stripe_id} (Skipped Stripe)")
                
                # --- UPDATE DATABASE FOR EVERYONE ---
                booking.status = "Cancelled"
                payment_record.status = "Refunded"
                booking.tier.available_quantity += booking.quantity
                
                for ticket in booking.tickets: 
                    ticket.status = "Cancelled"
                
                refund_count += 1
                
            except stripe.error.StripeError as e:
                print(f"⚠️ Stripe Error refunding Booking #{booking.booking_id}: {e}")
                continue # Skip this one but keep refunding the rest!

        db.commit()
        print(f"🏁 Mass Refund Complete! {refund_count} orders refunded for Event #{event_id}.")

    except Exception as e:
        print(f"🚨 Critical Error in Mass Refund:")
        traceback.print_exc()
    finally:
        db.close() # Always close the background session!


# --- 2. STANDARD EVENT SERVICES ---
def get_event_by_id(db: Session, event_id: int):
    return db.query(models.Event).filter(models.Event.event_id == event_id).first()

def create_event(db: Session , event: schema.EventCreate, organizer_id: int):
    db_event = models.Event(
        title=event.title,
        description=event.description,
        venue_id=event.venue_id,
        organizer_id=organizer_id,
        status="Pending",  
        isactive=True
    )
    db.add(db_event)
    db.flush()
    
    for schedule in event.schedules:
        db_schedule = models.EventSchedule(
            event_id=db_event.event_id,
            schedule_name=schedule.schedule_name,
            start_time=schedule.start_time,
            end_time=schedule.end_time
        )
        db.add(db_schedule)
    
    for tier in event.tiers:
        db_tier = models.TicketTier(
            event_id=db_event.event_id,
            tier_name=tier.tier_name,
            base_price=tier.current_price,
            current_price=tier.current_price,
            available_quantity=tier.available_quantity
        )
        db.add(db_tier)
    
    db.commit()
    db.refresh(db_event)
    return db_event

def cancel_event(db: Session, event_id: int, current_user: models.User, background_tasks: BackgroundTasks):
    # 1. Fetch the Event
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
        
    if event.status == models.EventStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Event is already cancelled.")

    # --- 2. ROLE-BASED BUSINESS LOGIC ---
    if current_user.role == "Organizer":
        if event.organizer_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="You can only cancel your own events.")
            
        first_schedule = db.query(models.EventSchedule).filter(
            models.EventSchedule.event_id == event_id
        ).order_by(models.EventSchedule.start_time.asc()).first()

        if first_schedule:
            deadline = datetime.now() + timedelta(days=2) 
            if first_schedule.start_time <= deadline:
                raise HTTPException(
                    status_code=400, 
                    detail="Too late to cancel! You must cancel at least 48 hours before start time."
                )

    elif current_user.role == "Admin":
        pass 
    else:
        raise HTTPException(status_code=403, detail="Customers cannot cancel events.")

    # --- 3. EXECUTE CANCELLATION ---
    event.status = models.EventStatus.CANCELLED
    event.isactive = False        # Soft delete for safety
    db.commit()                   # 🚨 Save the event status immediately so the UI updates!

    # 🚨 TRIGGER THE MASS REFUND IN THE BACKGROUND
    background_tasks.add_task(process_mass_refunds, event_id)

    # --- 4. NOTIFY USERS ---
    bookings = db.query(models.Booking).join(models.TicketTier).filter(
        models.TicketTier.event_id == event_id, 
        models.Booking.status == "Confirmed" # Only email people who actually paid
    ).all()

    emailed_users = set() 

    for booking in bookings:
        if booking.user_id not in emailed_users:
            customer = db.query(models.User).filter(models.User.user_id == booking.user_id).first()
            if customer:
                background_tasks.add_task(
                    email_services.send_cancellation_email,
                    customer.email,
                    event.title
                )
                if customer.phone_number:
                    background_tasks.add_task(
                        sms_services.send_cancellation_sms,
                        customer.phone_number,
                        event.title
                    )
                emailed_users.add(booking.user_id)
            
    db.refresh(event)
    return event

def deactivate_past_events(db: Session):
    """
    Finds all active events where the final schedule has ended,
    and automatically sets isactive to False.
    """
    now = datetime.now()
    updated_count = 0

    active_events = db.query(models.Event).filter(
        models.Event.isactive == True
    ).all()

    for event in active_events:
        if not event.schedules:
            continue
        
        latest_end_time = max(schedule.end_time for schedule in event.schedules)

        if now > latest_end_time:
            event.isactive = False
            updated_count += 1
    
    if updated_count > 0:
        db.commit()
        print(f"🧹 Event Sniper: Deactivated {updated_count} expired events.")