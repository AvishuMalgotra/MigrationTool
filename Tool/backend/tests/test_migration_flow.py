import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, get_db
from database import Base, engine, SessionLocal
from models import AssessmentJob

# Re-create DB
Base.metadata.create_all(bind=engine)
# client = TestClient(app) defined later after mocking if needed, but TestClient usually works fine with patches

def override_get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@patch("main.AzureConnector")
@patch("main.MigrationService")
def test_migration_flow(mock_migration_service_cls, mock_connector_cls):
    # Setup
    mock_migration = MagicMock()
    mock_migration_service_cls.return_value = mock_migration
    
    # Mock Validation Success
    mock_migration.validate_move.return_value = {"valid": True, "error": None}
    
    # Mock Execution Success
    mock_migration.execute_move.return_value = {"success": True, "status": "COMPLETED"}

    # 1. Pre-seed a Job (Migration needs a job_id)
    db = SessionLocal()
    job = AssessmentJob(id="job_mig_test", tenant_id="tenant_1", status="COMPLETED")
    db.add(job)
    db.commit()
    db.close()

    # 2. Trigger Migration
    payload = {
        "job_id": "job_mig_test",
        "source_resource_group": "rg-source",
        "target_resource_group_id": "/subscriptions/sub2/resourceGroups/rg-target",
        "resources": [
            "/subscriptions/sub1/resourceGroups/rg-source/providers/Microsoft.Compute/virtualMachines/vm1"
        ]
    }
    
    response = client.post("/api/v1/migrate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACCEPTED"
    plan_id = data["plan_id"]

    # 3. Check Plan Status (Mock background task execution)
    # Since TestClient runs synchronous background tasks after request:
    response = client.get(f"/api/v1/plans/{plan_id}")
    assert response.status_code == 200
    plan_data = response.json()
    
    assert plan_data["status"] == "COMPLETED"
    assert plan_data["execution_log"]["status"] == "success"
    
    # Verify calls
    mock_migration.validate_move.assert_called_once()
    mock_migration.execute_move.assert_called_once()

if __name__ == "__main__":
    test_migration_flow()
    print("Test Passed!")
