# DataBossX

A comprehensive document processing and analysis platform that combines OCR (Optical Character Recognition) with multiple LLM providers for intelligent document analysis.

## Features

- **Document Upload & Processing**: Upload documents for automated OCR processing
- **Multi-OCR Support**: Integrated OCR engines including PaddleOCR and Tesseract
- **LLM Analysis**: Analyze documents using multiple AI models:
  - OpenAI GPT-4
  - Anthropic Claude
  - Google Gemini
- **Real-time Processing**: Background task processing for large documents
- **Analytics Dashboard**: Track document processing metrics and system performance
- **System Logging**: Comprehensive logging and monitoring capabilities

## Tech Stack

### Backend
- **FastAPI**: High-performance web framework
- **SQLite/aiosqlite**: Asynchronous database operations
- **Pydantic**: Data validation and settings management
- **Playwright**: Browser automation for document processing
- **Multiple AI SDKs**: OpenAI, Anthropic, Google Generative AI

### Frontend
- **React 19**: Modern UI framework
- **React Router**: Client-side routing
- **Axios**: HTTP client for API communication
- **Tailwind CSS**: Utility-first CSS framework

## Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd DataBoss
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

5. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

6. Configure your environment variables in `.env`:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
FRONTEND_URL=http://localhost:3000
BACKEND_DOCKER_URL=http://host.docker.internal:8009
MOCK_AUTH=true

# AI API Keys (at least one required)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
# or
yarn install
```

## Running the Application

### Development Mode

**Backend:**
```bash
# From the root directory
python backend/server.py
# or
uvicorn backend.server:app --reload --port 8001
```

**Frontend:**
```bash
# From the frontend directory
npm start
# or
yarn start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Documentation: http://localhost:8001/docs

### Docker Deployment

```bash
docker build -t databossx .
docker run -p 8001:8001 --env-file .env databossx
```

## API Endpoints

### Health Check
- `GET /api/health` - System health and available services

### Documents
- `POST /api/documents/upload` - Upload a document for processing
- `GET /api/documents` - List all documents
- `GET /api/documents/{document_id}` - Get document details with OCR and LLM results

### Analytics
- `GET /api/analytics` - System analytics and metrics
- `GET /api/logs` - System logs (default limit: 100)

## Project Structure

```
DataBoss/
├── backend/
│   ├── server.py              # Main FastAPI application
│   └── external_integrations/ # External service integrations
├── frontend/
│   ├── src/                   # React application source
│   └── package.json           # Frontend dependencies
├── automation/
│   ├── playwright_bot.py      # Browser automation
│   ├── parsing.py             # Document parsing with LLM
│   ├── status_logic.py        # Status processing logic
│   └── writer.py              # Document writing utilities
├── tests/                     # Test files
├── scripts/                   # Utility scripts
├── prompts/                   # LLM prompts
├── logs/                      # Application logs
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
└── README.md                  # This file
```

## Testing

Run backend tests:
```bash
pytest
# With coverage
pytest --cov=backend tests/
```

Run frontend tests:
```bash
cd frontend
npm test
```

## Development

### Code Quality

The project uses several code quality tools:

- **Black**: Code formatting
- **Flake8**: Linting
- **MyPy**: Static type checking
- **ESLint**: JavaScript/React linting

Run code quality checks:
```bash
# Python
black .
flake8 .
mypy backend/

# Frontend
cd frontend
npm run lint
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For issues, questions, or contributions, please open an issue on the GitHub repository.
