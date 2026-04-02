Event Ticket Booking Platform - BackendThis is the core REST API for the Event Ticket Booking Platform, built with Python and FastAPI. It handles user authentication, event management, real-time ticket availability, and secure booking transactions.🚀 Tech StackFramework: FastAPI (Asynchronous Python)Database: PostgreSQL (Relational storage for ERD compliance)ORM: SQLAlchemy or Tortoise ORMAuthentication: JWT (JSON Web Tokens) with OAuth2 Password FlowValidation: Pydantic models🏗️ System ArchitectureThe backend follows a layered architecture to ensure scalability for the final project:API Router: Handles incoming requests and versioning.Service Layer: Contains the business logic (e.g., checking if tickets are sold out).Data Access Layer: Interfaces with the database using the Repository pattern.🛠️ Getting StartedPrerequisitesPython 3.9+PostgreSQL installed and runningVirtual Environment (venv)InstallationClone the repository:Bashgit clone <your-repo-url>
cd backend
Create and activate a virtual environment:Bashpython -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies:Bashpip install -r requirements.txt
Environment Variables:Create a .env file in the root directory:Code snippetDATABASE_URL=postgresql://user:password@localhost:5432/event_db
SECRET_KEY=your_super_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
Run the migrations:Bashalembic upgrade head
Start the server:Bashuvicorn main:app --reload
📑 API Endpoints (Brief)MethodEndpointDescriptionPOST/auth/signupRegister a new userPOST/auth/loginGet JWT access tokenGET/eventsList all upcoming eventsPOST/bookingsReserve a ticket (Requires Auth)GET/users/meGet current user profile📊 Database Schema (ERD)The backend is structured based on the following core entities:Users: Stores credentials and roles (Admin/Customer).Events: Details, timing, location, and total capacity.Tickets: Links users to events with unique booking IDs.🧪 TestingTo run the test suite:Bashpytest
📜 LicenseDistributed under the MIT License.