from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class AssessmentRequest(BaseModel):
    tenant_id: str
    subscription_id: str
    resource_groups: List[str] = []
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

class MigrationRequest(BaseModel):
    job_id: str
    source_resource_group: str
    target_resource_group_id: str
    resources: List[str]

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
