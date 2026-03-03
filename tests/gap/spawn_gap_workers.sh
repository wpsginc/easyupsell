#!/bin/bash
echo "Spawning worker for G3: CSV Injection Mitigation..."
gemini -y -p "You are a test implementation worker. Read the SDD at 'tests/gap/SDDs/SDD-Security-CSV-Sanitization.md'. Implement the test exactly as described. Write the code to the target location specified in the SDD. Do not change the SDD." &

echo "Spawning worker for G4: Database Path Restriction..."
gemini -y -p "You are a test implementation worker. Read the SDD at 'tests/gap/SDDs/SDD-Security-Path-Restriction.md'. Implement the test exactly as described. Write the code to the target location specified in the SDD. Do not change the SDD." &

echo "Spawning worker for G5: Bulk Migration Performance..."
gemini -y -p "You are a test implementation worker. Read the SDD at 'tests/gap/SDDs/SDD-Performance-Bulk-Migration.md'. Implement the test exactly as described. Write the code to the target location specified in the SDD. Do not change the SDD." &

echo "Spawning worker for G6: Malformed CSV Robustness..."
gemini -y -p "You are a test implementation worker. Read the SDD at 'tests/gap/SDDs/SDD-Robustness-Malformed-CSV.md'. Implement the test exactly as described. Write the code to the target location specified in the SDD. Do not change the SDD." &

echo "Spawning worker for G7: End-to-End Integration..."
gemini -y -p "You are a test implementation worker. Read the SDD at 'tests/gap/SDDs/SDD-Integration-E2E-Migration.md'. Implement the test exactly as described. Write the code to the target location specified in the SDD. Do not change the SDD." &

wait
echo "All workers spawned."
