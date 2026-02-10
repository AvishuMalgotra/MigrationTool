import re
import logging
import requests
from services.azure_connector import AzureConnector

logger = logging.getLogger(__name__)

class ContextService:
    def __init__(self, connector: AzureConnector):
        self.connector = connector

    def get_context_data(self, subscription_id: str):
        """
        Fetches comprehensive context about the Azure environment.
        """
        data = {
            "tenant_name": "Standard Tenant",
            "tenant_id": "Unknown",
            "subscription_id": subscription_id,
            "subscription_name": "Unknown",
            "subscription_plan": "Pay-As-You-Go",
            "cost_score": "Calculating...", 
            "secure_score": "Calculating...", 
            "resource_count": "Calculating..."
        }

        try:
            token = self.connector.get_token()
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Subscription Details
            sub_details = self.connector.get_subscription_details(subscription_id)
            data["subscription_name"] = sub_details.get("displayName", "Unknown")
            data["tenant_id"] = sub_details.get("tenantId", "Unknown")
            
            # Format Plan Name
            policies = sub_details.get("subscriptionPolicies", {})
            quota_id = policies.get("quotaId", "Pay-As-You-Go")
            # Cleanup: Remove dates and underscores (e.g., PayAsYouGo_2014-09-01 -> Pay As You Go)
            clean_plan = re.sub(r'_\d{4}-\d{2}-\d{2}$', '', quota_id) # Remove date suffix
            clean_plan = re.sub(r'(?<!^)(?=[A-Z])', ' ', clean_plan) # Add spaces before caps
            data["subscription_plan"] = clean_plan

            # Try to fetch Tenant Name
            try:
                ten_url = "https://management.azure.com/tenants?api-version=2020-01-01"
                ten_resp = requests.get(ten_url, headers=headers, timeout=3)
                if ten_resp.status_code == 200:
                    tenants = ten_resp.json().get("value", [])
                    # Find matching tenant
                    matching_tenant = next((t for t in tenants if t["tenantId"] == data["tenant_id"]), None)
                    if matching_tenant:
                        data["tenant_name"] = matching_tenant.get("displayName", "Standard Tenant")
            except Exception:
                pass # Fallback

            # 2. Resource Count (Lightweight)
            try:
                res_url = f"https://management.azure.com/subscriptions/{subscription_id}/resources?api-version=2021-04-01&$select=id"
                res_resp = requests.get(res_url, headers=headers, timeout=5)
                if res_resp.status_code == 200:
                    res_list = res_resp.json().get("value", [])
                    data["resource_count"] = str(len(res_list))
                else:
                    data["resource_count"] = "Unknown"
            except:
                data["resource_count"] = "Unknown"

            # 3. Secure Score (Microsoft.Security)
            try:
                sec_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Security/secureScores?api-version=2020-01-01"
                sec_resp = requests.get(sec_url, headers=headers, timeout=3)
                if sec_resp.status_code == 200:
                    scores = sec_resp.json().get("value", [])
                    main_score = next((s for s in scores if s["name"] == "ascScore"), None)
                    if main_score:
                        current = main_score.get("properties", {}).get("score", {}).get("current", 0)
                        max_s = main_score.get("properties", {}).get("score", {}).get("max", 0)
                        percentage = round((current / max_s) * 100) if max_s > 0 else 0
                        data["secure_score"] = f"{percentage}%"
                    else:
                        data["secure_score"] = "Not Configured"
                else:
                    data["secure_score"] = "Unavailable"
            except Exception as e:
                logger.warning(f"Secure Score Fetch failed: {e}")
                data["secure_score"] = "Unavailable"

            # 4. Cost (Advisor) - Potential Savings
            try:
                adv_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Advisor/recommendations?api-version=2020-01-01&$filter=category eq 'Cost'"
                adv_resp = requests.get(adv_url, headers=headers, timeout=3)
                if adv_resp.status_code == 200:
                    recs = adv_resp.json().get("value", [])
                    total_savings = 0.0
                    for r in recs:
                        props = r.get("properties", {})
                        ext = props.get("extendedProperties", {})
                        savings = ext.get("savingsAmount")
                        if savings:
                            try:
                                total_savings += float(savings)
                            except: pass
                    
                    if total_savings > 0:
                        data["cost_score"] = f"Potential Savings: ${total_savings:,.2f}/yr"
                    else:
                        data["cost_score"] = "Optimized"
                else:
                    data["cost_score"] = "Unavailable"
            except Exception as e:
                 logger.warning(f"Advisor Fetch failed: {e}")
                 data["cost_score"] = "Unavailable"

        except Exception as e:
            logger.error(f"Context fetch failed: {e}")
            
        return data

    def export_resource_template(self, subscription_id: str, resource_group: str, resources: list[str]):
        """
        Uses the official Azure Management API to export a template for specific resources.
        POST https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/exportTemplate?api-version=2021-04-01
        """
        token = self.connector.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/exportTemplate?api-version=2021-04-01"
        
        payload = {
            "resources": resources,
            "options": "IncludeParameterDefaultValue"
        }
        
        try:
            # this is a long running operation, usually returns 202 Accepted + Location header
            # But for small sets it might return 200 OK.
            resp = requests.post(url, headers=headers, json=payload)
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 202:
                # Poll logic
                location = resp.headers.get("Location")
                if not location:
                     return {"error": "Async operation accepted but no Location header found."}
                
                # Poll URL
                import time
                for _ in range(10): # Try for 20 seconds
                    time.sleep(2)
                    poll_resp = requests.get(location, headers=headers)
                    if poll_resp.status_code == 200:
                        return poll_resp.json()
                    if poll_resp.status_code != 202:
                        return {"error": f"Polling failed: {poll_resp.text}"}
                
                return {"error": "Export timed out (polling)"}
            else:
                return {"error": f"Azure API Error: {resp.text}"}
                
        except Exception as e:
            return {"error": str(e)}

    def get_full_resource(self, subscription_id: str, resource_id: str) -> dict:
        """
        Fetches the full resource definition by ID to get all properties.
        Recursively tries common API versions if default fails.
        """
        client = self.connector.get_resource_client(subscription_id)
        
        # List of common API versions to try for generic resources
        versions_to_try = ["2021-04-01", "2023-01-01", "2020-06-01"]
        
        for version in versions_to_try:
            try:
                res = client.resources.get_by_id(resource_id, version)
                return res.as_dict()
            except Exception:
                continue
                
        # If all fail, return basic dict (missing properties likely, but better than crash)
        # Or try one last '2019-05-01'
        try:
             res = client.resources.get_by_id(resource_id, "2019-05-01")
             return res.as_dict()
        except:
            return {} 

    def get_role_assignments(self, subscription_id: str):
        """
        Fetches all role assignments for the subscription.
        Does NOT filter yet (filtering happens in main.py).
        """
        try:
            token = self.connector.get_token()
            headers = {"Authorization": f"Bearer {token}"}
            # List all role assignments for the subscription
            url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("value", [])
            return []
        except Exception as e:
            logger.error(f"Failed to fetch RBAC: {e}")
            return []

    def get_public_ips(self, subscription_id: str):
        """
        Fetches all Public IPs in the subscription.
        """
        try:
            token = self.connector.get_token()
            headers = {"Authorization": f"Bearer {token}"}
            url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Network/publicIPAddresses?api-version=2022-07-01"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("value", [])
            return []
        except Exception as e:
            logger.error(f"Failed to fetch PIPs: {e}")
            return []
            
    def get_vms(self, subscription_id: str):
        """
        Fetches all VMs in the subscription with InstanceView for status.
        """
        try:
            token = self.connector.get_token()
            headers = {"Authorization": f"Bearer {token}"}
            # Use stable version 2021-07-01
            url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Compute/virtualMachines?api-version=2021-07-01&$expand=instanceView"
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("value", [])
            logger.error(f"VM Fetch Error {resp.status_code}: {resp.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch VMs: {e}")
            return []

    def get_role_definitions(self, subscription_id: str) -> dict:
        """
        Fetches Role Definitions map: RoleId -> RoleName
        """
        try:
            token = self.connector.get_token()
            headers = {"Authorization": f"Bearer {token}"}
            url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions?api-version=2022-04-01"
            resp = requests.get(url, headers=headers, timeout=10)
            mapping = {}
            if resp.status_code == 200:
                for role in resp.json().get("value", []):
                    # role["id"] is full ID, but assignment usually refs full ID too.
                    # Or sometimes user needs just the name. 
                    mapping[role["id"]] = role["properties"]["roleName"] # Full ID match
                    mapping[role["name"]] = role["properties"]["roleName"] # UUID match
            return mapping
        except Exception as e:
            logger.error(f"Failed to fetch Role Defs: {e}")
            return {}

    def resolve_principals(self, principal_ids: list) -> dict:
        """
        Resolves a list of Principal IDs to {Display Name, SignIn Name/Email} using Microsoft Graph.
        Returns map: PrincipalId -> {displayName, signInName, objectType}
        """
        if not principal_ids: return {}
        
        mapping = {}
        unique_ids = list(set(principal_ids))
        
        try:
            # Use Graph Token
            token = self.connector.get_token("https://graph.microsoft.com/.default")
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # Graph API allows batching via `directoryObjects/getByIds`
            # Limit is 1000 per request.
            
            # Batching logic
            chunk_size = 900
            for i in range(0, len(unique_ids), chunk_size):
                chunk = unique_ids[i:i + chunk_size]
                payload = {
                    "ids": chunk,
                    "types": ["user", "group", "servicePrincipal"]
                }
                
                resp = requests.post("https://graph.microsoft.com/v1.0/directoryObjects/getByIds", headers=headers, json=payload)
                
                if resp.status_code == 200:
                    for obj in resp.json().get("value", []):
                        pid = obj["id"]
                        d_name = obj.get("displayName", "Unknown")
                        s_name = obj.get("userPrincipalName") or obj.get("mail") or "N/A" # UPN for users
                        
                        if obj.get("@odata.type") == "#microsoft.graph.servicePrincipal":
                             s_name = obj.get("appId", "N/A") # AppID for SPs
                        
                        mapping[pid] = {
                            "displayName": d_name,
                            "signInName": s_name,
                            "objectType": obj.get("@odata.type", "").replace("#microsoft.graph.", "")
                        }
                else:
                    logger.warning(f"Graph API Error {resp.status_code}: {resp.text}")
                    
        except Exception as e:
            logger.error(f"Graph API Resolution Failed: {e}")
            # If Graph fails (e.g. permission denied), return empty map, main loop defaults to ID
            
        return mapping 
