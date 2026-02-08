"""Diagnostic tests to identify system failures"""
import pytest
import os
from pathlib import Path
import anthropic
from config import Config
from vector_store import VectorStore
from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool
from sentence_transformers import SentenceTransformer


def test_anthropic_api_key_exists():
    """Test that ANTHROPIC_API_KEY is set in environment"""
    print("\n=== Checking for ANTHROPIC_API_KEY ===")

    # Check .env file exists
    env_path = Path("/Users/san/cc/starting-ragchatbot-codebase/.env")
    if env_path.exists():
        print(f"✓ .env file found at {env_path}")
        with open(env_path) as f:
            env_contents = f.read()
            if "ANTHROPIC_API_KEY" in env_contents:
                print("✓ ANTHROPIC_API_KEY found in .env file")
            else:
                pytest.fail("✗ ANTHROPIC_API_KEY not found in .env file")
    else:
        print(f"✗ .env file not found at {env_path}")

    # Check if loaded in config
    config = Config()
    if config.ANTHROPIC_API_KEY:
        print(f"✓ API key loaded: {config.ANTHROPIC_API_KEY[:15]}..." if len(config.ANTHROPIC_API_KEY) > 15 else "✓ API key loaded (short key)")
        assert config.ANTHROPIC_API_KEY, "API key is empty"
    else:
        pytest.fail("✗ ANTHROPIC_API_KEY not loaded in Config")


def test_anthropic_api_key_valid():
    """Test that ANTHROPIC_API_KEY can authenticate with Anthropic API"""
    print("\n=== Validating ANTHROPIC_API_KEY with Anthropic API ===")

    config = Config()

    # Check key format
    if not config.ANTHROPIC_API_KEY:
        pytest.skip("API key not set, skipping validation test")

    if not config.ANTHROPIC_API_KEY.startswith("sk-ant-"):
        print(f"⚠ API key has unexpected format: {config.ANTHROPIC_API_KEY[:10]}...")
        print("  Expected format: sk-ant-...")

    # Attempt real API call
    try:
        print("Making test API call to Anthropic...")
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )
        print(f"✓ API call successful")
        print(f"  Model: {response.model}")
        print(f"  Response: {response.content[0].text[:50] if response.content else 'empty'}")
        assert response is not None

    except anthropic.AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        pytest.fail(f"API key is invalid: {e}")
    except anthropic.APIError as e:
        print(f"✗ API error: {e}")
        pytest.fail(f"API call failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}")
        pytest.fail(f"Unexpected error during API call: {e}")


def test_chromadb_collections_exist():
    """Test that ChromaDB collections are created and accessible"""
    print("\n=== Checking ChromaDB Collections ===")

    config = Config()
    chroma_path = Path(__file__).parent.parent / "chroma_db"

    if not chroma_path.exists():
        print(f"✗ ChromaDB directory not found: {chroma_path}")
        pytest.fail("ChromaDB directory does not exist")

    print(f"✓ ChromaDB directory exists: {chroma_path}")

    try:
        store = VectorStore(
            chroma_path=str(chroma_path),
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )
        print("✓ VectorStore initialized successfully")

        # Check collections exist
        assert store.course_catalog is not None, "course_catalog collection is None"
        print("✓ course_catalog collection exists")

        assert store.course_content is not None, "course_content collection is None"
        print("✓ course_content collection exists")

    except Exception as e:
        print(f"✗ Error initializing VectorStore: {e}")
        pytest.fail(f"Failed to initialize VectorStore: {e}")


def test_chromadb_has_data():
    """Test that ChromaDB collections contain course data"""
    print("\n=== Checking ChromaDB Data ===")

    config = Config()
    chroma_path = Path(__file__).parent.parent / "chroma_db"

    try:
        store = VectorStore(
            chroma_path=str(chroma_path),
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )

        # Check course_catalog count
        catalog_result = store.course_catalog.get()
        catalog_count = len(catalog_result['ids']) if catalog_result['ids'] else 0
        print(f"  course_catalog: {catalog_count} documents")

        if catalog_count > 0:
            print(f"  Courses: {catalog_result['ids'][:5]}")  # Show first 5
        else:
            print("  ⚠ No courses in catalog")

        # Check course_content count
        content_result = store.course_content.get()
        content_count = len(content_result['ids']) if content_result['ids'] else 0
        print(f"  course_content: {content_count} chunks")

        if content_count == 0:
            print("  ✗ No content chunks found")
            pytest.fail("ChromaDB has no course content. Run the app to load documents first.")
        else:
            print(f"  ✓ {content_count} content chunks found")

        assert catalog_count > 0, "No courses in catalog"
        assert content_count > 0, "No content chunks"

    except Exception as e:
        print(f"✗ Error checking ChromaDB data: {e}")
        pytest.fail(f"Failed to check ChromaDB data: {e}")


def test_vector_store_can_query():
    """Test that VectorStore can execute queries without exceptions"""
    print("\n=== Testing VectorStore Query Execution ===")

    config = Config()
    chroma_path = Path(__file__).parent.parent / "chroma_db"

    try:
        store = VectorStore(
            chroma_path=str(chroma_path),
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )

        # Test basic query
        print("Testing basic search...")
        results = store.search(query="What is MCP?")

        if results.error:
            print(f"✗ Search returned error: {results.error}")
            pytest.fail(f"Search query failed: {results.error}")

        print(f"✓ Basic search successful: {len(results.documents)} results")

        # Test query with course filter
        print("Testing search with course filter...")
        results_filtered = store.search(query="introduction", course_name="MCP")

        if results_filtered.error:
            print(f"✗ Filtered search returned error: {results_filtered.error}")
        else:
            print(f"✓ Filtered search successful: {len(results_filtered.documents)} results")

        assert not results.error, f"Search failed with error: {results.error}"

    except Exception as e:
        print(f"✗ Exception during search: {type(e).__name__}: {e}")
        pytest.fail(f"VectorStore query failed with exception: {e}")


def test_tools_registered():
    """Test that ToolManager has tools registered correctly"""
    print("\n=== Checking Tool Registration ===")

    config = Config()
    chroma_path = Path(__file__).parent.parent / "chroma_db"

    try:
        store = VectorStore(
            chroma_path=str(chroma_path),
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(store)
        outline_tool = CourseOutlineTool(store)

        tool_manager.register_tool(search_tool)
        tool_manager.register_tool(outline_tool)

        print(f"✓ Registered {len(tool_manager.tools)} tools")

        # Get tool definitions
        definitions = tool_manager.get_tool_definitions()
        print(f"✓ Tool definitions generated: {len(definitions)} tools")

        for tool_def in definitions:
            print(f"  - {tool_def['name']}: {tool_def['description'][:60]}...")

        assert len(definitions) == 2, f"Expected 2 tools, got {len(definitions)}"
        assert definitions[0]['name'] == 'search_course_content'
        assert definitions[1]['name'] == 'get_course_outline'

        print("✓ All tools registered correctly")

    except Exception as e:
        print(f"✗ Error with tool registration: {e}")
        pytest.fail(f"Tool registration failed: {e}")


def test_embedding_model_loads():
    """Test that SentenceTransformer embedding model loads"""
    print("\n=== Testing Embedding Model ===")

    config = Config()

    try:
        print(f"Loading embedding model: {config.EMBEDDING_MODEL}")
        model = SentenceTransformer(config.EMBEDDING_MODEL)
        print("✓ Embedding model loaded successfully")

        # Test embedding generation
        test_text = "This is a test sentence for embedding generation."
        embedding = model.encode([test_text])[0]
        print(f"✓ Generated embedding: shape={embedding.shape}, dtype={embedding.dtype}")

        assert len(embedding) > 0, "Embedding is empty"
        print(f"✓ Embedding dimension: {len(embedding)}")

    except Exception as e:
        print(f"✗ Error loading embedding model: {e}")
        pytest.fail(f"Failed to load embedding model: {e}")
