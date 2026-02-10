import json
import io
import zipfile
from typing import List, Dict, Any

class ARMService:
    """
    Generates ARM Templates for resources and packages them into a ZIP.
    Structure: Resource Type / Resource Name / template.json
    """

    def generate_arm_zip(self, resources: List[Dict[str, Any]], only_blocked: bool = False, blockers: Dict[str, Any] = None) -> bytes:
        """
        Generates a ZIP file containing ARM templates.
        """
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for res in resources:
                # Filter logic
                if only_blocked and blockers:
                    # If this resource ID is NOT in blockers, skip it
                    # But wait, blockers dict keys are IDs.
                    if res["id"] not in blockers and res["name"] not in blockers: 
                         # Check strict ID match or loose name match (safety)
                         # Blockers are usually keyed by ID in my app
                         continue

                # Generate Template Content
                template = self._create_single_resource_template(res)
                template_str = json.dumps(template, indent=4)
                
                # Determine Path
                # Type: Microsoft.Network/virtualNetworks -> Virtual Network
                # Folder: Virtual Network (Sanitized)
                # Name: Resource Name
                
                type_folder = res.get("type", "Unknown").split("/")[-1] # Simple type name
                res_name = res.get("name", "Unknown")
                
                # Path: Type/Name/template.json
                file_path = f"{type_folder}/{res_name}/template.json"
                
                zip_file.writestr(file_path, template_str)
                
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _create_single_resource_template(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wraps a resource definition in a valid ARM deployment template structure.
        """
        # Clean the resource definition for ARM
        props = resource.get("properties", {}).copy() if resource.get("properties") else {}
        
        # Remove Read-Only / System properties that cause deployment errors
        # Typical read-only fields: provisioningState, id, status, uniqueId
        keys_to_remove = [
            "provisioningState", "resourceId", "status", "uniqueId", "vmId", 
            "timeCreated", "defaultHostName", "inboundIpHeaders", "outboundIpHeaders"
        ]
        for k in keys_to_remove:
            props.pop(k, None)

        # Skeleton
        arm_resource = {
            "type": resource.get("type"),
            # Placeholder: Ideally we find this from the resource ID or a map. 
            # For now, 2021-04-01 is a reasonable fallback for many compute/network resources.
            # A more robust system would query the provider.
            "apiVersion": resource.get("apiVersion", "2021-04-01"), 
            "name": str(resource.get("name")), 
            "location": resource.get("location"),
            "properties": props
        }

        # Add SKU/Tags if present
        if "sku" in resource:
            arm_resource["sku"] = resource["sku"]
        if "tags" in resource:
            arm_resource["tags"] = resource["tags"]

        return {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {},
            "variables": {},
            "resources": [arm_resource] 
        }
