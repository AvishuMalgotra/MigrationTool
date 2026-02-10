# Azure Migration Agent - Operator Guide

This guide provides step-by-step instructions for assessing and migrating Azure resources using the Migration Agent.

## 1. Initial Setup

### A. Azure Permissions
To run an assessment, the Service Principal used by the application requires:
- **Reader** role on the Target Subscription(s).
- **Reader** role on the Tenant (for resolving graph info, optional but recommended).

To execute a migration (Phase 2), it requires:
- **Contributor** or **Owner** on both Source and Destination Subscriptions.
- **User Access Administrator** (if moving role assignments).

### B. Application Startup
1. **Backend**:
   ```bash
   cd backend
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   uvicorn main:app --reload --port 8000
   ```
   *Verify health at: http://localhost:8000/health*

2. **Frontend**:
   ```bash
   cd portal
   npm run dev
   ```
   *Access dashboard at: http://localhost:3000*

## 2. Running an Assessment

1. Navigate to the **Dashboard** (http://localhost:3000).
2. Click **"New Assessment"**.
3. Enter the **Target Subscription ID** you wish to scan.
   - *Optional*: You can override the Tenant ID if working cross-tenant.
4. Click **"Start Assessment"**.
5. The job will enter `PENDING` state and move to `COMPLETED` once the inventory scan and AI analysis are finished (approx. 30-90 seconds).

## 3. Interpreting Results

### Dashboard Overview
- **Total Resources**: Count of all scanned resources.
- **Ready to Move**: Resources that passed all compatibility checks.
- **Attention Needed**: Resources with identified blockers (locks, unsupported types, SKU mismatches).
- **Key Info**: Click the "Key Info" text to view Azure Advisor scores and Subscription details.

### Reviewing Blockers
The dashboard lists specific blocking reasons, for example:
- *"Resource type Microsoft.ClassicCompute/virtualMachines not supported."*
- *"Resource has a CanNotDelete lock."*

## 4. Exporting Reports

### Excel Report
Click **"Excel Report"** to download a detailed spreadsheet (`Assessment_Report_{id}.xlsx`).
- **Cover Page**: Executive summary and scores.
- **Resource Impact**: Detailed list of all resources with "Move Status" (Yes/No).
- **Blockers**: Filtered list of problematic resources.

### ARM Templates (For Blocked Resources)
If resources cannot be moved directly, you can re-create them.
1. Click **"Export ARM Templates (Zip)"**.
2. Extract the downloaded ZIP file.
3. You will find standard Azure Resource Manager (ARM) JSON templates for each blocked resource, ready for deployment to the new region/subscription.

## 5. Troubleshooting

### "Authentication Failed"
- Check `backend/.env` credentials.
- Ensure the Service Principal secret hasn't expired.
- Verify the Service Principal has `Reader` access to the subscription.

### "Migration Trigger Failed"
- This feature is currently in **Validation Mode**.
- Ensure you have `Contributor` rights if attempting a real move.

### "AI Service Unavailable"
- Check the `AZURE_OPENAI_ENDPOINT` and Key in `.env`.
- If using Google Gemini, ensure the API key is active.
