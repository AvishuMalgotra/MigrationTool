"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, AssessmentJob, AzureResource } from "@/lib/api";
import InventoryTable from "@/components/InventoryTable";

export default function JobPage() {
    const params = useParams();
    const id = params?.id as string;
    const [job, setJob] = useState<AssessmentJob | null>(null);
    const [loading, setLoading] = useState(true);
    const [migrating, setMigrating] = useState(false);
    const [planId, setPlanId] = useState<string | null>(null);
    const [exportingARM, setExportingARM] = useState(false);

    // Poll Job Status
    useEffect(() => {
        // ... (Keep existing fetchJob logic)
        if (!id) return;
        const fetchJob = async () => {
            try {
                const data = await api.getJobStatus(id);
                setJob(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchJob();
        const interval = setInterval(fetchJob, 3000);
        return () => clearInterval(interval);
    }, [id]);

    const handleMigrate = async () => {
        if (!job || !job.inventory_snapshot) return;
        setMigrating(true);
        try {
            const resources = job.inventory_snapshot.resources.map((r: any) => r.id);
            const sourceRg = job.inventory_snapshot.resource_groups[0]?.name || "default";
            const targetSub = job.inventory_snapshot.subscription_id;
            const targetRgId = `/subscriptions/${targetSub}/resourceGroups/${sourceRg}-migrated`;

            const data = await api.triggerMigration(job.id, sourceRg, targetRgId, resources);
            setPlanId(data.plan_id);

        } catch (err: any) {
            alert(`Migration trigger failed: ${err.message}`);
            setMigrating(false);
        }
    };

    const handleARMExport = async (e: React.MouseEvent) => {
        e.preventDefault();
        setExportingARM(true);
        // Simulate "Preparing" if synchronous, or actual fetch if we move to async later.
        // For now, we just redirect after a small UI feedback delay if it's instant, 
        // OR we fetch blob manually to show progress. Use Manual Fetch for UX.
        try {
            const response = await fetch(api.getARMExportUrl(job!.id));
            if (!response.ok) throw new Error("Export failed");

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Blocked_Resources_Templates_${job!.id}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err) {
            alert("Failed to download ARM templates.");
        } finally {
            setExportingARM(false);
        }
    };

    if (loading) return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        </div>
    );

    if (!job) return <div className="p-24 text-center text-red-500">Job not found</div>;

    const totalResources = job.inventory_snapshot?.total_resources || 0;
    const resourceGroups = job.inventory_snapshot?.resource_groups?.length || 0;
    const blockersCount = job.blockers ? Object.keys(job.blockers).length : 0;
    const readyCount = totalResources - blockersCount;

    const getStatusColor = (status: string) => {
        if (status === "COMPLETED") return "text-green-600";
        if (status === "FAILED") return "text-red-600";
        return "text-yellow-600";
    };

    return (
        <main className="min-h-screen bg-gray-50 pb-20">
            {/* Header */}
            <div className="bg-white border-b shadow-sm">
                <div className="max-w-7xl mx-auto px-6 py-6 flex justify-between items-center">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <a href="/dashboard" className="text-gray-400 hover:text-indigo-600 transition-colors">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                                </svg>
                            </a>
                            <h1 className="text-2xl font-bold text-gray-900">Assessment Dashboard</h1>
                        </div>
                        <p className="text-sm text-gray-500 font-mono ml-7">ID: {job.id}</p>
                    </div>
                    <div className="flex gap-3">
                        {job.status === "COMPLETED" && (
                            <a
                                href={api.getExportUrl(job.id)}
                                className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                            >
                                <svg className="-ml-1 mr-2 h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                Excel Report
                            </a>
                        )}
                        {job.status === "COMPLETED" && (
                            <button
                                onClick={handleARMExport}
                                disabled={exportingARM}
                                className={`inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-blue-700 bg-white hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${exportingARM ? 'opacity-75 cursor-not-allowed' : ''}`}
                            >
                                {exportingARM ? (
                                    <>
                                        <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <svg className="-ml-1 mr-2 h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                        </svg>
                                        Export ARM Templates (Zip)
                                    </>
                                )}
                            </button>
                        )}
                        {job.status === "COMPLETED" && !planId && (
                            <button
                                onClick={handleMigrate}
                                disabled={migrating}
                                className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                            >
                                {migrating ? "Starting..." : "Start Migration"}
                            </button>
                        )}
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-6 py-8">
                {/* Status Overview */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                        <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Status</p>
                        <p className={`text-2xl font-bold mt-2 ${getStatusColor(job.status)}`}>
                            {job.status}
                        </p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                        <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Total Resources</p>
                        <p className="text-3xl font-bold mt-2 text-gray-900">{totalResources}</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                        <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Ready to Move</p>
                        <p className="text-3xl font-bold mt-2 text-indigo-600">{readyCount}</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                        <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Attention Needed</p>
                        <p className={`text-3xl font-bold mt-2 ${blockersCount > 0 ? "text-red-600" : "text-gray-400"}`}>
                            {blockersCount}
                        </p>
                    </div>
                </div>

                {/* Compatibility Block */}
                {blockersCount > 0 && (
                    <div className="bg-white rounded-xl shadow-sm border border-red-100 mb-8 overflow-hidden">
                        <div className="px-6 py-4 border-b border-red-100 bg-red-50">
                            <h3 className="text-lg font-medium text-red-800">Compatibility Issues Detected</h3>
                        </div>
                        <div className="p-6">
                            <div className="bg-red-50 rounded-lg p-4 font-mono text-sm text-red-800 whitespace-pre-wrap">
                                {JSON.stringify(job.blockers, null, 2)}
                            </div>
                        </div>
                    </div>
                )}

                {/* Detailed Inventory Table */}
                {job.inventory_snapshot && (
                    <InventoryTable
                        resources={job.inventory_snapshot.resources}
                        blockers={job.blockers || {}}
                    />
                )}
            </div>
        </main>
    );
}
