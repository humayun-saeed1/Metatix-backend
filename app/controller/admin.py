from app.models.database import get_db
from app import schema
from app.services import admin_services
from app.api import deps
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models import models
from typing import List
from datetime import datetime, timedelta
from app.models import models
from sqlalchemy import func, or_
from app.core.scheduler import platform_scheduler, execute_discount_math




router = APIRouter()

@router.post("/create_venue", response_model=schema.VenueResponse)
def create_venue(venue: schema.VenueCreate, db: Session = Depends(get_db),current_user : models.User = Depends(deps.get_current_user)): 
    if current_user.role not in [models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can create venues")
    address = f"{venue.name} {venue.city}".lower()
    existing_venue = admin_services.get_venue_by_address(db=db, address=address)
    if existing_venue:
        raise HTTPException(status_code=400, detail="Venue already exists")
    return admin_services.create_venue(db=db, venue=venue)  

@router.get("/organizer_requests", response_model=list[schema.UserResponse])
def view_pending_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    # Security Check
    if current_user.role not in ["Admin", models.UserRole.ADMIN]: # handling both cases for safety
        raise HTTPException(status_code=403, detail="Only admins can view requests")
        
    return admin_services.get_pending_org_req(db)


# 2. APPROVE REQUEST
@router.put("/approve_organizer/{user_id}")
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in ["Admin", models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can approve users")

    user = admin_services.approve_org_req(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"message": f"User {user.email} promoted to Organizer successfully"}


# 3. REJECT REQUEST
@router.put("/reject_organizer/{user_id}")
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in ["Admin", models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can reject requests")

    user = admin_services.reject_org_req(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"message": f"Request for user {user.email} rejected."}


@router.get("/event-requests", response_model=list[schema.EventResponse])
def get_event_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in ["Admin", models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can view event requests")
    return admin_services.get_pending_event_requests(db)


@router.put("/approve_event/{event_id}")
def approve_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in ["Admin", models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can approve events")

    event = admin_services.approve_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    return {"message": f"Event {event.title} approved successfully"}

@router.put("/reject_event/{event_id}")
def reject_event(
    event_id: int,
    request: schema.EventRejectRequest, # <--- 1. Expect JSON body here
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in ["Admin", models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can reject events")

    # 2. Pass request.reason to the service
    event = admin_services.reject_event(db, event_id, request.reason) 
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    return {
        "message": f"Event '{event.title}' rejected successfully",
        "reason": event.rejection_reason
    }

@router.get("/particular-organizer-stats/{organizer_id}", response_model=schema.OrganizerStats)
def get_organizer_stats(
    organizer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in ["Admin", models.UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can view organizer stats")

    return admin_services.get_organizer_sales(db, organizer_id)


@router.get("/platform-stats", response_model=schema.PlatformStats)
def get_platform_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    # STRICT SECURITY: Only 'Admin' can see global stats
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Only Super Admins can view platform stats."
        )
    
    return admin_services.get_global_platform_stats(db)


@router.put("/users/{user_id}/ban")
def ban_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Bans a user or organizer and instantly cancels all their events.
    """
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can ban users.")

    banned_user = admin_services.toggle_user_ban(db, target_user_id=user_id, ban_status=True)
    return {"message": f"User {banned_user.email} has been permanently banned."}


@router.put("/users/{user_id}/unban")
def unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Restores a user's access (Note: this does not automatically un-cancel their events).
    """
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can unban users.")

    restored_user = admin_services.toggle_user_ban(db, target_user_id=user_id, ban_status=False)
    return {"message": f"User {restored_user.email} has been restored."}

@router.put("/users/{user_id}/promote-admin")
def promote_user_to_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Grants Admin privileges to another user.
    """
    # 🛑 The Bouncer: Only Admins can make other Admins
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=403, 
            detail="Access Denied: Only current Admins can promote users to Admin."
        )

    promoted_user = admin_services.promote_to_admin(db, target_user_id=user_id)
    
    return {
        "message": f"Success! User '{promoted_user.email}' has been promoted to Admin.",
        "new_role": promoted_user.role
    }

@router.put("/users/{user_id}/demote")
def revoke_admin_privileges(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Removes Admin privileges from a user. Only the Root Admin (User #1) can do this.
    """
    # 🛑 The Ultimate Bouncer: Only User #1 has this power
    if current_user.user_id != 1:
        raise HTTPException(
            status_code=403, 
            detail="Access Denied: Only the Root System Owner can revoke Admin rights."
        )
        
    if current_user.user_id == user_id:
        raise HTTPException(status_code=400, detail="You cannot demote yourself.")

    demoted_user = admin_services.demote_admin(db, target_user_id=user_id)
    
    return {
        "message": f"Success! {demoted_user.email} has been stripped of Admin rights.",
        "new_role": demoted_user.role
    }

@router.get("/approved-organizers", response_model=List[schema.UserResponse])
def get_approved_organizers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in [models.UserRole.ADMIN, "Admin"]:
        raise HTTPException(status_code=403, detail="Only admins can view this list.")
        
    # 🚨 Updated filter to include both Organizers AND Admins
    organizers = db.query(models.User).filter(
        models.User.role.in_(["Organizer", "Admin"])
    ).all()
    return organizers

@router.get("/all_users", response_model=List[schema.UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role not in [models.UserRole.ADMIN, "Admin"]:
        raise HTTPException(status_code=403, detail="Only admins can view all users.")
    
    return db.query(models.User).all()

@router.get("/treasury/stats")
def get_treasury_stats(db: Session = Depends(get_db), current_user: models.User = Depends(deps.get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admins only.")

    stats = db.query(
        func.sum(models.Booking.total_amount).label("gross_volume"),
        func.sum(models.Booking.platform_fee).label("net_profit")
    ).filter(models.Booking.status == "Confirmed").first()

    return {
        "gross_volume": float(stats.gross_volume or 0),
        "metatix_profit": float(stats.net_profit or 0),
        "organizer_payouts": float((stats.gross_volume or 0) - (stats.net_profit or 0))
    }


@router.post("/market/schedule-discount")
def schedule_flash_sale(
    payload: schema.DiscountPayload, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admins only.")

    if payload.percentage < 0 or payload.percentage > 100:
        raise HTTPException(status_code=400, detail="Percentage must be between 0 and 100.")

    # 1. Schedule the START of the campaign
    platform_scheduler.add_job(
        execute_discount_math,
        'date',
        run_date=payload.start_date,
        args=[payload.percentage],
        id=f"start_{payload.name}_{payload.start_date}"
    )

    # 2. Schedule the END of the campaign (0% restores original price)
    platform_scheduler.add_job(
        execute_discount_math,
        'date',
        run_date=payload.end_date,
        args=[0],
        id=f"end_{payload.name}_{payload.end_date}"
    )

    return {
        "message": f"Success! Campaign '{payload.name}' is armed.",
        "start": payload.start_date,
        "end": payload.end_date,
        "status": "Awaiting execution in background."
    }

@router.get("/market/active-campaigns")
def get_active_campaigns(db: Session = Depends(get_db), current_user: models.User = Depends(deps.get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admins only.")

    # Find ANY ticket tier where the price is currently slashed
    active_discount_tier = db.query(models.TicketTier).filter(
        models.TicketTier.current_price < models.TicketTier.base_price
    ).first()

    campaigns = []
    
    if active_discount_tier:
        # Reverse-engineer the math to find the percentage!
        base = float(active_discount_tier.base_price)
        current = float(active_discount_tier.current_price)
        
        if base > 0:
            discount_ratio = current / base
            percentage_off = round((1 - discount_ratio) * 100)
            
            campaigns.append({
                "id": "live_global",
                "name": "Global Active Discount",
                "percentage": percentage_off,
                "endsAt": "Scheduled via Engine"
            })
            
    return campaigns
