from typing import Dict, Any, List
import json
import logging
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # Support for Azure OpenAI
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        
        # Support for Generic OpenAI Compatible (Groq, DeepSeek, Official OpenAI)
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL") 
        self.openai_model = os.getenv("OPENAI_MODEL") or os.getenv("GROQ_MODEL") or os.getenv("GEMINI_MODEL") or "gpt-4o"

        self.client = None
        self.provider = "mock"
        
        # 1. Try Generic OpenAI Client (Priority for Flexibility)
        if self.openai_api_key:
            from openai import OpenAI
            
            # Auto-detect base_url for known providers if not explicitly set
            if not self.openai_base_url:
                if os.getenv("GROQ_API_KEY"):
                    self.openai_base_url = "https://api.groq.com/openai/v1"
                    self.provider = "groq"
                    if not self.openai_model: self.openai_model = "llama-3.3-70b-versatile"
                elif os.getenv("GEMINI_API_KEY"):
                    self.openai_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                    self.provider = "gemini"
            else:
                 self.provider = "openai-generic"

            self.client = OpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url # can be None (defaults to official)
            )
            
            # Fallback provider name if official
            if self.provider == "mock" and not self.openai_base_url:
                self.provider = "openai"

            # Clean model name for Gemini if used via this path
            if self.provider == "gemini" and self.openai_model.startswith("models/"):
                 self.openai_model = self.openai_model.replace("models/", "")
                 
            logger.info(f"AIService initialized. Provider: {self.provider}")
            logger.info(f" > Model: {self.openai_model}")
            logger.info(f" > Base URL: {self.openai_base_url or 'Default (OpenAI)'}")

        # 2. Try Azure OpenAI (Legacy/Enterprise)
        elif self.azure_api_key and self.azure_endpoint:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=self.azure_api_key,
                api_version="2023-05-15",
                azure_endpoint=self.azure_endpoint
            )
            self.provider = "azure"
            logger.info("AIService initialized with Azure OpenAI.")
        
        else:
             logger.warning("AIService running in MOCK mode.")

    def generate_report(self, inventory: Dict[str, Any], blockers: Dict[str, List[str]] = None) -> str:
        """
        Generates a markdown report by analyzing the inventory and blockers.
        Acts as a bridge to the LLM.
        """
        # ... (Sanitization logic remains same)
        
        resource_counts = {}
        for r in inventory.get("resources", []):
            rtype = r["type"].split("/")[-1] # Simplification
            resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

        summary_data = {
            "total_resources": inventory["total_resources"],
            "resource_distribution": resource_counts,
            "blocker_count": len(blockers) if blockers else 0
        }

        # Prompt Construction
        system_prompt = """
        You are an Azure Migration Architect. 
        Your goal is to analyze the provided infrastructure summary and blocking issues.
        Generate a professional Markdown report.
        
        Structure:
        # Executive Summary
        # Infrastructure Overview
        # Critical Issues (Explain why the blockers prevent migration)
        # Recommended Strategy (Give a sequence of moves)
        """
        
        user_prompt = f"""
        Data:
        {json.dumps(summary_data, indent=2)}
        
        Blocking Issues:
        {json.dumps(blockers, indent=2) if blockers else "None"}
        """
        
        if blockers:
             user_prompt += "\nExplain the risks of Classic resources and Management Locks."

        logger.info(f"Sending prompt to AI Engine ({self.provider})...")
        
        if self.client:
            try:
                # Determine model based on provider
                model = self.azure_deployment if self.provider == "azure" else self.openai_model
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"AI Generation Failed: {e}")
                return self._mock_llm_response(summary_data, blockers)
        else:
            return self._mock_llm_response(summary_data, blockers)

    async def check_health(self) -> bool:
        """
        Verifies if the AI service is reachable and working.
        """
        if not self.client:
            return False
        try:
            # Unified Health Check
            model = self.azure_deployment if self.provider == "azure" else self.openai_model

            self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"AI Health Check Failed: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def assess_migration_readiness(self, resource_type: str) -> Dict[str, Any]:
        """
        Asks the AI if a specific resource type supports migration.
        """
        if not self.client:
             return {"supported": False, "reason": "AI Connection Failed"}

        # 1. Retrieve Context
        rt_lower = resource_type.lower()
        context_str = "No specific official documentation found for this type."
        
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "move-support-resources.csv")
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    import csv
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("Resource", "").strip().lower() == rt_lower:
                            move_sub = row.get("Move Subscription", "0").strip()
                            context_str = f"Official Documentation Data: Resource='{row.get('Resource')}', MoveSubscriptionSupport='{'Yes' if move_sub == '1' else 'No'}'."
                            break
            except Exception:
                pass

        # 2. AI Decision
        prompt = f"""
        Resource Type: '{resource_type}'
        Context: {context_str}
        
        Task: 
        1. Analyze the Context.
        2. If Context says 'Yes', return supported=true.
        3. If Context says 'No', return supported=false.
        4. If Context is missing, use your internal Azure knowledge to decide.
        
        Reply JSON only: {{"supported": true/false, "reason": "logic used"}}
        """
        
        try:
            # Determine model based on provider
            model = self.azure_deployment if self.provider == "azure" else self.openai_model

            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an Azure Migration Evaluator. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            content = response.choices[0].message.content

            # Clean Markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                 content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"AI assessment error: {e}")
            raise e

    def _mock_llm_response(self, summary_data: Dict, blockers: Dict) -> str:
        """
        Simulates the LLM output based on input data.
        """
        md = "# Executive Summary\n"
        md += f"The assessment found **{summary_data['total_resources']} resources** eligible for analysis.\n"
        
        if summary_data['blocker_count'] > 0:
            md += f"⚠️ **{summary_data['blocker_count']} logic blockers** were identified that prevent immediate migration.\n\n"
        else:
            md += "✅ No critical blocking issues were found. The environment appears ready for migration.\n\n"

        md += "## Infrastructure Overview\n"
        for k, v in summary_data['resource_distribution'].items():
            md += f"- **{k}**: {v}\n"
        
        md += "\n## Critical Issues\n"
        if blockers:
            for res_id, issues in blockers.items():
                short_id = res_id.split("/")[-1]
                md += f"### {short_id}\n"
                for issue in issues:
                    md += f"- 🔴 {issue}\n"
                md += "\n"
        else:
            md += "No critical issues detected.\n"

        md += "\n## Recommended Strategy\n"
        md += "1. **Preparation**: Backup configuration of all Network Interfaces.\n"
        if "virtualMachines" in summary_data['resource_distribution']:
             md += "2. **Compute**: VMs should be stopped during the move to ensure data consistency.\n"
        md += "3. **Execution**: Use the Migration Agent's 'Validate Move' before final execution.\n"
        
        return md
