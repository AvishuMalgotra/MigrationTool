from .azure_connector import AzureConnector
from .dependency_resolver import DependencyResolver
from azure.core.exceptions import HttpResponseError
from azure.mgmt.resource.resources.models import ResourcesMoveInfo
import logging
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class MigrationService:
    def __init__(self, connector: AzureConnector):
        self.connector = connector

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(HttpResponseError),
        reraise=True
    )
    def validate_move(self, source_subscription_id: str, source_rg: str, target_rg_id: str, resource_ids: List[str], inventory_snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validates if resources can be moved to the target resource group.
        Includes "Intelligent" Dependency Check if inventory_snapshot is provided.
        """
        # 1. Dependency Check (Intelligent Layer)
        if inventory_snapshot:
            try:
                resolver = DependencyResolver(inventory_snapshot)
                missing = resolver.get_missing_dependencies(resource_ids)
                
                if missing:
                    msg = f"Validation Warning: The following required dependencies are missing from the move batch: {', '.join(missing)}. The move may fail."
                    logger.warning(msg)
                    # For strict mode, we could return False. For now, we append to error if Azure fails, or just warn.
                    # Let's return valid=False to force user to fix it (Safety Guard)
                    # return {"valid": False, "error": msg} 
                    # Actually, let's just log it for now to avoid blocking "partial moves" if user intends it.
                    # But the task is "Safety Guards". Let's fail validation? No, might handle it in UI.
                    # let's modify the return to include warnings
                    return {"valid": False, "error": msg} # Strict safety
            except Exception as e:
                logger.error(f"Dependency check failed: {e}")

        # 2. Azure API Validation (Official Layer)
        client = self.connector.get_resource_client(source_subscription_id)
        
        move_info = ResourcesMoveInfo(
            resources=resource_ids,
            target_resource_group=target_rg_id
        )

        logger.info(f"Validating move for {len(resource_ids)} resources from {source_rg} to {target_rg_id}")
        
        try:
            # Azure SDK poller for validation
            poller = client.resources.begin_validate_move_resources(
                source_resource_group_name=source_rg,
                parameters=move_info
            )
            poller.result() # Wait for completion
            
            logger.info("Validation successful")
            return {"valid": True, "error": None}
            
        except HttpResponseError as e:
            logger.error(f"Validation failed: {e.message}")
            return {"valid": False, "error": e.message}
        except Exception as e:
            logger.error(f"Unexpected error during validation: {str(e)}")
            return {"valid": False, "error": str(e)}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(HttpResponseError),
        reraise=True
    )
    def execute_move(self, source_subscription_id: str, source_rg: str, target_rg_id: str, resource_ids: List[str]) -> Dict[str, Any]:
        """
        Executes the move operation. This is a Long Running Operation.
        Retries on transient HTTP errors up to 3 times.
        """
        client = self.connector.get_resource_client(source_subscription_id)
        
        move_info = ResourcesMoveInfo(
            resources=resource_ids,
            target_resource_group=target_rg_id
        )

        logger.info(f"Starting move for {len(resource_ids)} resources...")
        
        try:
            poller = client.resources.begin_move_resources(
                source_resource_group_name=source_rg,
                parameters=move_info
            )
            
            # For MVP, we wait synchronously. In PROD, we would return the poller token or run in a background worker that polls.
            poller.result() 
            
            logger.info("Move operation completed successfully")
            return {"success": True, "status": "COMPLETED"}
            
        except HttpResponseError as e:
            # Check if it's a retryable error code (e.g. 429 Too Many Requests, 503 Service Unavailable)
            # Default generic retry grabs all HttpResponseError, which might be aggressive, but okay for MVP reliability.
            if e.status_code in [429, 503, 500]:
                 logger.warning(f"Transient error encountered: {e.status_code}. Retrying...")
                 raise e # Processed by tenacity
            
            logger.error(f"Move operation failed: {e.message}")
            return {"success": False, "status": "FAILED", "error": e.message}
        except Exception as e:
            logger.error(f"Move operation failed unexpectedly: {str(e)}")
            return {"success": False, "status": "FAILED", "error": str(e)}
