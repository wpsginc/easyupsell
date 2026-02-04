import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigquery_client import BigQueryClient

@pytest.fixture
def mock_bq_client():
    with patch("bigquery_client.bigquery.Client") as mock_client:
        yield mock_client

def test_init(mock_bq_client):
    """Test initialization of BigQueryClient."""
    client = BigQueryClient(project_id="test-project")
    mock_bq_client.assert_called_with(project="test-project")
    assert client.client == mock_bq_client.return_value

def test_run_query(mock_bq_client):
    """Test executing a query and returning a DataFrame."""
    # Setup mock response
    mock_query_job = Mock()
    mock_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    mock_query_job.to_dataframe.return_value = mock_df
    
    mock_bq_client.return_value.query.return_value = mock_query_job
    
    # Initialize client
    client = BigQueryClient(project_id="test-project")
    
    # Run query
    sql = "SELECT * FROM table"
    result = client.run_query(sql)
    
    # Verify calls
    mock_bq_client.return_value.query.assert_called_with(sql)
    mock_query_job.to_dataframe.assert_called_once()
    
    # Verify result
    pd.testing.assert_frame_equal(result, mock_df)

def test_extract_netsuite_id_static_method():
    """Test the static helper method for parsing BPN."""
    # Valid BPN
    assert BigQueryClient.extract_netsuite_id("12345, ABC") == "12345"
    assert BigQueryClient.extract_netsuite_id("99999") == "99999"
    
    # Empty/None
    # Note: These currently return None but don't log. 
    # The new implementation will log a warning.
    assert BigQueryClient.extract_netsuite_id("") is None
    assert BigQueryClient.extract_netsuite_id(None) is None
    
    # Whitespace
    assert BigQueryClient.extract_netsuite_id(" 5555 , XYZ") == "5555"

def test_extract_netsuite_id_logging(caplog):
    """Test that missing or malformed NetSuite IDs log a WARNING."""
    import logging
    
    # Missing/Empty
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert BigQueryClient.extract_netsuite_id("") is None
        assert "NetSuite ID missing" in caplog.text
    
    # Null
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert BigQueryClient.extract_netsuite_id(None) is None
        assert "NetSuite ID missing" in caplog.text

    # Malformed (empty extraction)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        # This case is tricky with current logic: ", ABC" would split to ""
        assert BigQueryClient.extract_netsuite_id(", ABC") is None
        assert "extraction failed" in caplog.text
