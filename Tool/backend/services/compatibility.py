from typing import List, Dict, Any, Optional

class CompatibilityService:
    UNSUPPORTED_TYPES = [
        "Microsoft.ClassicCompute/virtualMachines",
        "Microsoft.ClassicNetwork/virtualNetworks",
        "Microsoft.ClassicStorage/storageAccounts",
        "Microsoft.Compute/availabilitySets" 
    ]
    
    def __init__(self):
        # Cache for AI/Doc assessment answers to avoid redundant API calls
        # Map: ResourceType (str) -> Result (Dict)
        self._type_cache = {}

    def check_resource(self, resource: Dict[str, Any], target_region: str = None) -> List[str]:
        """
        Checks a single resource for migration blockers.
        Returns a list of blockers/warnings.
        Uses cached AI assessment for 'Can be moved' status indirectly.
        """
        issues = []
        res_type = resource.get("type", "").lower()
        
        # Note: The logic for "Can be moved" (Yes/No) is now handled primarily 
        # in assess_compatibility or generate_detailed_report via AI.
        # Here we only check for *instance-specific* blockers like locks.

        # 1. Lock Check
        if resource.get("locks"):
             issues.append("BLOCKER: Resource has Management Locks applied. Remove locks before moving.")

        # 2. Region Check
        if target_region and resource["location"] != target_region:
             issues.append(f"BLOCKER: Cross-region moves require Azure Resource Mover.")

        return issues

    def assess_compatibility(self, resources: List[Dict[str, Any]], target_region: str = None) -> Dict[str, List[str]]:
        """
        Batch assessment. Returns a map of resource_id -> list of blockers.
        Includes both instance-specific checks (locks) and Type-level AI validation.
        """
        report = {}
        
        # Pre-populate cache for all unique types to batch AI calls (if we supported batching)
        # For now, just ensures we hit the cache logic efficiently
        unique_types = set(r.get("type", "").lower() for r in resources)

        for res in resources:
            issues = self.check_resource(res, target_region)
            
            # AI Type Check
            res_type = res.get("type", "").lower()
            ai_result = self._get_ai_assessment(res_type)
            
            if not ai_result.get("supported", False):
                reason = ai_result.get("reason", "Unsupported Resource Type")
                issues.append(f"BLOCKER: {reason}")

            if issues:
                report[res["id"]] = issues
        return report

    def _get_ai_assessment(self, res_type: str):
        """
        Retrieves assessment from cache or queries AI Service.
        """
        if res_type in self._type_cache:
            return self._type_cache[res_type]
        
        from services.ai_service import AIService
        try:
            ai = AIService()
            result = ai.assess_migration_readiness(res_type)
            self._type_cache[res_type] = result
            return result
        except Exception as e:
            # Fallback for AI failure (Rate Limit, etc.)
            return {
                "supported": False, 
                "reason": f"AI Assessment Unavailable: {str(e)}. Please check official documentation."
            }

    def _human_readable_type(self, res_type: str) -> str:
        """
        Converts 'Microsoft.Compute/virtualMachines' to 'Virtual Machine'.
        """
        if not res_type: return "Unknown"
        parts = res_type.split("/")
        if len(parts) > 1:
            # "virtualMachines" -> "Virtual Machines"
            # Simple heuristic: SplitCase or just return last part capitalized
            name = parts[-1]
            # Simple space insertion for camelCase if needed, but for now just capitalizing
            return name[0].upper() + name[1:]
        return res_type

    def _generate_remark(self, can_move: str, res_type: str, existing_issues: List[str] = None) -> tuple[str, str]:
        """
        Generates a standardized remark and potentially updates can_move.
        Returns (can_move, remark).
        """
        if can_move == "Yes":
            return "Yes", "This resource type supports for direct move operation."
        
        if existing_issues:
            # Check for "Unknown/No Doc" case in the issues
            combined_issues = " ".join(existing_issues).lower()
            if "no specific official documentation" in combined_issues:
                # User Requirement: Keep Blank if doc is not provided
                return "", ""

            # Check for Explicit "No" case or other blockers
            # User Requirement: If listed as No, put remark of not supported
            # We assume anything else is a valid blocker or explicit No
            return "No", "This resource type does not support move operation and will be recreated in the Destination Subscription with same configurations."
            
        return "", "" # Should not happen if can_move is No but no issues, but safe fallback

    def generate_detailed_report(self, resources: List[Dict[str, Any]], existing_blockers: Dict[str, List[str]] = None) -> List[Dict[str, Any]]:
        """
        Generates a flat list of dicts suitable for Excel export.
        Refined column order: Name, Type, Can be moved, Resource Type, RG, Loc, Sub, Remarks.
        """
        detailed_rows = []
        
        for res in resources:
            res_id = res.get("id")
            res_type_full = res.get("type", "")
            
            # Use stored assessment if available (Fast Path)
            if existing_blockers is not None:
                if res_id in existing_blockers:
                    initial_can_move = "No"
                    issues = existing_blockers[res_id]
                else:
                    initial_can_move = "Yes"
                    issues = []
            
            # Fallback to fresh assessment (Slow Path)
            else:
                instance_issues = self.check_resource(res)
                res_type_lower = res_type_full.lower()
                ai_result = self._get_ai_assessment(res_type_lower)
                is_supported = ai_result.get("supported", False)
                
                if instance_issues:
                    initial_can_move = "No"
                    issues = instance_issues
                elif not is_supported:
                    initial_can_move = "No"
                    # If AI said no, use that as an issue
                    issues = [ai_result.get("reason", "Unsupported Resource Type")]
                else:
                    initial_can_move = "Yes"
                    issues = []

            # Generate Standardized Remark & Final Move Status
            final_can_move, final_remarks = self._generate_remark(initial_can_move, res_type_full, issues)

            # Subscription Parsing
            try:
                subscription = res["id"].split("/")[2]
            except:
                subscription = "unknown"

            # Column Ordering: Name, Type, Can be moved, Resource Type, Resource Group, Location, Subscription, Remarks
            row = {
                "Name": res.get("name"),
                "Type": self._human_readable_type(res_type_full), # Short Type
                "Can be moved": final_can_move,
                "Resource Type": res_type_full, # Full Type
                "Resource Group": res.get("resource_group"),
                "Location": res.get("location"),
                "Subscription": subscription,
                "Remarks": final_remarks
            }
            detailed_rows.append(row)
        return detailed_rows
