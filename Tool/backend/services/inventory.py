from .azure_connector import AzureConnector
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class InventoryService:
    def __init__(self, connector: AzureConnector):
        self.connector = connector

    def scan_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Performs a full inventory scan of the subscription.
        Returns a dictionary containing list of resource groups and their resources.
        """
        client = self.connector.get_resource_client(subscription_id)
        inventory = {
            "subscription_id": subscription_id,
            "resource_groups": [],
            "total_resources": 0,
            "resources": []
        }

        # 1. List Resource Groups
        logger.info(f"Scanning Resource Groups for subscription {subscription_id}...")
        rgs = list(client.resource_groups.list())
        for rg in rgs:
            rg_data = {
                "name": rg.name,
                "location": rg.location,
                "tags": rg.tags
            }
            inventory["resource_groups"].append(rg_data)

        # 2. List All Resources
        # We can use list_by_resource_group to map them better, but list() at sub level is faster for overview
        logger.info("Scanning Resources...")
        # Expand createdTime and changedTime if available
        resources = list(client.resources.list(expand="createdTime,changedTime"))
        
        for res in resources:
            res_data = {
                "id": res.id,
                "name": res.name,
                "type": res.type,
                "location": res.location,
                "sku": res.sku.as_dict() if res.sku else None,
                "kind": res.kind,
                "tags": res.tags,
                "resource_group": res.id.split("/resourceGroups/")[1].split("/")[0] if "/resourceGroups/" in res.id else None,
                "properties": res.as_dict().get("properties", {})
            }
            inventory["resources"].append(res_data)

        inventory["total_resources"] = len(inventory["resources"])
        
        # 3. Build Dependency Graph
        logger.info("Building Dependency Graph...")
        inventory["dependencies"] = self._build_dependency_graph(inventory["resources"])
        
        return inventory

    def _build_dependency_graph(self, resources: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Scans resource properties for references to other resources.
        Returns a list of edges: {"source": resource_id, "target": dependency_id}
        """
        # Create a set of all known resource IDs for O(1) lookup (case insensitive for Azure)
        resource_ids = {r["id"].lower() for r in resources}
        edges = []

        for res in resources:
            source_id = res["id"]
            props = res.get("properties", {})
            self._find_refs_recursive(props, source_id, resource_ids, edges)
        
        return edges

    def _find_refs_recursive(self, obj: Any, source_id: str, known_ids: set, edges: list):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and (k.lower() == "id" or k.endswith("Id")):
                    clean_v = v.lower()
                    if clean_v in known_ids and clean_v != source_id.lower():
                        edges.append({"source": source_id, "target": v, "relation": "property_ref"})
                else:
                    self._find_refs_recursive(v, source_id, known_ids, edges)
        elif isinstance(obj, list):
            for item in obj:
                self._find_refs_recursive(item, source_id, known_ids, edges)
