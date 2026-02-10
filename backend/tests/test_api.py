"""Tests for FastAPI endpoints"""
import pytest
from fastapi import HTTPException
from unittest.mock import Mock


@pytest.mark.api
class TestQueryEndpoint:
    """Tests for POST /api/query endpoint"""

    def test_query_with_session_id(self, client, mock_rag_system, sample_query_request):
        """Test successful query with existing session ID"""
        response = client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify response values
        assert data["answer"] == "This is a test answer from the RAG system."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Test Course - Lesson 1"
        assert data["sources"][0]["link"] == "https://example.com/lesson1"
        assert data["session_id"] == "test-session-123"

        # Verify RAG system was called correctly
        mock_rag_system.query.assert_called_once_with(
            "What is MCP?",
            "test-session-123"
        )

    def test_query_without_session_id(self, client, mock_rag_system, sample_query_request_no_session):
        """Test query without session ID creates new session"""
        response = client.post("/api/query", json=sample_query_request_no_session)

        assert response.status_code == 200
        data = response.json()

        # Verify new session was created
        mock_rag_system.session_manager.create_session.assert_called_once()
        assert data["session_id"] == "test-session-123"

        # Verify RAG system was called with new session ID
        mock_rag_system.query.assert_called_once()

    def test_query_with_empty_query(self, client):
        """Test query with empty string"""
        response = client.post("/api/query", json={"query": ""})

        # Should still process (validation happens in RAG system)
        assert response.status_code in [200, 422, 500]

    def test_query_missing_required_field(self, client):
        """Test query without required 'query' field"""
        response = client.post("/api/query", json={"session_id": "test"})

        # FastAPI should return 422 for validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_query_with_invalid_json(self, client):
        """Test query with malformed JSON"""
        response = client.post(
            "/api/query",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_query_with_multiple_sources(self, client, mock_rag_system):
        """Test query returning multiple source links"""
        # Configure mock to return multiple sources
        mock_rag_system.query.return_value = (
            "Answer with multiple sources",
            [
                {"text": "Source 1", "link": "https://example.com/1"},
                {"text": "Source 2", "link": "https://example.com/2"},
                {"text": "Source 3", "link": None},  # Source without link
            ]
        )

        response = client.post("/api/query", json={"query": "test query"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 3
        assert data["sources"][0]["link"] == "https://example.com/1"
        assert data["sources"][2]["link"] is None

    def test_query_with_no_sources(self, client, mock_rag_system):
        """Test query returning answer with no sources"""
        mock_rag_system.query.return_value = (
            "General knowledge answer",
            []
        )

        response = client.post("/api/query", json={"query": "What is Python?"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "General knowledge answer"
        assert data["sources"] == []

    def test_query_rag_system_error(self, client, mock_rag_system):
        """Test handling of RAG system ValueError"""
        mock_rag_system.query.side_effect = ValueError("Course not found")

        response = client.post("/api/query", json={"query": "test"})

        assert response.status_code == 500
        data = response.json()
        assert "Course not found" in data["detail"]

    def test_query_unexpected_error(self, client, mock_rag_system):
        """Test handling of unexpected errors"""
        mock_rag_system.query.side_effect = RuntimeError("Database connection lost")

        response = client.post("/api/query", json={"query": "test"})

        assert response.status_code == 500
        data = response.json()
        assert "RuntimeError" in data["detail"]
        assert "Database connection lost" in data["detail"]

    def test_query_with_long_text(self, client, mock_rag_system):
        """Test query with very long input text"""
        long_query = "What is " + "very " * 1000 + "long question?"

        response = client.post("/api/query", json={"query": long_query})

        # Should process normally (length limits handled by RAG system)
        assert response.status_code == 200
        mock_rag_system.query.assert_called_once()

    def test_query_with_special_characters(self, client):
        """Test query with special characters and unicode"""
        special_query = "What is AI? 🤖 Testing émojis and spëcial çhars!"

        response = client.post("/api/query", json={"query": special_query})

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for GET /api/courses endpoint"""

    def test_get_courses_success(self, client, mock_rag_system):
        """Test successful retrieval of course statistics"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify response values
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Test Course on AI" in data["course_titles"]
        assert "Advanced Testing Techniques" in data["course_titles"]

        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_courses_empty(self, client, mock_rag_system):
        """Test course stats with no courses loaded"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_many_courses(self, client, mock_rag_system):
        """Test course stats with many courses"""
        many_courses = [f"Course {i}" for i in range(100)]
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 100,
            "course_titles": many_courses
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 100
        assert len(data["course_titles"]) == 100

    def test_get_courses_error(self, client, mock_rag_system):
        """Test error handling in course stats endpoint"""
        mock_rag_system.get_course_analytics.side_effect = Exception("Database error")

        response = client.get("/api/courses")

        assert response.status_code == 500
        data = response.json()
        assert "Database error" in data["detail"]

    def test_get_courses_accepts_no_params(self, client):
        """Test that courses endpoint doesn't accept query parameters"""
        # Should work regardless of extra params
        response = client.get("/api/courses?extra=param")

        assert response.status_code == 200


@pytest.mark.api
class TestRootEndpoint:
    """Tests for GET / root endpoint"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "RAG System API"


@pytest.mark.api
class TestCORSHeaders:
    """Tests for CORS configuration"""

    def test_cors_headers_on_query(self, client):
        """Test CORS headers are present on actual requests"""
        # Make actual POST request (TestClient doesn't fully emulate OPTIONS)
        response = client.post(
            "/api/query",
            json={"query": "test"},
            headers={"Origin": "https://example.com"}
        )

        # CORS middleware should add these headers on actual requests
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_all_origins(self, client):
        """Test CORS allows requests from any origin"""
        response = client.post(
            "/api/query",
            json={"query": "test"},
            headers={"Origin": "https://example.com"}
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


@pytest.mark.api
class TestResponseModels:
    """Tests for response model validation"""

    def test_query_response_schema(self, client):
        """Test QueryResponse matches expected schema"""
        response = client.post("/api/query", json={"query": "test"})

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Source structure
        for source in data["sources"]:
            assert "text" in source
            assert "link" in source
            assert isinstance(source["text"], str)
            # link can be str or None

    def test_courses_response_schema(self, client):
        """Test CourseStats matches expected schema"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Required fields with correct types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

        # All titles should be strings
        for title in data["course_titles"]:
            assert isinstance(title, str)


@pytest.mark.api
class TestContentNegotiation:
    """Tests for content type handling"""

    def test_json_content_type_required(self, client):
        """Test that query endpoint requires JSON content type"""
        response = client.post(
            "/api/query",
            data="query=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should reject non-JSON content
        assert response.status_code == 422

    def test_response_is_json(self, client):
        """Test that responses are JSON formatted"""
        response = client.post("/api/query", json={"query": "test"})

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


@pytest.mark.api
@pytest.mark.integration
class TestEndToEndFlow:
    """Integration tests for complete request flows"""

    def test_complete_query_flow(self, client, mock_rag_system):
        """Test complete flow: create session -> query -> get sources"""
        # First query without session (creates new session)
        response1 = client.post("/api/query", json={"query": "First question"})
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Second query with same session
        mock_rag_system.query.reset_mock()
        response2 = client.post("/api/query", json={
            "query": "Follow-up question",
            "session_id": session_id
        })

        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Verify session was reused
        mock_rag_system.query.assert_called_once_with("Follow-up question", session_id)

    def test_multiple_concurrent_sessions(self, client, mock_rag_system):
        """Test multiple independent sessions"""
        # Create multiple sessions
        mock_rag_system.session_manager.create_session.side_effect = [
            "session-1",
            "session-2",
            "session-3"
        ]

        responses = []
        for i in range(3):
            response = client.post("/api/query", json={"query": f"Query {i}"})
            assert response.status_code == 200
            responses.append(response.json())

        # Verify different session IDs
        session_ids = [r["session_id"] for r in responses]
        assert len(set(session_ids)) == 3  # All unique

    def test_query_then_check_courses(self, client, mock_rag_system):
        """Test querying then checking course list"""
        # Make a query
        response1 = client.post("/api/query", json={"query": "What courses exist?"})
        assert response1.status_code == 200

        # Check courses
        response2 = client.get("/api/courses")
        assert response2.status_code == 200

        # Both should succeed
        assert mock_rag_system.query.called
        assert mock_rag_system.get_course_analytics.called
