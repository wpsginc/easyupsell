# SDD: End-to-End User Workflow Testing

## 1. Gap Description
The complete user workflow described in README.md (config → analyze → review → export) has ZERO integration testing. Each command is tested in isolation, but the data flow between commands is untested.

**Critical risk:** Commands may work individually but fail when chained together in real usage.

**Severity:** P0 - CRITICAL  
**Impact:** Users cannot complete the documented workflow; data loss between steps

## 2. Target Location
**Test file:** `tests/integration/test_e2e_workflow.py` (create new)  
**Source under test:** Full CLI pipeline (`easyupsell.cli`, all command modules)

## 3. Test Strategy

### 3.1 Real User Journey Simulation
Simulate a real user following the README quick start:
1. User sets up environment (`.env` file)
2. User runs `easyupsell config` to validate credentials
3. User runs `easyupsell analyze` to generate recommendations
4. User runs `easyupsell review` to approve/reject pairings
5. User runs `easyupsell export` to export final CSV

### 3.2 Data Continuity Validation
Verify data flows correctly between steps:
- Config step → writes validated credentials
- Analyze step → reads credentials, writes `data/recommendations.csv`
- Review step → reads `data/recommendations.csv`, writes `data/reviewed_recommendations.csv`
- Export step → reads reviewed data, writes final output

### 3.3 Failure Recovery Testing
Test what happens when:
- Analyze crashes mid-run (50% complete)
- User runs analyze --resume
- Review file is deleted between steps
- Network fails during analyze

## 4. Implementation Details

### 4.1 Test Structure
```python
# tests/integration/test_e2e_workflow.py
import pytest
import subprocess
import tempfile
import os
from pathlib import Path
import csv
import shutil

@pytest.fixture
def temp_workspace(tmp_path):
    """Create isolated workspace for E2E tests"""
    workspace = tmp_path / "easyupsell_test"
    workspace.mkdir()
    
    # Create data directory
    (workspace / "data").mkdir()
    
    # Create minimal .env file (with test credentials)
    env_file = workspace / ".env"
    env_file.write_text("""
BC_STORE_HASH=test_store_hash_12345
BC_ACCESS_TOKEN=test_token_67890
OPENAI_API_KEY=sk-test-key-not-real
AZURE_OPENAI_API_KEY=test_azure_key
AZURE_OPENAI_API_BASE=https://test.openai.azure.com
BQ_PROJECT_ID=test-project-123
""")
    
    # Set working directory
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    yield workspace
    
    # Cleanup
    os.chdir(original_cwd)


class TestE2EHappyPath:
    """Test complete user journey with no errors"""
    
    def test_full_workflow_config_to_export(self, temp_workspace):
        """
        Complete workflow: config → analyze → review → export
        
        This is the EXACT workflow from README.md Quick Start
        """
        # Step 1: Config validation
        result = subprocess.run(
            ["easyupsell", "config", "test"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Config failed: {result.stderr}"
        assert "BigCommerce connection" in result.stdout
        
        # Step 2: Run analysis (with mocked API calls)
        # Note: This test needs mock BigCommerce + BigQuery + LLM
        # For initial test, use --skip-orders flag to skip BQ
        result = subprocess.run(
            ["easyupsell", "analyze", "--limit", "5", "--skip-orders"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        assert result.returncode == 0, f"Analyze failed: {result.stderr}"
        
        # Verify output file exists
        recommendations_file = temp_workspace / "data" / "recommendations.csv"
        assert recommendations_file.exists(), "Analyze did not create recommendations.csv"
        
        # Verify CSV format
        with open(recommendations_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) > 0, "Recommendations file is empty"
            
            # Check required columns
            required_cols = ["source_category", "target_category", "weight", "llm_valid"]
            for col in required_cols:
                assert col in reader.fieldnames, f"Missing column: {col}"
        
        # Step 3: Review recommendations (auto-approve all for test)
        # This would normally be interactive, use --auto-approve flag
        result = subprocess.run(
            ["easyupsell", "review", "--auto-approve"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Review failed: {result.stderr}"
        
        # Verify reviewed file exists
        reviewed_file = temp_workspace / "data" / "reviewed_recommendations.csv"
        assert reviewed_file.exists(), "Review did not create reviewed file"
        
        # Step 4: Export to final format
        export_file = temp_workspace / "data" / "final_export.csv"
        result = subprocess.run(
            ["easyupsell", "export", "--output", str(export_file), "--format", "csv"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Export failed: {result.stderr}"
        assert export_file.exists(), "Export did not create output file"
        
        # Verify final CSV is valid
        with open(export_file) as f:
            reader = csv.DictReader(f)
            final_rows = list(reader)
            assert len(final_rows) > 0, "Final export is empty"
            
            # Verify only approved recommendations are exported
            assert all(row.get("status") == "approved" for row in final_rows)


class TestE2EDataContinuity:
    """Test data integrity between pipeline steps"""
    
    def test_analyze_to_review_data_match(self, temp_workspace):
        """Data from analyze step matches review step input"""
        # Run analyze
        subprocess.run(
            ["easyupsell", "analyze", "--limit", "3", "--skip-orders"],
            capture_output=True,
            timeout=180
        )
        
        # Read raw recommendations
        raw_file = temp_workspace / "data" / "recommendations.csv"
        with open(raw_file) as f:
            raw_data = list(csv.DictReader(f))
        
        # Simulate review (approve first 2, reject rest)
        # In real test, would invoke review command with scripted input
        # For now, manually create reviewed file
        reviewed_file = temp_workspace / "data" / "reviewed_recommendations.csv"
        with open(reviewed_file, "w", newline="") as f:
            fieldnames = list(raw_data[0].keys()) + ["status", "review_note"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, row in enumerate(raw_data):
                row["status"] = "approved" if i < 2 else "rejected"
                row["review_note"] = "" if i < 2 else "Not relevant"
                writer.writerow(row)
        
        # Verify export only includes approved
        export_file = temp_workspace / "data" / "export.csv"
        subprocess.run(
            ["easyupsell", "export", "--output", str(export_file)],
            capture_output=True
        )
        
        with open(export_file) as f:
            exported = list(csv.DictReader(f))
        
        # Should only have 2 approved items
        assert len(exported) == 2, f"Expected 2 approved, got {len(exported)}"
    
    def test_category_ids_preserved_across_steps(self, temp_workspace):
        """Category IDs remain consistent through pipeline"""
        # Run analyze with known test data
        subprocess.run(
            ["easyupsell", "analyze", "--category", "Tactical Pants", "--skip-orders"],
            capture_output=True,
            timeout=180
        )
        
        # Extract category IDs from analyze output
        raw_file = temp_workspace / "data" / "recommendations.csv"
        with open(raw_file) as f:
            analyze_data = list(csv.DictReader(f))
        
        source_cats = {row["source_category"] for row in analyze_data}
        target_cats = {row["target_category"] for row in analyze_data}
        
        # Run review (auto-approve)
        subprocess.run(
            ["easyupsell", "review", "--auto-approve"],
            capture_output=True
        )
        
        # Check reviewed file has same categories
        reviewed_file = temp_workspace / "data" / "reviewed_recommendations.csv"
        with open(reviewed_file) as f:
            review_data = list(csv.DictReader(f))
        
        review_source_cats = {row["source_category"] for row in review_data}
        review_target_cats = {row["target_category"] for row in review_data}
        
        assert source_cats == review_source_cats, "Source categories changed"
        assert target_cats == review_target_cats, "Target categories changed"


class TestE2EErrorRecovery:
    """Test failure scenarios and recovery"""
    
    def test_analyze_resume_after_interrupt(self, temp_workspace):
        """Resume analysis after interruption"""
        # Start analysis
        proc = subprocess.Popen(
            ["easyupsell", "analyze", "--limit", "100"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Let it run for 5 seconds then kill
        import time
        time.sleep(5)
        proc.terminate()
        proc.wait(timeout=10)
        
        # Check if checkpoint file exists
        checkpoint_file = temp_workspace / "data" / ".analyze_checkpoint.json"
        if checkpoint_file.exists():
            # Resume from checkpoint
            result = subprocess.run(
                ["easyupsell", "analyze", "--resume"],
                capture_output=True,
                text=True,
                timeout=300
            )
            assert result.returncode == 0, "Resume failed"
            assert "Resumed from checkpoint" in result.stdout
        else:
            pytest.skip("Checkpoint not implemented yet")
    
    def test_review_with_missing_input_file(self, temp_workspace):
        """Review command handles missing input gracefully"""
        # Try to review without running analyze first
        result = subprocess.run(
            ["easyupsell", "review"],
            capture_output=True,
            text=True
        )
        
        # Should fail with helpful error message
        assert result.returncode != 0
        assert "recommendations.csv not found" in result.stderr.lower() or \
               "run analyze first" in result.stderr.lower()
    
    def test_export_with_no_approved_recommendations(self, temp_workspace):
        """Export handles case where all recommendations are rejected"""
        # Create reviewed file with all rejected
        reviewed_file = temp_workspace / "data" / "reviewed_recommendations.csv"
        with open(reviewed_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["source_category", "target_category", "status"])
            writer.writeheader()
            writer.writerow({
                "source_category": "Cat A",
                "target_category": "Cat B",
                "status": "rejected"
            })
        
        # Try to export
        export_file = temp_workspace / "data" / "export.csv"
        result = subprocess.run(
            ["easyupsell", "export", "--output", str(export_file)],
            capture_output=True,
            text=True
        )
        
        # Should succeed but warn about empty export
        assert result.returncode == 0
        assert "0 recommendations" in result.stdout or "no approved" in result.stdout.lower()


class TestE2ENetworkFailures:
    """Test network failure handling"""
    
    @pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="Requires network mocking setup"
    )
    def test_bigcommerce_timeout_during_analyze(self, temp_workspace, monkeypatch):
        """Analyze handles BigCommerce API timeout"""
        # Mock BigCommerce client to simulate timeout
        def mock_timeout(*args, **kwargs):
            import requests
            raise requests.exceptions.Timeout("Connection timed out")
        
        monkeypatch.setattr("src.bigcommerce.client.BigCommerceClient._get", mock_timeout)
        
        result = subprocess.run(
            ["easyupsell", "analyze", "--limit", "5"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Should fail gracefully with clear error
        assert result.returncode != 0
        assert "timeout" in result.stderr.lower() or "connection" in result.stderr.lower()
    
    @pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="Requires LLM mocking setup"
    )
    def test_llm_failure_during_analyze(self, temp_workspace):
        """Analyze handles LLM API failure"""
        # Set invalid LLM credentials
        env_file = temp_workspace / ".env"
        env_content = env_file.read_text()
        env_content += "\nOPENAI_API_KEY=sk-invalid-key-will-fail\n"
        env_file.write_text(env_content)
        
        result = subprocess.run(
            ["easyupsell", "analyze", "--limit", "5", "--skip-orders"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Should either:
        # 1. Fail with clear error about invalid API key
        # 2. Fall back to non-LLM mode (if implemented)
        assert result.returncode != 0 or "fallback" in result.stdout.lower()


class TestE2EPerformance:
    """Test performance characteristics of full pipeline"""
    
    @pytest.mark.slow
    def test_analyze_completes_within_time_limit(self, temp_workspace):
        """Analyze with 100 categories completes in reasonable time"""
        import time
        
        start = time.time()
        result = subprocess.run(
            ["easyupsell", "analyze", "--limit", "100", "--skip-orders"],
            capture_output=True,
            timeout=600  # 10 minute max
        )
        elapsed = time.time() - start
        
        assert result.returncode == 0
        assert elapsed < 300, f"Analyze took {elapsed}s, should be <5 minutes"
    
    @pytest.mark.slow
    def test_memory_usage_reasonable(self, temp_workspace):
        """Pipeline doesn't consume excessive memory"""
        # Would need psutil or similar to measure memory
        # For now, just verify no OOM errors
        result = subprocess.run(
            ["easyupsell", "analyze", "--limit", "1000", "--skip-orders"],
            capture_output=True,
            timeout=1200
        )
        
        assert "MemoryError" not in result.stderr
        assert "out of memory" not in result.stderr.lower()
```

### 4.2 Mock Strategy
For isolated E2E tests, use mocks for external services:

1. **BigCommerce API:** Use `responses` library to mock HTTP calls
2. **BigQuery:** Use `google-cloud-bigquery` test fixtures
3. **LLM APIs:** Mock OpenAI/Azure responses with pre-canned JSON

For TRUE integration tests, use:
- Real BigCommerce sandbox account
- Real BigQuery test dataset
- Real LLM with test API key (monitor costs!)

### 4.3 Test Data
Create fixtures in `tests/fixtures/e2e_data/`:
- `sample_products.json` — 100 test products
- `sample_categories.json` — 20 test categories
- `sample_orders.json` — 500 test orders
- `expected_recommendations.csv` — Known-good output for validation

### 4.4 CI/CD Integration
```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install package
        run: pip install -e .
      - name: Run E2E tests
        env:
          RUN_INTEGRATION_TESTS: "1"
        run: pytest tests/integration/test_e2e_workflow.py -v -m "not slow"
```

## 5. Recommended Executor
**Demon:** rem_uat  
**Reason:** End-to-end testing requires simulating real user interactions with CLI

**Alternative:** rem_testing can handle if UAT demon unavailable

## 6. Dependencies
- pytest
- responses (for HTTP mocking)
- pytest-timeout (for long-running test timeouts)
- pytest-subprocess (for CLI subprocess mocking)

## 7. Estimated Effort
**Test Implementation:** 8-12 hours  
**Mock setup:** 4-6 hours  
**CI/CD integration:** 2-4 hours  
**Total:** ~2-3 days

## 8. Success Criteria
- ✅ Complete workflow (config → analyze → review → export) passes
- ✅ Data integrity verified between steps
- ✅ Error recovery paths tested (resume, missing files)
- ✅ Network failure handling validated
- ✅ Performance benchmarks established (<5 min for 100 categories)

## 9. Known Limitations
- Cannot test interactive TUI review without Playwright/terminal emulation
- LLM responses are non-deterministic (use temperature=0 for testing)
- BigQuery may have quota limits in CI (use mocks for frequent runs)

## 10. Follow-up SDDs
After this SDD is complete, consider:
- **SDD-UAT-TUIReview** — Test interactive review terminal UI
- **SDD-UAT-ErrorMessages** — Validate user-facing error message quality
- **SDD-Performance-LargeScale** — Benchmark with 10k+ products
