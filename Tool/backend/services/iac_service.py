from typing import List, Dict, Any
import json

class IaCService:
    """
    Generates Terraform code from Azure Resource Inventory.
    Implements a basic "Reverse Engineering" of resources.
    """

    def generate_terraform(self, resources: List[Dict[str, Any]]) -> str:
        tf_code = ["""
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}
"""]
        
        # We need to ensure Resource Groups are created first
        rgs = set()
        for res in resources:
            if res.get("resource_group"):
                rgs.add((res["resource_group"], res["location"]))
        
        for rg_name, location in rgs:
            tf_code.append(self._generate_rg(rg_name, location))

        # Sort resources by type to group them in output (Dependency Sort passed in would be better, but Terraform handles DAG graph itself usually)
        # We just dump them.
        
        for res in resources:
            res_type = res.get("type", "").lower()
            if "virtualnetworks" in res_type:
                tf_code.append(self._generate_vnet(res))
            elif "virtualmachines" in res_type:
                tf_code.append(self._generate_vm(res))
            elif "networkinterfaces" in res_type:
                tf_code.append(self._generate_nic(res))
            elif "storageaccounts" in res_type:
                tf_code.append(self._generate_storage(res))
            # Add more handlers as needed
            
        return "\n".join(tf_code)

    def _sanitize(self, name: str) -> str:
        return name.replace("-", "_").lower()

    def _generate_rg(self, name: str, location: str) -> str:
        return f"""
resource "azurerm_resource_group" "{self._sanitize(name)}" {{
  name     = "{name}"
  location = "{location}"
}}
"""

    def _generate_vnet(self, res: Dict) -> str:
        name = res["name"]
        rg = res["resource_group"]
        loc = res["location"]
        props = res.get("properties", {})
        address_space = json.dumps(props.get("addressSpace", {}).get("addressPrefixes", ["10.0.0.0/16"]))
        
        return f"""
resource "azurerm_virtual_network" "{self._sanitize(name)}" {{
  name                = "{name}"
  location            = "{loc}"
  resource_group_name = azurerm_resource_group.{self._sanitize(rg)}.name
  address_space       = {address_space}
}}
"""

    def _generate_vm(self, res: Dict) -> str:
        name = res["name"]
        rg = res["resource_group"]
        loc = res["location"]
        vm_size = res.get("sku", {}).get("name", "Standard_DS1_v2")
        
        # Simplified NIC attachment (assuming 1st NIC found in props)
        # In real-world, we'd need to link to the actual NIC resource ID
        nic_id = "TODO_LINK_NIC_ID"
        
        return f"""
resource "azurerm_linux_virtual_machine" "{self._sanitize(name)}" {{
  name                = "{name}"
  resource_group_name = azurerm_resource_group.{self._sanitize(rg)}.name
  location            = "{loc}"
  size                = "{vm_size}"
  admin_username      = "adminuser"
  network_interface_ids = [] # TODO: specific NIC mapping required complex graph logic

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }}

  source_image_reference {{
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "16.04-LTS"
    version   = "latest"
  }}
}}
"""

    def _generate_nic(self, res: Dict) -> str:
        name = res["name"]
        rg = res["resource_group"]
        loc = res["location"]
        
        return f"""
resource "azurerm_network_interface" "{self._sanitize(name)}" {{
  name                = "{name}"
  location            = "{loc}"
  resource_group_name = azurerm_resource_group.{self._sanitize(rg)}.name

  ip_configuration {{
    name                          = "internal"
    subnet_id                     = "TODO_SUBNET_ID"
    private_ip_address_allocation = "Dynamic"
  }}
}}
"""

    def _generate_storage(self, res: Dict) -> str:
        name = res["name"]
        rg = res["resource_group"]
        loc = res["location"]
        sku = res.get("sku", {}).get("name", "Standard_LRS") # Standard_LRS
        # Split Standard_LRS -> tier=Standard, replication=LRS
        parts = sku.split("_")
        tier = parts[0] if len(parts) > 0 else "Standard"
        repl = parts[1] if len(parts) > 1 else "LRS"

        return f"""
resource "azurerm_storage_account" "{self._sanitize(name)}" {{
  name                     = "{name}"
  resource_group_name      = azurerm_resource_group.{self._sanitize(rg)}.name
  location                 = "{loc}"
  account_tier             = "{tier}"
  account_replication_type = "{repl}"
}}
"""
