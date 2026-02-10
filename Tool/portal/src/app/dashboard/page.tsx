"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, Suspense, useEffect } from "react";
import { motion } from "framer-motion";
import {
    FileSearch,
    ArrowRightLeft,
    Lightbulb,
    ChevronRight,
    Activity,
    LayoutDashboard
} from "lucide-react";
import { api } from "@/lib/api";

function DashboardContent() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const tenantId = searchParams.get("tenantId") || "";
    const subId = searchParams.get("subId") || "";
    const loginMode = searchParams.get("mode") || "auto";
    const clientId = searchParams.get("clientId") || "";
    const clientSecret = searchParams.get("clientSecret") || "";

    const [loadingAction, setLoadingAction] = useState<string | null>(null);

    const handleAssessment = async () => {
        setLoadingAction("assessment");
        try {
            // Re-using the same API trigger logic
            const data = await api.triggerAssessment(
                tenantId,
                subId,
                loginMode === "explicit" ? clientId : undefined,
                loginMode === "explicit" ? clientSecret : undefined
            );
            router.push(`/jobs/${data.job_id}`);
        } catch (err) {
            alert("Failed to trigger assessment. Check console.");
            console.error(err);
            setLoadingAction(null);
        }
    };

    const [showKeyInfo, setShowKeyInfo] = useState(false);
    const [keyInfo, setKeyInfo] = useState<any>(null);
    const [loadingKeyInfo, setLoadingKeyInfo] = useState(false);

    const loadKeyInfo = async () => {
        setLoadingKeyInfo(true);
        try {
            // Use current URL params via props or scope if available, else from searchParams
            // Note: subId and tenantId are available in scope
            const res = await fetch(`http://localhost:8000/api/v1/context?subscription_id=${subId}&tenant_id=${tenantId}`);
            if (res.ok) {
                const data = await res.json();
                setKeyInfo(data);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoadingKeyInfo(false);
        }
    };

    const handleMigration = () => {
        alert("Migration Wizard coming soon! (Phase 3)");
    };

    const handleInsights = () => {
        setShowKeyInfo(true);
        loadKeyInfo();
    };

    const OptionCard = ({
        title,
        desc,
        icon: Icon,
        color,
        onClick,
        isLoading
    }: {
        title: string;
        desc: string;
        icon: any;
        color: string;
        onClick: () => void;
        isLoading?: boolean;
    }) => (
        <motion.div
            whileHover={{ y: -5, boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)" }}
            whileTap={{ scale: 0.98 }}
            onClick={onClick}
            className={`bg-white p-6 rounded-2xl shadow-lg border border-slate-100 cursor-pointer relative overflow-hidden group h-full flex flex-col`}
        >
            <div className={`absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
                <Icon className="w-24 h-24" />
            </div>

            <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 text-white ${color} shadow-lg`}>
                {isLoading ? <Activity className="w-6 h-6 animate-spin" /> : <Icon className="w-6 h-6" />}
            </div>

            <h3 className="text-lg font-bold text-slate-800 mb-2 group-hover:text-blue-600 transition-colors">
                {title}
            </h3>
            <p className="text-slate-500 text-sm leading-relaxed mb-6 flex-grow">
                {desc}
            </p>

            <div className="flex items-center text-sm font-semibold text-blue-600 opacity-0 group-hover:opacity-100 transition-all transform translate-x-[-10px] group-hover:translate-x-0">
                Start Now <ChevronRight className="w-4 h-4 ml-1" />
            </div>
        </motion.div>
    );



    const KeyInfoModal = () => {
        if (!showKeyInfo) return null;
        return (
            <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="bg-white rounded-2xl max-w-2xl w-full p-8 shadow-2xl relative"
                >
                    <button
                        onClick={() => setShowKeyInfo(false)}
                        className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
                    >
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>

                    <div className="flex items-center gap-3 mb-6">
                        <div className="bg-amber-100 p-3 rounded-xl">
                            <Lightbulb className="w-8 h-8 text-amber-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-gray-900">Key Information</h2>
                    </div>

                    {loadingKeyInfo ? (
                        <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                            <Activity className="w-10 h-10 animate-spin mb-4 text-amber-500" />
                            <p>Analyzing Azure Environment via Advisor...</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <InfoItem label="Tenant Name" value={keyInfo?.tenant_name || "Standard Tenant"} />
                            <InfoItem label="Tenant ID" value={keyInfo?.tenant_id || tenantId} />
                            <InfoItem label="Subscription ID" value={keyInfo?.subscription_id || subId} />
                            <InfoItem label="Subscription Plan" value={keyInfo?.subscription_plan || "Loading..."} />
                            <InfoItem label="Cost Score (Advisor)" value={keyInfo?.cost_score || "-"} highlight={keyInfo?.cost_score?.includes("$")} />
                            <InfoItem label="Secure Score (Advisor)" value={keyInfo?.secure_score || "-"} />
                            <InfoItem label="Current Access" value={keyInfo?.current_access || "Owner"} />
                            <InfoItem label="Resource Count" value={keyInfo?.resource_count || "-"} />
                        </div>
                    )}

                    <div className="mt-8 flex justify-end">
                        <button
                            onClick={() => setShowKeyInfo(false)}
                            className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-6 py-2 rounded-lg font-medium transition-colors"
                        >
                            Close
                        </button>
                    </div>
                </motion.div>
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Top Navigation */}
            <header className="bg-white shadow-sm border-b border-slate-200 sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">

                    {/* Left: Branding & Status */}
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-3">
                            <div className="bg-blue-600 p-2.5 rounded-xl shadow-lg shadow-blue-600/20">
                                <LayoutDashboard className="w-6 h-6 text-white" />
                            </div>
                            <span className="font-extrabold text-slate-800 text-2xl tracking-tight">Azure Migration Tool</span>
                        </div>

                        <div className="hidden md:block h-8 w-px bg-slate-200 mx-2"></div>
                        <AIStatusIndicator />
                    </div>

                    {/* Right: Context Info */}
                    <div className="hidden md:flex items-center gap-4 text-sm font-medium">
                        <div className="flex flex-col items-end">
                            <div className="flex items-center text-slate-500">
                                <span className="mr-2 text-xs uppercase tracking-wider font-bold text-slate-400">Tenant</span>
                                <span className="font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 transition-colors hover:border-blue-300">
                                    {tenantId || "Unknown"}
                                </span>
                            </div>
                            <div className="flex items-center text-slate-500 mt-1">
                                <span className="mr-2 text-xs uppercase tracking-wider font-bold text-slate-400">Subscription</span>
                                <span className="font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 transition-colors hover:border-blue-300">
                                    {subId || "Not Selected"}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
                <div className="text-center mb-16">
                    <motion.h1
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-4xl font-extrabold text-slate-900 mb-4"
                    >
                        What would you like to do today?
                    </motion.h1>
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.1 }}
                        className="text-lg text-slate-500 max-w-3xl mx-auto leading-relaxed"
                    >
                        Select a workflow to begin managing your Azure environment.
                    </motion.p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <motion.div className="h-full" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
                        <OptionCard
                            title="Prepare Assessment Report"
                            desc="Deep scan and analysis of resources for cross-subscription migration compatibility. Powered by AI validation."
                            icon={FileSearch}
                            color="bg-blue-600"
                            onClick={handleAssessment}
                            isLoading={loadingAction === "assessment"}
                        />
                    </motion.div>

                    <motion.div className="h-full" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                        <OptionCard
                            title="Start Migration"
                            desc="Orchestrate the move of validated resources. Includes dry-runs, dependency handling, and rollback safety."
                            icon={ArrowRightLeft}
                            color="bg-purple-600"
                            onClick={handleMigration}
                        />
                    </motion.div>

                    <motion.div className="h-full" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
                        <OptionCard
                            title="Key Information"
                            desc="Get instant insights about your environment's health, blockers, and migration readiness score."
                            icon={Lightbulb}
                            color="bg-amber-500"
                            onClick={handleInsights}
                        />
                    </motion.div>
                </div>
            </main>

            <KeyInfoModal />
        </div>
    );
}

function AIStatusIndicator() {
    const [status, setStatus] = useState<"checking" | "success" | "failed">("checking");

    useEffect(() => {
        const checkStatus = () => {
            fetch("http://localhost:8000/api/ai-status")
                .then(res => {
                    if (!res.ok) throw new Error("Endpoint unreachable");
                    return res.json();
                })
                .then(data => setStatus(data.connected ? "success" : "failed"))
                .catch(err => {
                    console.error("AI Status Check Failed:", err);
                    setStatus("failed");
                });
        };

        checkStatus();
        // Optional: Poll every 30s
        const interval = setInterval(checkStatus, 30000);
        return () => clearInterval(interval);
    }, []);

    const config = {
        checking: { color: "bg-slate-100 text-slate-600 border-slate-200", dot: "bg-slate-400 animate-pulse", text: "Checking AI..." },
        success: { color: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500", text: "AI Online" },
        failed: { color: "bg-rose-50 text-rose-700 border-rose-200", dot: "bg-rose-500", text: "AI Offline" }
    };

    const current = config[status];

    return (
        <div className={`flex items-center px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border transition-all shadow-sm ${current.color}`}>
            <span className={`w-2 h-2 rounded-full mr-2 ${current.dot}`}></span>
            {current.text}
        </div>
    );
}



const InfoItem = ({ label, value, highlight }: any) => (
    <div className="flex justify-between items-center bg-gray-50 p-3 rounded-lg border border-gray-100 h-12">
        <span className="text-sm font-medium text-gray-500 whitespace-nowrap mr-4">{label}</span>
        <span className={`text-sm font-bold truncate ${highlight ? 'text-green-600' : 'text-gray-800'}`} title={value}>
            {value}
        </span>
    </div>
);

export default function Dashboard() {
    return (
        <Suspense fallback={<div>Loading Dashboard...</div>}>
            <DashboardContent />
        </Suspense>
    );
}
