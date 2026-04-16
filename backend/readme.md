# Backend Documentation

## Overview

The TTC Chatbot backend is built with **FastAPI** and includes:
- Session and conversation management
- Message storage and retrieval
- **JWT Authentication with Role-Based Access Control** ✨
- Database integration (SQLAlchemy ORM)
- RESTful API endpoints for session management
- Integration with ML prediction layer

---

## 🔐 Authentication & Authorization (NEW!)

The backend now includes comprehensive authentication and authorization:

### Quick Start
```bash
# 1. Create .env values (recommended)
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('ADMIN_SETUP_KEY=' + secrets.token_urlsafe(32))"

# 2. Start the app with .env exported (important)
set -a && source .env && set +a && python main.py

# 3. Login with default credentials
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# 4. Use token to access protected endpoints
curl -X GET http://localhost:8000/api/sessions \
  -H "Authorization: Bearer {token}"
```

### JWT & Security Keys Quick Guide

- `SECRET_KEY`: used to sign and validate JWT access tokens.
- `ADMIN_SETUP_KEY`: used only for `POST /api/auth/setup-admin` query parameter validation.
- Use different values for these keys.

Example `.env` entries:

```env
SECRET_KEY=replace-with-long-random-value
ADMIN_SETUP_KEY=replace-with-different-long-random-value
```

Token login and reuse example:

```bash
# Login and get access token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# Then call protected route with token
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <access_token>"
```

Admin setup example (first run only):

```bash
curl -X POST "http://localhost:8000/api/auth/setup-admin?security_key=$ADMIN_SETUP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin2","email":"admin2@example.com","password":"Keepkeep123.","full_name":"Admin User"}'
```

### Features
- **JWT Token Authentication** - Stateless, secure request authentication
- **Passlib Password Hashing** - Uses `pbkdf2_sha256` (with bcrypt compatibility support)
- **Role-Based Access Control (RBAC)** - 4 roles with granular permissions:
  - **ADMIN** - Full system access
  - **MODERATOR** - Moderate sessions and users
  - **USER** - Access own sessions only (default)
  - **GUEST** - Limited access (chat only)
- **Default Credentials** - Quick startup with demo users
- **Optional Authentication** - API routes work with or without auth tokens

### Default Users
| Username | Password | Role |
|----------|----------|------|
| `admin` | `changeme` | Admin |
| `demo` | `demo123` | User |
| `moderator` | `mod123` | Moderator |

### New Endpoints (`/api/auth`)
- `POST /register` - Create account with strong password validation
- `POST /login` - Authenticate and get JWT token
- `POST /refresh` - Refresh expired tokens
- `GET /me` - Get current user profile
- `PUT /me` - Update profile
- `POST /reset-password` - Change password
- `POST /setup-admin` - Initialize admin (first run)

### Authentication Flow

```
User Credentials
      ↓
POST /api/auth/login
      ↓
JWT Token Returned
      ↓
Include in: Authorization: Bearer {token}
      ↓
Protected Routes (authenticated sessions)
      ↓
Token Validated → Permission Check → Response
```

**👉 [See Full Authentication Guide](./AUTHENTICATION.md)** for:
- Detailed API documentation
- Role & permission definitions
- Password requirements
- Security best practices
- Environment configuration
- Code integration examples

---

## Architecture

```
Frontend (HTTP)
    ↓
FastAPI (main.py)
    ├─ POST /chat
    └─ Backend Routes (/api/sessions/*)
        ↓
SessionService & MessageService
        ↓
SQLAlchemy ORM
        ↓
Database (SQLite | PostgreSQL)
```

Current local setup commonly uses MySQL as well (via SQLAlchemy URL such as `mysql+pymysql://root@localhost:3306/ttc_chatbot`).

---

## Directory Structure

```
backend/
├── __init__.py            # Package initialization
├── database.py            # SQLAlchemy configuration & session management
├── models.py              # Database models (Session, Message, User, Permission)
├── services.py            # CRUD operations (SessionService, MessageService)
├── routes.py              # API endpoints for session/message management
├── auth.py                # Authentication & authorization logic ✨
├── auth_routes.py         # Authentication API endpoints ✨
├── schemas.py             # Pydantic request/response validation models ✨
├── admin_setup.py         # Admin setup and user management script ✨
├── readme.md              # Backend documentation
└── AUTHENTICATION.md      # Detailed authentication guide ✨
```

**New Files (Authentication):**
- `auth.py` - Core JWT, password hashing, RBAC logic
- `auth_routes.py` - API endpoints for register, login, token refresh, profile
- `schemas.py` - Pydantic models for request validation
- `admin_setup.py` - CLI tool for managing users
- `AUTHENTICATION.md` - Comprehensive auth documentation

---

## Core Components

### Database Configuration (`database.py`)

**Features:**
- SQLAlchemy ORM setup
- Support for SQLite (development) and PostgreSQL (production)
- Automatic connection pooling and recycling
- Dependency injection for FastAPI

**Usage:**
```python
from backend.database import get_db
from sqlalchemy.orm import Session

@app.post("/some-endpoint")
async def endpoint(db: Session = Depends(get_db)):
    # Use db session here
    pass
```

**Environment Variables:**
```bash
DATABASE_URL=sqlite:///./ttc_chatbot.db           # Default (development)
DATABASE_URL=postgresql://user:pass@localhost/db  # PostgreSQL (production)
```

### Data Models (`models.py`)

Models are organized into three categories:

#### Conversation Models

##### Session Model
Represents a user conversation session.

**Fields:**
- `id` (UUID): Unique session identifier
- `user_id` (UUID, optional): Link to User (if authenticated)
- `created_at` (datetime): Session creation timestamp
- `updated_at` (datetime): Last update timestamp
- `topic` (str, optional): Conversation topic (e.g., "Line 1 delays")
- `feedback_score` (int, optional): User rating 1-5
- `messages` (relationship): List of Message objects in this session

**Methods:**
- `to_dict()`: Convert session to dictionary

**Relationships:**
- `user` - One-to-Many with User model (sessions owned by user)
- `messages` - One-to-Many with Message model (messages in session)

##### Message Model
Represents a single message in a conversation.

**Fields:**
- `id` (UUID): Message identifier
- `session_id` (UUID, FK): Reference to parent session
- `role` (str): "user" or "bot"
- `content` (str): Message text
- `created_at` (datetime): Message timestamp
- `extracted_line` (str, optional): Detected TTC line (user messages)
- `extracted_station` (str, optional): Detected station (user messages)
- `extracted_time` (str, optional): Detected time (user messages)
- `extracted_day` (str, optional): Detected day (user messages)
- `intent` (str, optional): Message intent classification (user messages)
- `confidence_score` (float, optional): NLP confidence 0.0-1.0 (user messages)
- `ml_used` (bool): Whether ML predictor was used (bot messages)
- `ml_model_version` (str, optional): Model version that made prediction (bot messages)
- `prediction_data` (json): Full prediction result JSON (bot messages)

**Methods:**
- `to_dict()`: Convert message to dictionary

#### Authentication Models ✨

##### User Model
Represents a system user with authentication credentials.

**Fields:**
- `id` (UUID): User identifier
- `username` (str, unique): Username for login
- `email` (str, unique): Email address
- `hashed_password` (str): passlib-generated password hash
- `role` (Enum): UserRole (admin, moderator, user, guest)
- `is_active` (bool): Whether account is active
- `is_verified` (bool): Whether email is verified
- `created_at` (datetime): Account creation timestamp
- `last_login` (datetime, optional): Last login time
- `full_name` (str, optional): User's full name
- `permissions` (json, optional): Custom permissions JSON

**Methods:**
- `to_dict()`: Convert user to dictionary

**Relationships:**
- `sessions` - One-to-Many with Session model (user's sessions)

##### Permission Model
Represents system permissions for granular access control.

**Fields:**
- `id` (UUID): Permission identifier
- `name` (str, unique): Permission code (e.g., "chat:create", "sessions:read:all")
- `description` (str, optional): Human-readable description
- `created_at` (datetime): Creation timestamp

**Methods:**
- `to_dict()`: Convert permission to dictionary

##### UserRole Enum
Defines available roles with predefined permissions.

**Roles:**
- `ADMIN` - Full system access
- `MODERATOR` - Moderate content and users
- `USER` - Access own sessions
- `GUEST` - Limited access (chat only)

### Service Layer (`services.py`)

#### SessionService
Static methods for session CRUD operations:

**Methods:**
- `create_session(user_id, topic)` → Session
- `get_session(session_id, db)` → Session | None
- `get_or_create_session(session_id, db)` → Session
- `list_sessions(user_id, limit, db)` → List[Session]
- `update_session(session_id, topic, feedback_score, db)` → Session | None
- `get_session_context(session_id, db)` → dict

**Example:**
```python
from backend.services import SessionService
from backend.database import SessionLocal

db = SessionLocal()
session = SessionService.get_or_create_session("user_123", db)
context = SessionService.get_session_context(session.id, db)
```

#### MessageService
Static methods for message operations:

**Methods:**
- `add_user_message(session_id, content, db, extracted_*, intent, confidence_score)` → Message
- `add_bot_message(session_id, content, db, ml_used, ml_model_version, prediction_data)` → Message
- `get_session_messages(session_id, db, limit)` → List[Message]
- `get_message(message_id, db)` → Message | None

**Example:**
```python
from backend.services import MessageService

msg = MessageService.add_user_message(
    session_id="session_123",
    content="Will Line 1 be delayed?",
    db=db,
    extracted_line="Line 1",
    intent="delay_query",
    confidence_score=0.95
)
```

### API Routes (`routes.py`)

All routes are prefixed with `/api`:

#### Session Management

**POST /api/sessions** - Create a new session
```json
Request:  {"user_id": "user123", "topic": "Line 1 delays"}
Response: {
  "id": "uuid",
  "user_id": "user123",
  "created_at": "2026-04-11T10:30:00",
  "updated_at": "2026-04-11T10:30:00",
  "topic": "Line 1 delays",
  "feedback_score": null,
  "message_count": 0
}
```

**GET /api/sessions** - List sessions
```json
Query:    ?user_id=user123&limit=50
Response: [{ ... }, { ... }]
```

**GET /api/sessions/{session_id}** - Get session details
```json
Response: { "id": "uuid", ... }
```

**PATCH /api/sessions/{session_id}** - Update session
```json
Request:  {"topic": "New topic", "feedback_score": 5}
Response: { "id": "uuid", "topic": "New topic", ... }
```

**POST /api/sessions/{session_id}/feedback** - Submit feedback
```json
Request:  {"score": 4, "comment": "Good response"}
Response: {"message": "Feedback recorded", "score": 4}
```

**DELETE /api/sessions/{session_id}** - Delete session
```json
Response: {"message": "Session deleted"}
```

#### Message Management

**GET /api/sessions/{session_id}/messages** - Get messages in session
```json
Query:    ?limit=100
Response: [
  {
    "id": "uuid",
    "session_id": "uuid",
    "role": "user",
    "content": "...",
    "created_at": "...",
    "extracted_line": "Line 1",
    ...
  }
]
```

**GET /api/messages/{message_id}** - Get specific message
```json
Response: { "id": "uuid", ... }
```

#### Session Export

**POST /api/sessions/{session_id}/export** - Export session as JSON
```json
Response: {
  "session": { ... },
  "messages": [ ... ]
}
```

---

## Integration with /chat Endpoint

The main chat endpoint (`POST /chat` in `main.py`) automatically:

1. **Gets or creates a session** in the database
2. **Saves user message** with any extracted entities
3. **Builds session context** from conversation history
4. **Calls NLP handler** with context for multi-turn support
5. **Saves bot response** with ML metadata
6. **Returns response** to frontend

**Flow:**
```python
@app.post("/chat")
async def chat(request: ChatMessage, db: Session = Depends(get_db)):
    # 1. Get or create session
    session = SessionService.get_or_create_session(request.session_id, db)
    
    # 2. Save user message
    MessageService.add_user_message(session.id, request.message, db)
    
    # 3. Build context
    context = SessionService.get_session_context(session.id, db)
    
    # 4. Call NLP
    result = await handle_message(request.message, session.id, context)
    
    # 5. Save bot response
    MessageService.add_bot_message(
        session.id, result["response"], db,
        ml_used=result["ml_used"],
        prediction_data=result["data"]
    )
    
    # 6. Return response
    return ChatResponse(...)
```

---

## Testing

Run backend tests:

```bash
# All backend tests
pytest tests/test_backend/ -v

# Database tests only
pytest tests/test_backend/test_database.py -v

# With coverage
pytest tests/test_backend/ --cov=backend --cov-report=html
```

**Test Results:** 14/14 database tests passing ✅

See [TEST_RESULTS.md](../TEST_RESULTS.md) for detailed results.

---

## Development

### Running Locally

```bash
# Development with .env loaded (recommended)
set -a && source .env && set +a && python main.py

# Or with uvicorn
uvicorn main:app --reload --port 8000
```

### Interactive API Documentation

Visit `http://localhost:8000/docs` for Swagger UI.

### Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create random keys for .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('ADMIN_SETUP_KEY=' + secrets.token_urlsafe(32))"

# Sample .env values
# SECRET_KEY=<random-value>
# ADMIN_SETUP_KEY=<different-random-value>
# DATABASE_URL=mysql+pymysql://root@localhost:3306/ttc_chatbot

# Run migrations (if using Alembic in future)
# alembic upgrade head
```

---

## Production Deployment

### Database Setup

**PostgreSQL:**
```bash
# Create database
createdb ttc_chatbot

# Set environment variable
export DATABASE_URL="postgresql://user:password@localhost/ttc_chatbot"
```

### Running with Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Docker Deployment

```bash
# Build image
docker build -t ttc-chatbot .

# Run container
docker run -e DATABASE_URL="postgresql://..." -p 8000:8000 ttc-chatbot
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ttc_chatbot.db` | Database connection string |
| `PORT` | `8000` | Web server port |
| `DEBUG` | `false` | Enable debug logging |
| `ML_THRESHOLD` | `0.5` | Delay prediction threshold |
| `SECRET_KEY` | generated | JWT signing key (required in production) |
| `ADMIN_SETUP_KEY` | `change-me-in-production` fallback | Security key for `/api/auth/setup-admin` |

To generate a random code use this,
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Database Configuration (database.py)

```python
# SQLite (development)
- Single file storage
- No external dependencies
- Perfect for testing

# PostgreSQL (production)
- Connection pooling
- Pool recycling (1 hour)
- Connection pre-ping for reliability
- Support for multiple concurrent connections
```

---

## Troubleshooting

### Database Errors

**"Database is locked"**
- SQLite only: Use PostgreSQL for production
- Close any other connections to the database

**"Foreign key constraint failed"**
- Ensure message has valid session_id
- Messages are auto-saved in /chat endpoint

**"Connection pool exhausted"**
- PostgreSQL: Increase max pool size in database.py
- Or reduce number of concurrent connections

### Common Issues

| Issue | Solution |
|-------|----------|
| Migrations not running | Run `init_db()` on startup |
| Messages not saving | Check database connection & permissions |
| Slow queries | Add indexes on session_id, user_id |
| Memory leak | Ensure sessions are properly closed |
| `Invalid security key` on `/api/auth/setup-admin` | Start app with `.env` loaded (`set -a && source .env && set +a && python main.py`) and verify `security_key` matches `ADMIN_SETUP_KEY` |
| `Admin user already exists` on `/api/auth/setup-admin` | This is expected after first admin creation/default bootstrap; use `/api/auth/login` instead |
| `zsh: parse error near '<'` when killing PIDs | Do not type placeholders like `<pid1>`; use real PIDs or `lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill` |

---

## Performance Tips

1. **Use PostgreSQL for production** - Much better than SQLite under load
2. **Enable connection pooling** - Already configured in database.py
3. **Add indexes** - session_id, user_id, created_at are indexed
4. **Batch operations** - Use bulk_insert_mappings() for multiple messages
5. **Archive old sessions** - Delete sessions older than 90 days

---

## Future Enhancements

- [ ] Database migrations with Alembic
- [ ] Conversation analytics dashboard
- [ ] Full-text search on messages
- [ ] Session encryption at rest
- [ ] Automated backups
- [ ] Database replication/clustering
- [ ] Cache layer (Redis) for session context

---

## Related Files

- [main.py](../main.py) - Main application entry point
- [DATABASE_IMPLEMENTATION.md](../DATABASE_IMPLEMENTATION.md) - Database setup details
- [TEST_RESULTS.md](../TEST_RESULTS.md) - Test results and coverage
- [tests/test_backend/test_database.py](../tests/test_backend/test_database.py) - Test suite

---

## Contact & Support

For questions about the backend implementation:
1. Check the docstrings in database.py, models.py, services.py
2. Review the test suite in tests/test_backend/
3. See [DATABASE_IMPLEMENTATION.md](../DATABASE_IMPLEMENTATION.md) for setup

