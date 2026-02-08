"""Shared pytest fixtures for all tests"""
import pytest
from unittest.mock import Mock, MagicMock
import tempfile
import os
from config import Config
from vector_store import VectorStore, SearchResults
from models import Course, Lesson, CourseChunk


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
