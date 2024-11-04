# Meeting Transcription Web Application - Project Outline

## Project Structure
```
meeting-transcription/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── config.py            # Configuration management
│   │   ├── dependencies.py      # FastAPI dependencies
│   │   ├── websockets/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py       # WebSocket connection management
│   │   │   └── audio.py         # Audio streaming handlers
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── meeting.py       # Meeting data models
│   │   │   └── audio.py         # Audio processing models
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── transcription.py # Whisper integration
│   │   │   ├── storage.py       # File storage operations
│   │   │   └── export.py        # Export functionality
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── meetings.py  # Meeting endpoints
│   │   │   │   └── audio.py     # Audio processing endpoints
│   │   │   └── deps.py          # API specific dependencies
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── audio.py         # Audio processing utilities
│   │       └── errors.py        # Custom error definitions
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          # Test configurations
│   │   ├── test_api/           
│   │   └── test_services/
│   ├── alembic/                 # Database migrations
│   ├── requirements.txt
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AudioRecorder/
│   │   │   ├── MeetingList/
│   │   │   ├── Transcription/
│   │   │   └── common/
│   │   ├── hooks/
│   │   │   ├── useAudio.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── useMeeting.ts
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   ├── websocket.ts
│   │   │   └── storage.ts
│   │   ├── utils/
│   │   │   ├── audio.ts
│   │   │   └── errors.ts
│   │   ├── types/
│   │   ├── contexts/
│   │   └── pages/
│   ├── public/
│   ├── package.json
│   └── README.md
│
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── docker-compose.yml
│
└── README.md
```

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 16+
- Docker (optional)
- PostgreSQL
- Redis (for WebSocket state management)

### Backend Setup
1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Environment configuration (.env):
```env
DATABASE_URL=postgresql://user:password@localhost:5432/meeting_db
REDIS_URL=redis://localhost:6379
WHISPER_MODEL=base
JWT_SECRET=your-secret-key
CORS_ORIGINS=http://localhost:3000
```

4. Initialize database:
```bash
alembic upgrade head
```

### Frontend Setup
1. Install dependencies:
```bash
cd frontend
npm install
```

2. Environment configuration (.env):
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws
```

## Core Features Implementation

### 1. Audio Recording & Processing
- Use WebSocket for real-time audio streaming
- Implement audio chunking for efficient processing
- Handle browser audio API compatibility

```typescript
// frontend/src/hooks/useAudio.ts
export const useAudio = () => {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStream(stream);
    } catch (err) {
      setError(err as Error);
    }
  };

  // ... rest of implementation
};
```

### 2. Real-time Transcription
- Implement chunked audio processing
- Handle transcription errors gracefully
- Provide feedback on transcription progress

```python
# backend/app/services/transcription.py
class TranscriptionService:
    def __init__(self):
        self.model = whisper.load_model("base")
        self.audio_buffer = []

    async def process_audio_chunk(self, chunk: bytes) -> Optional[str]:
        try:
            self.audio_buffer.append(chunk)
            if len(self.audio_buffer) >= CHUNK_THRESHOLD:
                return await self._transcribe_buffer()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise TranscriptionError(str(e))
```

### 3. Meeting Management
- Implement CRUD operations for meetings
- Handle concurrent access
- Implement auto-saving

```python
# backend/app/api/v1/meetings.py
@router.post("/meetings")
async def create_meeting(
    meeting: MeetingCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        return await meeting_service.create_meeting(db, meeting)
    except DuplicateError:
        raise HTTPException(status_code=400, message="Meeting already exists")
```

## Error Handling & Debugging

### Backend Error Handling

1. Custom Exception Classes:
```python
# backend/app/utils/errors.py
class TranscriptionError(Exception):
    pass

class StorageError(Exception):
    pass

class AudioProcessingError(Exception):
    pass
```

2. Global Exception Handler:
```python
# backend/app/main.py
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__}
    )
```

### Frontend Error Handling

1. API Error Handling:
```typescript
// frontend/src/services/api.ts
class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const handleApiError = (error: unknown) => {
  if (error instanceof ApiError) {
    toast.error(error.message);
  } else {
    toast.error('An unexpected error occurred');
  }
};
```

2. WebSocket Error Handling:
```typescript
// frontend/src/hooks/useWebSocket.ts
export const useWebSocket = (url: string) => {
  useEffect(() => {
    const ws = new WebSocket(url);
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      toast.error('Connection error. Retrying...');
    };

    ws.onclose = () => {
      setTimeout(() => {
        console.log('Reconnecting...');
        // Implement reconnection logic
      }, 1000);
    };
  }, [url]);
};
```

## Debugging Strategies

### Backend Debugging

1. Logging Configuration:
```python
# backend/app/config.py
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'DEBUG',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
            'level': 'DEBUG',
        },
    },
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
}
```

2. Debug Endpoints:
```python
# backend/app/api/v1/debug.py
@router.get("/debug/audio-buffer")
async def get_audio_buffer_status():
    return {
        "buffer_size": len(audio_service.buffer),
        "processing_status": audio_service.status,
        "last_error": audio_service.last_error
    }
```

### Frontend Debugging

1. Debug Hooks:
```typescript
// frontend/src/hooks/useDebug.ts
export const useDebug = (componentName: string) => {
  useEffect(() => {
    console.log(`[${componentName}] Mounted`);
    return () => console.log(`[${componentName}] Unmounted`);
  }, [componentName]);

  const logError = useCallback((error: Error) => {
    console.error(`[${componentName}] Error:`, error);
  }, [componentName]);

  return { logError };
};
```

2. Performance Monitoring:
```typescript
// frontend/src/utils/performance.ts
export const measurePerformance = (label: string) => {
  const start = performance.now();
  return () => {
    const end = performance.now();
    console.log(`${label} took ${end - start}ms`);
  };
};
```

## Testing Strategy

### Backend Tests

1. API Tests:
```python
# backend/tests/test_api/test_meetings.py
async def test_create_meeting(client: AsyncClient):
    response = await client.post(
        "/api/v1/meetings",
        json={"title": "Test Meeting", "participants": ["John"]}
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Test Meeting"
```

2. Service Tests:
```python
# backend/tests/test_services/test_transcription.py
async def test_transcription_service(audio_chunk: bytes):
    service = TranscriptionService()
    result = await service.process_audio_chunk(audio_chunk)
    assert result is not None
    assert isinstance(result, str)
```

### Frontend Tests

1. Component Tests:
```typescript
// frontend/src/components/AudioRecorder/AudioRecorder.test.tsx
describe('AudioRecorder', () => {
  it('should handle recording state correctly', () => {
    const { getByRole } = render(<AudioRecorder />);
    const button = getByRole('button');
    fireEvent.click(button);
    expect(button).toHaveTextContent('Stop Recording');
  });
});
```

## Deployment

### Docker Setup

1. Backend Dockerfile:
```dockerfile
# docker/backend.Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Frontend Dockerfile:
```dockerfile
# docker/frontend.Dockerfile
FROM node:16-alpine

WORKDIR /app
COPY frontend/package*.json ./
RUN npm install

COPY frontend .
RUN npm run build

FROM nginx:alpine
COPY --from=0 /app/build /usr/share/nginx/html
```

3. Docker Compose:
```yaml
# docker/docker-compose.yml
version: '3.8'
services:
  backend:
    build:
      context: ..
      dockerfile: docker/backend.Dockerfile
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/meeting_db
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: ..
      dockerfile: docker/frontend.Dockerfile
    ports:
      - "80:80"

  db:
    image: postgres:13
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=meeting_db

  redis:
    image: redis:6
```

## Performance Optimization

1. Backend Optimizations:
- Use connection pooling for database
- Implement caching for frequently accessed data
- Use background tasks for heavy processing
- Implement rate limiting

2. Frontend Optimizations:
- Implement code splitting
- Use React.memo for expensive components
- Optimize bundle size
- Use service workers for offline capability

## Security Considerations

1. Backend Security:
- Implement JWT authentication
- Rate limiting
- Input validation
- CORS configuration
- Secure WebSocket connections

2. Frontend Security:
- Sanitize user input
- Implement CSP
- Handle sensitive data securely
- Implement proper authentication flow

## Monitoring & Maintenance

1. Backend Monitoring:
- Implement health check endpoints
- Set up logging aggregation
- Monitor system resources
- Track API performance metrics

2. Frontend Monitoring:
- Implement error tracking
- Monitor user interactions
- Track performance metrics
- Set up analytics

## Development Workflow

1. Version Control:
- Use feature branches
- Implement PR reviews
- Set up CI/CD pipelines
- Maintain changelog

2. Documentation:
- Maintain API documentation
- Update README files
- Document deployment procedures
- Keep configuration templates updated

This outline provides a comprehensive guide for implementing the meeting transcription web application. It covers all major aspects of development, from project setup to deployment and maintenance. The structure is designed to be scalable and maintainable, with proper error handling and debugging capabilities built in from the start.
