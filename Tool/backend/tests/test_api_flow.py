import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, get_db
from database import Base, engine, SessionLocal

# Setup Test DB
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@patch("main.AzureConnector")
@patch("main.InventoryService")
def test_assessment_flow(mock_inventory_service_cls, mock_azure_connector_cls):
    # Setup Mocks
    mock_connector = MagicMock()
    mock_azure_connector_cls.return_value = mock_connector
    
    mock_inventory = MagicMock()
    mock_inventory_service_cls.return_value = mock_inventory
    
    mock_inventory.scan_subscription.return_value = {
        "subscription_id": "sub-123",
        "total_resources": 5,
        "resources": [{"id": "res1", "name": "vm1"}]
    }

    # 1. Trigger Assessment
    payload = {
        "tenant_id": "tenant-test-1",
        "subscription_id": "sub-123"
    }
    response = client.post("/api/v1/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACCEPTED"
    job_id = data["job_id"]

    # 2. Check Job Status (Background task might take a ms, but should be fast in mock)
    # In real integration tests we might need to wait, but here it's executing in-process
    # However, depending on how TestClient handles BackgroundTasks, we might need a small wait?
    # TestClient runs background tasks after the response is returned. 
    
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    job_data = response.json()
    
    assert job_data["status"] == "COMPLETED"
    assert job_data["inventory_snapshot"]["total_resources"] == 5
    assert job_data["ai_generated_summary"] is not None

if __name__ == "__main__":
    # Manually run if executed directly
    test_assessment_flow()
    print("Test Passed!")
