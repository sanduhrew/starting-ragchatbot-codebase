"""Shared pytest fixtures for all tests"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from config import Config
from vector_store import VectorStore, SearchResults
from models import Course, Lesson, CourseChunk
from rag_system import RAGSystem
from session_manager import SessionManager


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    config = Mock(spec=Config)
    config.ANTHROPIC_API_KEY = "sk-ant-test-key-12345"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    return config


@pytest.fixture
def test_vector_store():
    """Create temporary VectorStore for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(
            chroma_path=tmpdir,
            embedding_model="all-MiniLM-L6-v2",
            max_results=5
        )
        yield store


@pytest.fixture
def sample_course():
    """Create sample course for testing"""
    return Course(
        title="Test Course on AI",
        course_link="https://example.com/course",
        instructor="Dr. Test Instructor",
        lessons=[
            Lesson(
                lesson_number=1,
                title="Introduction to Testing",
                lesson_link="https://example.com/lesson1"
            ),
            Lesson(
                lesson_number=2,
                title="Advanced Testing Techniques",
                lesson_link="https://example.com/lesson2"
            )
        ]
    )


@pytest.fixture
def sample_chunks(sample_course):
    """Create sample course chunks"""
    return [
        CourseChunk(
            content="This is lesson 1 content about unit testing and test-driven development.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="This is lesson 2 content about integration testing and mocking techniques.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=0
        )
    ]


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    mock_client = Mock()

    # Default response without tool use
    mock_response = Mock()
    mock_response.content = [Mock(type="text", text="This is a test response from Claude.")]
    mock_response.stop_reason = "end_turn"
    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_search_results():
    """Create mock search results"""
    return SearchResults(
        documents=["Sample course content about testing methodologies."],
        metadata=[{
            "course_title": "Test Course on AI",
            "lesson_number": 1,
            "chunk_index": 0
        }],
        distances=[0.5]
    )


@pytest.fixture
def mock_rag_system():
    """Mock RAG system for API testing"""
    rag = Mock(spec=RAGSystem)
    rag.session_manager = Mock(spec=SessionManager)
    rag.session_manager.create_session.return_value = "test-session-123"

    # Default query response
    rag.query.return_value = (
        "This is a test answer from the RAG system.",
        [{"text": "Test Course - Lesson 1", "link": "https://example.com/lesson1"}]
    )

    # Default analytics response
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course on AI", "Advanced Testing Techniques"]
    }

    return rag


@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI app without static file mounting"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional

    # Create fresh app instance for testing
    app = FastAPI(title="Test RAG System")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pydantic models (matching app.py)
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class SourceLink(BaseModel):
        text: str
        link: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[SourceLink]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # Define endpoints using the mock RAG system
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)
            source_links = [SourceLink(**source) for source in sources]

            return QueryResponse(
                answer=answer,
                sources=source_links,
                session_id=session_id
            )
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Query processing failed: {type(e).__name__}: {str(e)}"
            )

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"message": "RAG System API"}

    return app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


@pytest.fixture
def sample_query_request():
    """Sample query request payload"""
    return {
        "query": "What is MCP?",
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_query_request_no_session():
    """Sample query request without session ID"""
    return {
        "query": "What is MCP?"
    }
