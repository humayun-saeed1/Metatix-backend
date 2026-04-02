from apscheduler.schedulers.background import BackgroundScheduler
from app.models.database import SessionLocal  

# 1. Boot up the global scheduler
platform_scheduler = BackgroundScheduler()
platform_scheduler.start()

# 2. Define the exact task that runs in the background
def execute_discount_math(percentage: float):
    """This function wakes up, opens a DB session, runs the math, and closes it."""
    db = SessionLocal() # Open a private background DB session
    try:
        from app.models import models # Import inside to avoid circular imports
        
        active_tiers = db.query(models.TicketTier).join(models.Event).filter(
            models.Event.status == "APPROVED"
        ).all()

        multiplier = (100 - percentage) / 100.0

        for tier in active_tiers:
            if percentage == 0:
                tier.current_price = tier.base_price
            else:
                new_price = float(tier.base_price) * multiplier
                tier.current_price = round(new_price, 2)
                
        db.commit()
        print(f"⏰ SCHEDULER: Successfully executed {percentage}% discount.")
    except Exception as e:
        print(f"⏰ SCHEDULER ERROR: {e}")
        db.rollback()
    finally:
        db.close() # Always close the background session!