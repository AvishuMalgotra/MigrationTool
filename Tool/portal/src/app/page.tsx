"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, ShieldCheck, Server, Globe, User, Trash2 } from "lucide-react";

interface SavedLogin {
  alias: string;
  tenantId: string;
  subId: string;
  mode: "auto" | "explicit";
  clientId?: string;
  clientSecret?: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState("tenant-demo-1");
  const [subId, setSubId] = useState("");
  const [alias, setAlias] = useState(""); // New Alias Field

  // Login Mode State
  const [loginMode, setLoginMode] = useState<"auto" | "explicit">("auto");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");

  const [savedLogins, setSavedLogins] = useState<SavedLogin[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem("azure_migration_logins");
    if (saved) {
      try {
        setSavedLogins(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse saved logins", e);
      }
    }
  }, []);

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();

    // Save Login if Alias is present
    if (alias.trim()) {
      const newLogin: SavedLogin = {
        alias: alias.trim(),
        tenantId,
        subId,
        mode: loginMode,
        clientId,
        clientSecret
      };

      // Check if alias exists, update it, otherwise add new
      const existingIndex = savedLogins.findIndex(l => l.alias === newLogin.alias);
      let updatedLogins = [...savedLogins];
      if (existingIndex >= 0) {
        updatedLogins[existingIndex] = newLogin;
      } else {
        updatedLogins.push(newLogin);
      }

      setSavedLogins(updatedLogins);
      localStorage.setItem("azure_migration_logins", JSON.stringify(updatedLogins));
    }

    // Pass credentials to Dashboard via Query Params 
    const params = new URLSearchParams({
      tenantId,
      subId,
      mode: loginMode,
      clientId: loginMode === "explicit" ? clientId : "",
      clientSecret: loginMode === "explicit" ? clientSecret : ""
    });

    router.push(`/dashboard?${params.toString()}`);
  };

  const loadLogin = (login: SavedLogin) => {
    setAlias(login.alias);
    setTenantId(login.tenantId);
    setSubId(login.subId);
    setLoginMode(login.mode);
    setClientId(login.clientId || "");
    setClientSecret(login.clientSecret || "");
  };

  const deleteLogin = (e: React.MouseEvent, targetAlias: string) => {
    e.stopPropagation();
    const filtered = savedLogins.filter(l => l.alias !== targetAlias);
    setSavedLogins(filtered);
    localStorage.setItem("azure_migration_logins", JSON.stringify(filtered));
  };

  return (
    <main className="flex min-h-screen bg-slate-50">
      {/* Left Side - Hero / Brandy */}
      <motion.div
        initial={{ opacity: 0, x: -50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.8 }}
        className="hidden lg:flex w-1/2 bg-blue-900 text-white flex-col justify-center px-16 relative overflow-hidden"
      >
        <div className="absolute top-0 left-0 w-full h-full bg-[url('/grid-pattern.svg')] opacity-10"></div>
        <div className="absolute -bottom-32 -left-32 w-96 h-96 bg-blue-500 rounded-full blur-3xl opacity-20"></div>

        <div className="z-10 relative">
          <div className="flex items-center space-x-3 mb-8">
            <Globe className="w-16 h-16 text-blue-300" />
            <span className="text-3xl font-bold tracking-widest uppercase text-blue-200">Migration Suite</span>
          </div>
          <h1 className="text-6xl font-extrabold leading-tight mb-8">
            Simplify Your <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-200 to-cyan-200">
              Azure Migration
            </span>
          </h1>
          <p className="text-2xl text-blue-100 max-w-lg leading-relaxed opacity-90">
            Enterprise-grade assessment, validation, and cross-subscription migration orchestration. Powered by AI.
          </p>

          <div className="mt-16 flex space-x-12 text-lg font-medium text-blue-200">
            <div className="flex items-center"><ShieldCheck className="w-8 h-8 mr-3" /> Secure</div>
            <div className="flex items-center"><Server className="w-8 h-8 mr-3" /> Reliable</div>
          </div>
        </div>
      </motion.div>

      {/* Right Side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-16 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="max-w-xl w-full"
        >
          <div className="mb-12">
            <h2 className="text-4xl font-extrabold text-slate-900">Connect to Azure</h2>
            <p className="text-xl text-slate-500 mt-3">Enter your environment details to begin.</p>
          </div>

          <form onSubmit={handleConnect} className="space-y-8">
            {/* Login Mode Tabs */}
            <div className="bg-slate-100 p-1.5 rounded-xl flex mb-8">
              <button
                type="button"
                onClick={() => setLoginMode("auto")}
                className={`flex-1 py-3 text-base font-semibold rounded-lg transition-all ${loginMode === "auto" ? "bg-white shadow-md text-blue-700" : "text-slate-500 hover:text-slate-700"}`}
              >
                CLI / Managed Identity
              </button>
              <button
                type="button"
                onClick={() => setLoginMode("explicit")}
                className={`flex-1 py-3 text-base font-semibold rounded-lg transition-all ${loginMode === "explicit" ? "bg-white shadow-md text-blue-700" : "text-slate-500 hover:text-slate-700"}`}
              >
                Service Principal
              </button>
            </div>

            <div className="grid grid-cols-1 gap-6">
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Tenant ID</label>
                <input
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  className="w-full p-4 text-lg border border-slate-300 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-600 outline-none transition"
                  placeholder="ex: 72f988bf-..."
                  required
                />
              </div>

              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">Target Subscription ID</label>
                <input
                  value={subId}
                  onChange={(e) => setSubId(e.target.value)}
                  className="w-full p-4 text-lg border border-slate-300 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-600 outline-none transition"
                  placeholder="ex: sub-123-abc..."
                  required
                />
              </div>

              {/* Alias Field */}
              <div>
                <label className="block text-base font-semibold text-slate-700 mb-2">
                  Save as Alias <span className="text-slate-400 font-normal text-sm ml-2">(Optional)</span>
                </label>
                <input
                  value={alias}
                  onChange={(e) => setAlias(e.target.value)}
                  className="w-full p-4 text-lg border border-slate-300 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-600 outline-none transition bg-slate-50"
                  placeholder="e.g. Production, Dev Environment..."
                />
              </div>
            </div>

            {loginMode === "explicit" && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="space-y-6 p-6 bg-slate-50 rounded-xl border border-slate-200"
              >
                <div>
                  <label className="block text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">Client ID</label>
                  <input
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    className="w-full p-3 border border-slate-300 rounded-lg text-base"
                    placeholder="App ID"
                  />
                </div>
                <div>
                  <label className="block text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">Client Secret</label>
                  <input
                    type="password"
                    value={clientSecret}
                    onChange={(e) => setClientSecret(e.target.value)}
                    className="w-full p-3 border border-slate-300 rounded-lg text-base"
                    placeholder="********"
                  />
                </div>
              </motion.div>
            )}

            <button
              type="submit"
              className="w-full py-5 bg-blue-600 hover:bg-blue-700 text-white text-xl font-bold rounded-xl shadow-xl shadow-blue-500/20 transition-all flex items-center justify-center gap-3 transform hover:scale-[1.02]"
            >
              Access Dashboard <ArrowRight className="w-6 h-6" />
            </button>
          </form>

          {/* Saved Logins Section */}
          {savedLogins.length > 0 && (
            <div className="mt-12 border-t border-slate-200 pt-8">
              <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                <User className="w-5 h-5 mr-2 text-blue-500" /> Saved Logins
              </h3>
              <div className="grid grid-cols-1 gap-3">
                {savedLogins.map((login, idx) => (
                  <div
                    key={idx}
                    onClick={() => loadLogin(login)}
                    className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-blue-300 hover:shadow-md cursor-pointer transition-all group"
                  >
                    <div>
                      <div className="font-bold text-slate-800">{login.alias}</div>
                      <div className="text-sm text-slate-500 font-mono">Tenant: {login.tenantId.substring(0, 8)}...</div>
                    </div>
                    <button
                      onClick={(e) => deleteLogin(e, login.alias)}
                      className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors"
                      title="Remove Saved Login"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="mt-12 text-center text-sm text-slate-400">
            Powered by Tech Plus Talent &copy; 2026
          </p>
        </motion.div>
      </div>
    </main>
  );
}
