import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import logging

from config import config
from rag_system import RAGSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Course Materials RAG System", root_path="")

# Add trusted host middleware for proxy
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Enable CORS with proper settings for proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize RAG system
rag_system = RAGSystem(config)

# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None

class SourceLink(BaseModel):
    """Model for a source citation with optional link"""
    text: str
    link: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[SourceLink]
    session_id: str

class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]

# API Endpoints

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Process a query and return response with sources"""
    try:
        logger.info(f"Received query: {request.query[:50]}...")

        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = rag_system.session_manager.create_session()
            logger.debug(f"Created new session: {session_id}")

        # Process query using RAG system
        answer, sources = rag_system.query(request.query, session_id)

        # Convert source dictionaries to SourceLink objects
        source_links = [SourceLink(**source) for source in sources]

        logger.info(f"Query processed successfully, {len(source_links)} sources")
        return QueryResponse(
            answer=answer,
            sources=source_links,
            session_id=session_id
        )
    except ValueError as e:
        # Known errors with good error messages (from ai_generator)
        logger.error(f"Query failed with known error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Unexpected errors - log with full traceback
        logger.exception(f"Query failed with unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {type(e).__name__}: {str(e)}"
        )

@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    """Get course analytics and statistics"""
    try:
        analytics = rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Load initial documents and validate configuration on startup"""
    # Validate API key
    if not config.ANTHROPIC_API_KEY:
        logger.error("CRITICAL: ANTHROPIC_API_KEY not set in environment")
        print("=" * 60)
        print("ERROR: ANTHROPIC_API_KEY not configured in .env file")
        print("Please add your Anthropic API key to .env file:")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        print("=" * 60)
    elif not config.ANTHROPIC_API_KEY.startswith("sk-ant-"):
        logger.warning(f"API key has unexpected format: {config.ANTHROPIC_API_KEY[:20]}...")
        print("=" * 60)
        print("WARNING: ANTHROPIC_API_KEY does not start with 'sk-ant-'")
        print(f"Current value: {config.ANTHROPIC_API_KEY[:30]}...")
        print("This may be a placeholder. Get a valid key from:")
        print("  https://console.anthropic.com/")
        print("=" * 60)
    else:
        logger.info("API key format looks valid")
        print(f"✓ Anthropic API key configured: {config.ANTHROPIC_API_KEY[:15]}...")

    # Load documents
    docs_path = "../docs"
    if os.path.exists(docs_path):
        print("Loading initial documents...")
        try:
            courses, chunks = rag_system.add_course_folder(docs_path, clear_existing=False)
            print(f"Loaded {courses} courses with {chunks} chunks")
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            print(f"Error loading documents: {e}")

    # Check ChromaDB data
    try:
        stats = rag_system.get_course_analytics()
        print(f"✓ Vector store: {stats['total_courses']} courses, {len(stats['course_titles'])} total")
        if stats['total_courses'] == 0:
            logger.warning("No courses in vector store")
            print("WARNING: No courses loaded in vector store")
            print("  Add course documents to ../docs/ and restart")
        else:
            print(f"  Courses: {', '.join(stats['course_titles'][:3])}...")
    except Exception as e:
        logger.error(f"Error checking vector store: {e}")
        print(f"Error checking vector store: {e}")

# Custom static file handler with no-cache headers for development
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path


class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            # Add no-cache headers for development
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    
    
# Serve static files for the frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")