const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AzureResource {
    id: string;
    name: string;
    type: string;
    location: string;
    resource_group: string;
    tags?: Record<string, string>;
    sku?: any;
    kind?: string;
}

export interface InventorySnapshot {
    subscription_id: string;
    tenant_id?: string;
    total_resources: number;
    resources: AzureResource[];
    resource_groups: { name: string; location: string }[];
    dependencies?: any[];
}

export interface AssessmentJob {
    id: string;
    tenant_id: string;
    status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED";
    inventory_snapshot?: InventorySnapshot;
    blockers?: Record<string, string[]>;
    ai_generated_summary?: string;
    created_at: string;
}

export interface MigrationPlan {
    id: string;
    job_id: string;
    status: string;
    execution_log?: any;
    ordered_batches?: any;
}

async function handleResponse(res: Response) {
    if (!res.ok) {
        let errorMsg = "Unknown error occurred";
        try {
            const errorData = await res.json();
            errorMsg = errorData.detail || errorData.message || JSON.stringify(errorData);
        } catch (e) {
            errorMsg = res.statusText;
        }
        throw new Error(errorMsg);
    }
    return res.json();
}

export const api = {
    async triggerAssessment(tenantId: string, subscriptionId: string, clientId?: string, clientSecret?: string): Promise<{ job_id: string }> {
        const payload: any = { tenant_id: tenantId, subscription_id: subscriptionId };
        if (clientId && clientSecret) {
            payload.client_id = clientId;
            payload.client_secret = clientSecret;
        }

        const res = await fetch(`${API_URL}/api/v1/assess`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        return handleResponse(res);
    },

    async getJobStatus(jobId: string): Promise<AssessmentJob> {
        const res = await fetch(`${API_URL}/api/v1/jobs/${jobId}`);
        return handleResponse(res);
    },

    async triggerMigration(jobId: string, sourceRg: string, targetRgId: string, resources: string[]): Promise<{ plan_id: string }> {
        const res = await fetch(`${API_URL}/api/v1/migrate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                job_id: jobId,
                source_resource_group: sourceRg,
                target_resource_group_id: targetRgId,
                resources: resources
            })
        });
        return handleResponse(res);
    },

    async getMigrationPlan(planId: string): Promise<MigrationPlan> {
        const res = await fetch(`${API_URL}/api/v1/plans/${planId}`);
        return handleResponse(res);
    },

    getExportUrl(jobId: string): string {
        return `${API_URL}/api/v1/jobs/${jobId}/export`;
    },

    getARMExportUrl(jobId: string): string {
        return `${API_URL}/api/v1/jobs/${jobId}/export/arm`;
    }
};
