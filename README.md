🎟️ Metatix | Advanced Event Ticketing Ecosystem (Markdown)
🚀 Overview
Metatix is a high-performance async ticketing platform handling full event lifecycle:

Organizer creation → admin approval
Stripe checkout + refunds
Automated inventory and background task management
🧩 Tech Stack
Backend: FastAPI (Python 3.10+)
Frontend: React + Vite + Tailwind CSS
Database: PostgreSQL + SQLAlchemy
Payments: Stripe API
Tasks: asyncio-based schedulers
Security: JWT (OAuth2) + BCrypt passwords
🛠️ Key Features
🔐 Authentication
Role-Based Access Control (Customers, Organizers, Admins)
JWT stateless sessions
Secure password hashing
💳 Finance
Stripe checkout, metadata validation
Smart refunds for real + test transactions
Cart with multi-event checkout
🤖 Automation ("Snipers")
Cart Sniper: releases pending tickets after 15 min
Event Sniper: auto-deactivate events past final schedule
Mass Refund Sniper: bulk refunds on cancellation
📱 UX
Digital wallet with real-time status
PDF ticket generation + QR codes
Double-booking prevention (venue time validation)
🏗️ Architecture
controller: API routes + validation
services: business logic + background tasks
models: SQLAlchemy ORM
app/schema: Pydantic models
⚙️ Setup
1. Prerequisites
Python 3.9+
PostgreSQL
Stripe (Test)
2. Install
3. .env
4. DB + Server
📊 Core API Endpoints
POST /auth/signup : register customer/organizer
POST /events/create_event : organizer event request
POST /booking/reserve : reserve tickets (15min hold)
POST /stripe/create-cart-session : Stripe checkout session
PATCH /events/cancel/{id} : cancel + mass refund
GET /booking/my_tickets : user wallet + QR codes
📝 License
MIT License
Built with ❤️ by Humayun Saeed