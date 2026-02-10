from azure.identity import DefaultAzureCredential, ClientSecretCredential, AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
import os

class AzureConnector:
    def __init__(self, tenant_id: str = None, client_id: str = None, client_secret: str = None):
        """
        Initialize Azure Connector.
        Supports both AzureCliCredential (Env/CLI) and explicit Service Principal.
        """
        if client_id and client_secret and tenant_id:
            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            # Explicitly use Azure CLI Credential to avoid picking up empty/invalid env vars from .env
            # This is the most reliable way for local dev when "az login" is used.
            self.credential = AzureCliCredential()
    
    def get_resource_client(self, subscription_id: str) -> ResourceManagementClient:
        """
        Returns an authenticated ResourceManagementClient for the given subscription.
        """
        return ResourceManagementClient(self.credential, subscription_id)

    def verify_access(self, subscription_id: str):
        """
        Probes the subscription to verify we have at least Reader access.
        """
        client = self.get_resource_client(subscription_id)
        # Try a lightweight read operation
        try:
            # Listing locations is a cheap way to verify read access without listing all resources
            client.subscriptions.list_locations(subscription_id)
            return True
        except Exception as e:
            print(f"Access verification failed: {str(e)}")
            return False

    def get_token(self, scope: str = "https://management.azure.com/.default") -> str:
        """
        Gets an access token for the specified scope.
        Default: ARM Management.
        For Graph: Use 'https://graph.microsoft.com/.default'
        """
        if not self.credential:
            raise Exception("Azure Credential not initialized.")
        try:
            token = self.credential.get_token(scope)
            return token.token
        except Exception as e:
            logger.error(f"Failed to get token for scope {scope}: {e}")
            raise e

    def get_subscription_details(self, subscription_id: str):
         """
         Fetches subscription display name and other details.
         """
         client = self.get_resource_client(subscription_id)
         try:
             # azure.mgmt.resource.ResourceManagementClient.subscriptions usually has get(subscription_id)
             # But wait, ResourceManagementClient in older versions might just be resources.
             # Actually, Subscription operations are usually in 'SubscriptionClient'.
             # However, often ResourceManagementClient has .subscriptions too? 
             # Let's check imports. 'azure-mgmt-resource'.
             # If not, we use raw HTTP with token.
             import requests
             token = self.get_token()
             headers = {"Authorization": f"Bearer {token}"}
             url = f"https://management.azure.com/subscriptions/{subscription_id}?api-version=2020-01-01"
             resp = requests.get(url, headers=headers)
             if resp.status_code == 200:
                 return resp.json()
             return {"displayName": "Unknown", "subscriptionPolicies": {}}
         except Exception as e:
             return {"displayName": "Error", "error": str(e)}
