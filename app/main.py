# app/main.py
from fastapi import FastAPI
from app.controller import auth, events, admin, booking, user ,organizer , payments , payout

import asyncio
from contextlib import asynccontextmanager
from app.models.database import SessionLocal 
from app.services.booking_services import release_expired_bookings

# 🚨 IMPORT YOUR EVENT SERVICES HERE
from app.services import event_services 

from fastapi.middleware.cors import CORSMiddleware

# --- BACKGROUND TASK 1: THE CART SNIPER (Runs every 5 mins) ---
async def cart_cleanup_loop():
    while True:
        db = SessionLocal() 
        try:
            release_expired_bookings(db)
        except Exception as e:
            print(f"Error in Cart Sniper: {e}")
        finally:
            db.close() 
        await asyncio.sleep(300) # 300 seconds = 5 minutes

# --- BACKGROUND TASK 2: THE EVENT SNIPER (Runs every 1 hour) ---
async def event_cleanup_loop():
    while True:
        db = SessionLocal() 
        try:
            # 🚨 Make sure this function exists in your event_services.py!
            event_services.deactivate_past_events(db)
        except Exception as e:
            print(f"Error in Event Sniper: {e}")
        finally:
            db.close() 
        await asyncio.sleep(3600) # 3600 seconds = 1 hour


# --- FASTAPI LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Background Tasks...")
    
    # Fire up both snipers
    cart_task = asyncio.create_task(cart_cleanup_loop())
    event_task = asyncio.create_task(event_cleanup_loop())
    
    yield # The server is running here!
    
    print("🛑 Shutting down Background Tasks...")
    # Kill both snipers on shutdown
    cart_task.cancel()
    event_task.cancel()

# --- APP INIT ---
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# Connect the "wires" from the controller
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(organizer.router, prefix="/organizer", tags=["Organizer"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(booking.router, prefix="/booking", tags=["Booking"])
app.include_router(payments.router, prefix="/stripe", tags=["Payments"])
app.include_router(payout.router, prefix="/payouts", tags=["Payouts"])

@app.get("/")
def root():
    return {"message": "Ticket System is Underconstruction!"}