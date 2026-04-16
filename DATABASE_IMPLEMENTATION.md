# Database Implementation for TTC Chatbot - Complete Summary

## What Was Implemented

### 1. **Database Layer** (`backend/database.py`)
- SQLAlchemy ORM setup with support for both SQLite (development) and PostgreSQL (production)
- Automatic database initialization via `init_db()` function
- Session management with FastAPI dependency injection

**Configuration:**
- Default: SQLite at `./ttc_chatbot.db`
- Production: Set `DATABASE_URL` env variable for PostgreSQL

### 2. **Database Models** (`backend/models.py`)

#### Session Model
Stores conversation sessions with metadata:
- `id`: UUID primary key
- `user_id`: Optional user identifier
- `created_at`, `updated_at`: Timestamps
- `topic`: Conversation topic (e.g., "Line 1 delays")
- `feedback_score`: User rating (1-5)
- Relationship: Multiple messages per session

#### Message Model
Stores individual messages (user and bot):
- `id`: UUID primary key
- `session_id`: Foreign key to Session
- `role`: "user" or "bot"
- `content`: Message text
- `created_at`: Timestamp
- **For user messages:**
  - `extracted_line`: Detected TTC line
  - `extracted_station`: Detected station
  - `extracted_time`: Detected time
  - `extracted_day`: Detected day
  - `intent`: Message intent classification
  - `confidence_score`: NLP confidence
- **For bot messages:**
  - `ml_used`: Whether ML predictor was used
  - `ml_model_version`: Model version that made prediction
  - `prediction_data`: Full prediction JSON result

### 3. **Service Layer** (`backend/services.py`)

#### SessionService
CRUD operations for sessions:
- `create_session()`: Create new session
- `get_session()`: Retrieve by ID
- `get_or_create_session()`: Get existing or create new
- `list_sessions()`: List with optional filtering by user_id
- `update_session()`: Update metadata (topic, feedback_score)
- `get_session_context()`: Build conversation context from history

#### MessageService
Message operations:
- `add_user_message()`: Save user message with entities and intent
- `add_bot_message()`: Save bot response with ML metadata
- `get_session_messages()`: Retrieve all messages in session
- `get_message()`: Get specific message by ID

### 4. **API Routes** (`backend/routes.py`)

#### Session Endpoints
- `POST /api/sessions` - Create new session
- `GET /api/sessions` - List sessions (optionally filtered by user_id)
- `GET /api/sessions/{session_id}` - Get session details
- `PATCH /api/sessions/{session_id}` - Update session metadata
- `POST /api/sessions/{session_id}/feedback` - Submit feedback/rating
- `DELETE /api/sessions/{session_id}` - Delete session

#### Message Endpoints
- `GET /api/sessions/{session_id}/messages` - Get all messages in session
- `GET /api/messages/{message_id}` - Get specific message

#### Utility Endpoints
- `POST /api/sessions/{session_id}/export` - Export session as JSON

### 5. **Main Application Integration** (`main.py`)

The `/chat` endpoint now:
1. Gets or creates a session in the database
2. Saves the user message with any extracted entities
3. Calls the NLP handler with session context (for multi-turn conversations)
4. Saves the bot response with ML metadata
5. Returns the response to the front end

All database operations have error handling to prevent chat failures due to DB issues.

---

## Key Features

✅ **Multi-turn Conversations** - Sessions store context for follow-up questions
✅ **Entity Extraction Storage** - Track detected lines, stations, times for analysis
✅ **ML Metadata** - Store which model version made each prediction
✅ **User Feedback** - Collect ratings for model improvement
✅ **Session Export** - Download full conversation as JSON
✅ **Conversation History** - Query past conversations by user or date
✅ **Easy Integration** - Fully integrated with existing FastAPI app

---

## Running the Application

### Development (with auto-reload)
```bash
python main.py
```

### With uvicorn directly
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
export DATABASE_URL="postgresql://user:pass@localhost/ttc_chatbot"
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Environment Variables

- `PORT` - Web server port (default: 8000)
- `DEBUG` - Enable debug logging: "true" or "false" (default: false)
- `ML_THRESHOLD` - Delay prediction threshold 0.0-1.0 (default: 0.5)
- `DATABASE_URL` - Database connection string (default: sqlite:///./ttc_chatbot.db)

---

## Database Schema

### sessions table
```sql
CREATE TABLE sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255),
    created_at DATETIME,
    updated_at DATETIME,
    topic VARCHAR(255),
    feedback_score INTEGER
);
```

### messages table
```sql
CREATE TABLE messages (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) FOREIGN KEY,
    role VARCHAR(10),
    content TEXT,
    created_at DATETIME,
    ml_used BOOLEAN,
    ml_model_version VARCHAR(50),
    prediction_data TEXT,
    extracted_line VARCHAR(50),
    extracted_station VARCHAR(255),
    extracted_time VARCHAR(50),
    extracted_day VARCHAR(20),
    confidence_score FLOAT,
    intent VARCHAR(50)
);
```

---

## Testing the Database

### Create a session
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "topic": "Line 1 delays"}'
```

### Send a chat message
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Will Line 1 be delayed at 5pm?",
    "session_id": "YOUR_SESSION_ID"
  }'
```

### Get session history
```bash
curl http://localhost:8000/api/sessions/YOUR_SESSION_ID/messages
```

### List all user sessions
```bash
curl "http://localhost:8000/api/sessions?user_id=user123"
```

### Export session as JSON
```bash
curl -X POST http://localhost:8000/api/sessions/YOUR_SESSION_ID/export
```

---

## Next Steps

1. **Test the API** - Use the Swagger UI at `http://localhost:8000/docs`
2. **Monitor conversations** - Check the database for stored messages and entities
3. **Implement NLP handler** - The NLP team should update `nlp/handler.py` to extract entities and return data in the expected format
4. **Add authentication** - Implement user authentication in the backend routes
5. **Build frontend** - Create a React/Vue app that uses the `/chat` and `/api/sessions/*` endpoints
6. **Deploy** - Use Docker Compose (support is already configured) or cloud deployment

---

## Files Modified/Created

- ✅ `main.py` - Updated chat endpoint with database integration
- ✅ `backend/database.py` - Added `init_db()` function
- ✅ `backend/models.py` - Complete (no changes needed)
- ✅ `backend/services.py` - Complete (no changes needed)
- ✅ `backend/routes.py` - Complete (no changes needed)
- ✅ `backend/__init__.py` - Created package marker
- ✅ `requirements.txt` - SQLAlchemy & psycopg2 already present

---

## Architecture Diagram

```
Frontend (Browser/Mobile)
        |
        | HTTP POST /chat
        | + HTTP GET /api/sessions/*
        v
    main.py (FastAPI)
        |
        +-- GET /docs (Swagger UI)
        +-- POST /chat (saves user & bot messages)
        |-- /api/sessions/* (CRUD operations)
        |
        v
    nlp/handler.py (NLP Layer)
        |
        v
    models/src/predictor.py (ML Predictions)
        |
        v
    SQLAlchemy ORM
        |
        v
    [Database: SQLite | PostgreSQL]
        |
        +-- sessions table
        +-- messages table
```

---

## Troubleshooting

**Issue: "Database not found"**
- Solution: Run `python main.py` to initialize database on startup

**Issue: "Foreign key constraint failed"**
- Solution: Ensure session exists before adding messages (auto-created in `/chat` endpoint)

**Issue: "PostgreSQL connection failed"**
- Solution: Set `DATABASE_URL` to valid PostgreSQL connection string

**Issue: Messages not being saved**
- Check logs for errors; database failures are logged but don't crash the API
- Verify database file has write permissions

