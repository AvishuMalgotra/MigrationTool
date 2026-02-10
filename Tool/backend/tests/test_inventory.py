import pytest
import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.inventory import InventoryService

def test_dependency_graph_building():
    # Setup Mocks
    mock_connector = MagicMock()
    mock_client = MagicMock()
    mock_connector.get_resource_client.return_value = mock_client
    
    # Mock Resources
    # VM1 depends on NIC1
    vm_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    nic_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
    
    vm_res = MagicMock()
    vm_res.id = vm_id
    vm_res.name = "vm1"
    vm_res.type = "Microsoft.Compute/virtualMachines"
    vm_res.location = "eastus"
    vm_res.tags = {}
    vm_res.sku = None
    # Mock properties where dependency exists
    vm_res.as_dict.return_value = {
        "properties": {
            "networkProfile": {
                "networkInterfaces": [
                    {"id": nic_id}
                ]
            }
        }
    }
    
    nic_res = MagicMock()
    nic_res.id = nic_id
    nic_res.name = "nic1"
    nic_res.type = "Microsoft.Network/networkInterfaces"
    nic_res.location = "eastus"
    nic_res.tags = {}
    nic_res.sku = None
    nic_res.as_dict.return_value = {"properties": {}}

    mock_client.resources.list.return_value = [vm_res, nic_res]
    mock_client.resource_groups.list.return_value = []

    # Run Service
    service = InventoryService(mock_connector)
    result = service.scan_subscription("sub1")

    # Assertions
    assert result["total_resources"] == 2
    dependencies = result["dependencies"]
    assert len(dependencies) >= 1
    
    # Verify exact edge
    edge = next((e for e in dependencies if e["source"] == vm_id and e["target"] == nic_id), None)
    assert edge is not None
    assert edge["relation"] == "property_ref" or edge.get("type") == "property_link" # Allow either key based on implementation

if __name__ == "__main__":
    test_dependency_graph_building()
    print("Test Passed!")
