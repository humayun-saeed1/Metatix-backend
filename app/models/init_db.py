from database import Base , engine
from models import User, Venue, Event, EventSchedule, TicketTier, Booking, Payment, Ticket

# Create all tables in the database
Base.metadata.create_all(bind=engine)

