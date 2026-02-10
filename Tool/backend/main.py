import os
import logging
import io
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import concurrent.futures

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import AssessmentJob, Tenant, MigrationPlan
from schemas import AssessmentRequest, MigrationRequest

from services.azure_connector import AzureConnector
from services.inventory import InventoryService
from services.ai_service import AIService
from services.compatibility import CompatibilityService
from services.report_service import ReportService
from services.migration import MigrationService
from services.arm_service import ARMService
from services.context_service import ContextService

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables (for MVP only - usually use Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Azure Migration Agent API",
    description="Backend service for assessing and migrating Azure resources.",
    version="0.1.0"
)

origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info(">>> SERVER RESTARTING <<<")
    logger.info(f"Active Config - Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    logger.info(f"Active Config - Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}")
    logger.info(f"Active Config - Origins: {os.getenv('ALLOWED_ORIGINS')}")
    logger.info(">>> VERIFYING AI CONNECTION... <<<")
    try:
        service = AIService()
        status = await service.check_health()
        logger.info(f"Startup Connectivity Check: {'SUCCESS' if status else 'FAILED'}")
    except Exception as e:
        logger.error(f"Startup Check Crashed: {e}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "details": str(exc)},
    )

# Helper for Safe DB Session in Background Tasks
@contextmanager
def safe_db_session():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()

def run_assessment_task(job_id: str, subscription_id: str, tenant_id: str, client_id: str = None, client_secret: str = None):
    """
    Background task to run the inventory scan and update the job status.
    Uses safe_db_session to ensure cleanup.
    """
    with safe_db_session() as db:
        try:
            logger.info(f"Starting assessment for Job {job_id}")
            
            connector = AzureConnector(tenant_id, client_id, client_secret) 
            inventory_service = InventoryService(connector)
            compatibility_service = CompatibilityService()
            ai_service = AIService()
            
            # 1. Run Inventory Scan
            inventory_data = inventory_service.scan_subscription(subscription_id)
            
            # 2. Run Compatibility Analysis
            blockers = compatibility_service.assess_compatibility(inventory_data["resources"])
            
            # 3. Generate AI Report (Graceful Failure)
            try:
                ai_report = ai_service.generate_report(inventory_data, blockers)
            except Exception as ai_e:
                logger.error(f"AI Report Generation Failed: {ai_e}")
                ai_report = f"# Assessment Completed (AI Unavailable)\n\n**Note:** The AI report could not be generated due to provider limits ({str(ai_e)}).\n\nHowever, your infrastructure data and compatibility analysis are fully available below."

            # 4. Update Job
            job = db.query(AssessmentJob).filter(AssessmentJob.id == job_id).first()
            if job:
                job.status = "COMPLETED"
                job.inventory_snapshot = inventory_data
                job.blockers = blockers
                job.ai_generated_summary = ai_report
                db.commit()
                logger.info(f"Job {job_id} completed successfully.")
                
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            # We must rollback to ensure the session is clean for the update
            db.rollback() 
            job = db.query(AssessmentJob).filter(AssessmentJob.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.blockers = {"error": str(e)}
                db.commit()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "migration-agent-backend"}

@app.get("/")
def read_root():
    return {"status": "ok", "service": "migration-agent-backend", "docs_url": "/docs"}

@app.get("/api/debug-ai")
async def debug_ai():
    """Diagnostic endpoint to debug AI connection"""
    from dotenv import load_dotenv # Keep local import for logic specific to this debug endpoint (force reload)
    load_dotenv(override=True) 
    
    try:
        service = AIService()
        health_check = False
        runtime_details = "N/A"
        
        # 1. Official Health Check
        health_check = await service.check_health()
        
        # 2. Deep Probe (Bypass try/catch in check_health to see error)
        try:
            if service.client:
                # Unified Probe
                target_model = service.azure_deployment if service.provider == "azure" else service.openai_model
                
                resp = service.client.chat.completions.create(
                    model=target_model,
                    messages=[{"role": "user", "content": "probetest"}],
                    max_tokens=5
                )
                runtime_details = f"Success: {resp.choices[0].message.content[:20]}..."
        except Exception as deep_e:
            runtime_details = f"Deep Failure: {str(deep_e)}"
            
        return {
            "provider": service.provider,
            "has_key": bool(service.openai_api_key or service.azure_api_key),
            "key_prefix": (service.openai_api_key[:4] if service.openai_api_key else "None"),
            "model": service.openai_model or service.azure_deployment,
            "health_check": health_check,
            "runtime_error": runtime_details
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/ai-status")
async def ai_status():
    """Checks connection to Azure OpenAI / OpenAI"""
    try:
        service = AIService()
        logger.info(f"Checking AI Status. Provider: {service.provider}")
        is_connected = await service.check_health()
        logger.info(f"AI Check Result: {is_connected}")
        return {"connected": is_connected, "provider": service.provider}
    except Exception as e:
        logger.error(f"AI Status Check Failed: {e}")
        return {"connected": False, "error": str(e)}

@app.post("/api/v1/assess")
def trigger_assessment(
    request: AssessmentRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Triggers an asynchronous assessment job.
    """
    # 1. Create Tenant if not exists (Lazy init for MVP)
    tenant = db.query(Tenant).filter(Tenant.id == request.tenant_id).first()
    if not tenant:
        tenant = Tenant(id=request.tenant_id, name="Auto-Created Tenant")
        db.add(tenant)
        db.commit()
    
    # 2. Create Job
    new_job = AssessmentJob(
        tenant_id=request.tenant_id,
        status="PENDING"
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # 3. Schedule Background Task
    background_tasks.add_task(
        run_assessment_task, 
        new_job.id, 
        request.subscription_id, 
        request.tenant_id,
        request.client_id,
        request.client_secret
    )
    
    return {
        "job_id": new_job.id,
        "status": "ACCEPTED",
        "message": f"Assessment started for subscription {request.subscription_id}"
    }

@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Retrieve status and results of an assessment job.
    """
    job = db.query(AssessmentJob).filter(AssessmentJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/v1/jobs/{job_id}/export")
def export_job_report(job_id: str, db: Session = Depends(get_db)):
    """
    Generates and downloads an Excel report for the job.
    """
    job = db.query(AssessmentJob).filter(AssessmentJob.id == job_id).first()
    if not job or not job.inventory_snapshot:
        raise HTTPException(status_code=404, detail="Job or inventory not found")
    
    # Use ReportService for Professional Export
    report_service = ReportService()
    
    # We pass the inventory directly. The Job ID helps details.
    inventory = job.inventory_snapshot
    if not inventory.get("tenant_id"): inventory["tenant_id"] = job.tenant_id
    if not inventory.get("subscription_id"): 
        try:
             inventory["subscription_id"] = inventory["resources"][0]["id"].split("/")[2]
        except:
             inventory["subscription_id"] = "Unknown"

    # Sync generation
    excel_bytes = report_service.generate_excel_report(job_id, inventory, job.blockers)
    
    output = io.BytesIO(excel_bytes)
    output.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="Assessment_Report_{job_id}.xlsx"'
    }
    return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)

@app.get("/api/v1/jobs/{job_id}/export/arm")
def export_arm_templates(job_id: str, db: Session = Depends(get_db)):
    """
    Export ARM Templates for BLOCKED resources only.
    Fetches FULL resource details to ensure valid templates.
    """
    job = db.query(AssessmentJob).filter(AssessmentJob.id == job_id).first()
    if not job or not job.inventory_snapshot:
        raise HTTPException(status_code=404, detail="Job or inventory not found")

    raw_resources = job.inventory_snapshot.get("resources", [])
    
    # Identify Subscription ID
    try:
        sub_id = job.inventory_snapshot.get("subscription_id") or raw_resources[0]["id"].split("/")[2]
    except:
        sub_id = None

    # Setup Connector/Service for fetching full details
    connector = AzureConnector()
    ctx_service = ContextService(connector)
    arm_service = ARMService()

    # Filter for Blocked resources 
    full_resources = []
    
    # Blockers dict keys are Resource IDs or Names.
    blockers = job.blockers or {}

    # Identify targets
    targets = [res for res in raw_resources if res["id"] in blockers or res["name"] in blockers]

    if not targets:
        # No blocked resources, return empty zip
        zip_bytes = arm_service.generate_arm_zip([], only_blocked=False)
        output = io.BytesIO(zip_bytes)
        output.seek(0)
        headers = {'Content-Disposition': f'attachment; filename="Blocked_Resources_Templates_{job_id}.zip"'}
        return StreamingResponse(output, media_type='application/zip', headers=headers)

    # Identify targets
    targets = [res for res in raw_resources if res["id"] in blockers or res["name"] in blockers]

    if not targets:
        # No blocked resources, return empty zip
        zip_bytes = arm_service.generate_arm_zip([], only_blocked=False)
        output = io.BytesIO(zip_bytes)
        output.seek(0)
        headers = {'Content-Disposition': f'attachment; filename="Blocked_Resources_Templates_{job_id}.zip"'}
        return StreamingResponse(output, media_type='application/zip', headers=headers)

    # Parallel Export of INDIVIDUAL Resources
    # User Requirement: 
    # 1. Exact Portal Content (handled by export_resource_template API)
    # 2. Specific Hierarchy "Type/Name/template.json" (handled here)
    
    logger.info(f"Starting Parallel Official ARM Export for {len(targets)} resources.")
    


    def export_single_resource(res):
        try:
            rg = res.get("resource_group")
            if not rg: return None
            
            # API Call: Export Single Resource
            # Passing a list of 1 ID ensures we get just that resource's template.
            template = ctx_service.export_resource_template(subscription_id=sub_id, resource_group=rg, resources=[res["id"]])
            
            if "error" in template:
                logger.error(f"Export Error for {res['name']}: {template['error']}")
                return {
                    "resource": res,
                    "error": template["error"]
                }
            
            return {
                "resource": res,
                "template": template
            }
        except Exception as e:
            logger.error(f"Export Crash for {res['name']}: {e}")
            return None

    exported_items = []
    # Using 10 workers to balance speed vs API Rate Limits
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(export_single_resource, targets))
        exported_items = [r for r in results if r]

    # --- EXTRA EXPORTS (RBAC, PIPS, VMS) ---
    logger.info("Fetching extra export data (RBAC, PIPs, VMs)...")
    
    # 1. RBAC (Enriched)
    # Requested Columns: RoleAssignmentId, Scope, DisplayName, SignInName, RoleDefinitionName, RoleDefinitionId, ObjectId, ObjectType, RoleAssignmentDescription, ConditionVersion, Condition
    rbac_csv_rows = [["RoleAssignmentId", "Scope", "DisplayName", "SignInName", "RoleDefinitionName", "RoleDefinitionId", "ObjectId", "ObjectType", "RoleAssignmentDescription", "ConditionVersion", "Condition"]]
    
    all_rbacs = ctx_service.get_role_assignments(sub_id)
    role_defs = ctx_service.get_role_definitions(sub_id) # ID -> Name map
    
    # Collect Principal IDs for Batch Resolution
    principal_ids = set()
    filtered_rbacs = []
    sub_scope_prefix = f"/subscriptions/{sub_id}"

    for r in all_rbacs:
        scope = r.get("properties", {}).get("scope", "").lower()
        if not scope.startswith(sub_scope_prefix.lower()):
            continue
        filtered_rbacs.append(r)
        principal_ids.add(r.get("properties", {}).get("principalId"))
    
    # Resolve Principals via Graph (User/Group Names)
    principal_map = ctx_service.resolve_principals(list(principal_ids))
    
    rbac_json = []

    for r in filtered_rbacs:
        props = r.get("properties", {})
        
        # Resolve Data
        p_id = props.get("principalId")
        rd_id = props.get("roleDefinitionId")
        
        # Role Name
        role_name = role_defs.get(rd_id, "Unknown Role")
        if role_name == "Unknown Role" and rd_id:
             # Try matching just the UUID part if full ID failed
             uuid_part = rd_id.split("/")[-1]
             # Search values (slow linear scan but safe for small list)
             # Better: ContextService already maps UUID -> Name if possible
             pass

        # Principal Data
        p_data = principal_map.get(p_id, {})
        d_name = p_data.get("displayName", "Unknown")
        s_name = p_data.get("signInName", "")
        o_type = p_data.get("objectType", props.get("principalType", "Unknown"))
        
        # Build Row
        row = [
            r.get("id"), # RoleAssignmentId
            props.get("scope"),
            d_name, # DisplayName
            s_name, # SignInName
            role_name, # RoleDefinitionName
            rd_id, # RoleDefinitionId
            p_id, # ObjectId
            o_type, # ObjectType
            props.get("description", ""), # RoleAssignmentDescription
            props.get("conditionVersion", ""), # ConditionVersion
            props.get("condition", "") # Condition
        ]
        rbac_csv_rows.append(row)

    # 2. Public IPs
    pips = ctx_service.get_public_ips(sub_id)
    pip_csv_rows = [["Name", "Resource Group", "IP Address", "SKU", "Assignment", "Associated to", "Location", "Subscription"]]
    
    # Helper to map NIC ID to PIP Address (for VM export later)
    nic_to_pip = {} 

    for p in pips:
        props = p.get("properties", {})
        sku = p.get("sku", {}).get("name", "Basic")
        
        # Association
        assoc_text = "Unattached"
        ip_conf = props.get("ipConfiguration", {})
        if ip_conf:
            assoc_id = ip_conf.get("id", "")
            # ID looks like: .../networkInterfaces/nic1/ipConfigurations/ipconfig1
            if "/networkInterfaces/" in assoc_id:
                parts = assoc_id.split("/")
                try:
                    nic_idx = parts.index("networkInterfaces")
                    nic_name = parts[nic_idx+1]
                    assoc_text = f"NIC: {nic_name}"
                    
                    # Store for VM mapping: /subscriptions/.../networkInterfaces/nic1 -> 1.2.3.4
                    # Reconstruct NIC ID properly or allow partial match
                    # Let's map the FULL NIC ID (up to the nic name)
                    nic_full_id = "/".join(parts[:nic_idx+2]).lower()
                    nic_to_pip[nic_full_id] = props.get("ipAddress", "")
                except:
                    assoc_text = assoc_id
        
        pip_csv_rows.append([
            p.get("name"),
            p.get("id", "").split("/resourceGroups/")[1].split("/")[0] if "/resourceGroups/" in p.get("id", "") else "Unknown",
            props.get("ipAddress"),
            sku,
            props.get("publicIPAllocationMethod"),
            assoc_text,
            p.get("location"),
            sub_id
        ])

    # 3. Virtual Machines
    vms = ctx_service.get_vms(sub_id)
    vm_csv_rows = [["Name", "Resource Group", "Location", "Subscription", "Status", "Operating System", "Size", "Public IP Address"]]
    
    for vm in vms:
        props = vm.get("properties", {})
        
        # Status Logic (Improved)
        status = "Unknown"
        # instanceView usually in properties, but check strict
        iv = props.get("instanceView", {})
        if not iv:
             iv = vm.get("instanceView", {}) # Fallback to top level
        
        # Look for PowerState
        for s in iv.get("statuses", []):
            code = s.get("code", "")
            if "PowerState" in code:
                # Prefer displayStatus (e.g., "VM running")
                status = s.get("displayStatus", code.split("/")[-1])
                break
        
        # OS
        os_type = props.get("storageProfile", {}).get("osDisk", {}).get("osType", "Unknown")
        
        # Size
        size = props.get("hardwareProfile", {}).get("vmSize", "Unknown")
        
        # Public IP (via NICs)
        vm_pip = "None"
        nics = props.get("networkProfile", {}).get("networkInterfaces", [])
        for nic_ref in nics:
            nic_id = nic_ref.get("id", "").lower()
            if nic_id in nic_to_pip:
                vm_pip = nic_to_pip[nic_id]
                break # Show first found
        
        vm_csv_rows.append([
            vm.get("name"),
            vm.get("id", "").split("/resourceGroups/")[1].split("/")[0] if "/resourceGroups/" in vm.get("id", "") else "Unknown",
            vm.get("location"),
            sub_id,
            status,
            os_type,
            size,
            vm_pip
        ])

    # Generate ZIP
    import zipfile
    import csv
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
         # Standard Exports
         for item in exported_items:
            res = item["resource"]
            type_folder = res.get("type", "Unknown").split("/")[-1] 
            res_name = res.get("name", "Unknown")
            
            if "template" in item:
                file_path = f"{type_folder}/{res_name}/template.json"
                content = item["template"]
                if "template" in content: content = content["template"]
                zip_file.writestr(file_path, json.dumps(content, indent=4))
            elif "error" in item:
                file_path = f"{type_folder}/{res_name}/error.log"
                zip_file.writestr(file_path, str(item["error"]))
        
         # Extra Exports Folder
         # RBAC
         # Save JSON BEFORE CSV loop to keep it clean/official
         zip_file.writestr("Extra_Exports/RBAC.json", json.dumps(filtered_rbacs, indent=4))
         
         rbac_csv_io = io.StringIO()
         csv.writer(rbac_csv_io).writerows(rbac_csv_rows)
         zip_file.writestr("Extra_Exports/RBAC.csv", rbac_csv_io.getvalue())
         
         # Public IPs
         zip_file.writestr("Extra_Exports/PublicIPs.json", json.dumps(pips, indent=4)) 
         pip_csv_io = io.StringIO()
         csv.writer(pip_csv_io).writerows(pip_csv_rows)
         zip_file.writestr("Extra_Exports/PublicIPs.csv", pip_csv_io.getvalue())

         # VMs
         zip_file.writestr("Extra_Exports/VirtualMachines.json", json.dumps(vms, indent=4))
         vm_csv_io = io.StringIO()
         csv.writer(vm_csv_io).writerows(vm_csv_rows)
         zip_file.writestr("Extra_Exports/VirtualMachines.csv", vm_csv_io.getvalue())


    zip_bytes = zip_buffer.getvalue()
    
    output = io.BytesIO(zip_bytes)
    output.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="Blocked_Resources_Templates_{job_id}.zip"'
    }
    return StreamingResponse(output, media_type='application/zip', headers=headers)

@app.get("/api/v1/context")
def get_environment_context(subscription_id: str, tenant_id: str = None, client_id: str = None, client_secret: str = None):
    """
    Returns Key Info about the environment: Scores, Plan, etc.
    """
    try:
        # Create fresh connector (lightweight)
        connector = AzureConnector(tenant_id, client_id, client_secret)
        ctx_service = ContextService(connector)
        return ctx_service.get_context_data(subscription_id)
    except Exception as e:
        logger.error(f"Context API failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def run_migration_task(plan_id: str, request: MigrationRequest, subscription_id: str):
    """
    Background task to orchestrate migration.
    Uses safe_db_session for reliability.
    """
    with safe_db_session() as db:
        try:
            logger.info(f"Starting migration plan {plan_id}")
            connector = AzureConnector()
            service = MigrationService(connector)
            
            # 1. Update status to VALIDATING
            plan = db.query(MigrationPlan).filter(MigrationPlan.id == plan_id).first()
            job = db.query(AssessmentJob).filter(AssessmentJob.id == plan.job_id).first()
            
            if plan:
                plan.status = "VALIDATING"
                db.commit()

            # 2. Validate
            # Pass inventory snapshot for Intelligent Dependency Checking
            snapshot = job.inventory_snapshot if job else None
            
            validation = service.validate_move(
                subscription_id, 
                request.source_resource_group, 
                request.target_resource_group_id, 
                request.resources,
                inventory_snapshot=snapshot
            )

            if not validation["valid"]:
                logger.error(f"Validation failed for plan {plan_id}: {validation['error']}")
                plan.status = "FAILED_VALIDATION"
                plan.execution_log = {"error": validation["error"]}
                db.commit()
                return

            # 3. Execute
            plan.status = "MOVING"
            db.commit()
            
            result = service.execute_move(
                subscription_id, 
                request.source_resource_group, 
                request.target_resource_group_id, 
                request.resources
            )
            
            if result["success"]:
                plan.status = "COMPLETED"
                plan.execution_log = {"status": "success"}
            else:
                plan.status = "FAILED"
                plan.execution_log = {"error": result["error"]}
            
            db.commit()
            logger.info(f"Migration plan {plan_id} finished with status {plan.status}")

        except Exception as e:
            logger.error(f"Migration plan {plan_id} crashed: {str(e)}")
            # Rollback to ensure clean state
            db.rollback()
            plan = db.query(MigrationPlan).filter(MigrationPlan.id == plan_id).first()
            if plan:
                plan.status = "CRASHED"
                plan.execution_log = {"error": str(e)}
                db.commit()

@app.post("/api/v1/migrate")
def trigger_migration(
    request: MigrationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Triggers the migration workflow.
    """
    # Verify Job exists
    job = db.query(AssessmentJob).filter(AssessmentJob.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Assessment Job not found")
        
    # Create Plan
    plan = MigrationPlan(
        job_id=request.job_id,
        status="PENDING",
        ordered_batches=json.dumps(request.resources) # Simplified for MVP
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    # Safety Check for Resources
    if not request.resources:
        raise HTTPException(status_code=400, detail="No resources provided for migration")

    # We need subscription ID from the job snapshot or request. 
    # For MVP, let's extract it from the first resource ID or assume passed.
    # Parsing subscription from resource ID: /subscriptions/{sub}/...
    try:
        subscription_id = request.resources[0].split("/")[2]
    except:
        raise HTTPException(status_code=400, detail="Invalid resource ID format")

    background_tasks.add_task(
        run_migration_task,
        plan.id,
        request,
        subscription_id
    )
    
    return {
        "plan_id": plan.id,
        "status": "ACCEPTED",
        "message": "Migration orchestration started"
    }

@app.get("/api/v1/plans/{plan_id}")
def get_plan_status(plan_id: str, db: Session = Depends(get_db)):
    plan = db.query(MigrationPlan).filter(MigrationPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

