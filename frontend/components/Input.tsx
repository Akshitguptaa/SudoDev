"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Rocket, Loader2, Github, Database, Monitor } from "lucide-react";

type InputMode = "swebench" | "github" | null;

interface InputProps {
    mode: InputMode;
    setMode: (mode: InputMode) => void;
    instanceId: string;
    setInstanceId: (id: string) => void;
    githubRepoUrl: string;
    setGithubRepoUrl: (url: string) => void;
    githubIssueUrl: string;
    setGithubIssueUrl: (url: string) => void;
    context: string;
    setContext: (ctx: string) => void;
    loading: boolean;
    onSubmit: (e: React.FormEvent) => void;
    onOpenIDE?: () => void;
    ideLoading?: boolean;
}

export default function Input({
    mode,
    setMode,
    instanceId,
    setInstanceId,
    githubRepoUrl,
    setGithubRepoUrl,
    githubIssueUrl,
    setGithubIssueUrl,
    context,
    setContext,
    loading,
    onSubmit,
    onOpenIDE,
    ideLoading,
}: InputProps) {
    const handleModeSelect = (selectedMode: InputMode) => {
        setMode(selectedMode);
        // Reset fields when switching modes
        setInstanceId("");
        setGithubRepoUrl("");
        setGithubIssueUrl("");
        setContext("");
    };

    return (
        <motion.div
            key="input"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center min-h-[calc(100vh-120px)] px-6"
        >
            <div className="max-w-2xl w-full">
                <div className="text-center mb-10">
                    <h2 className="text-4xl font-bold mb-3">Deploy AI Agent</h2>
                    <p className="text-zinc-500">
                        Choose your source and let the agent fix it automatically
                    </p>
                </div>

                <AnimatePresence mode="wait">
                    {!mode ? (
                        <motion.div
                            key="mode-selection"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="grid grid-cols-2 gap-4"
                        >
                            <button
                                onClick={() => handleModeSelect("swebench")}
                                className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-8 hover:border-blue-500 hover:bg-zinc-900/70 transition-all group"
                            >
                                <Database className="w-12 h-12 text-zinc-600 group-hover:text-blue-500 mx-auto mb-4 transition-colors" />
                                <h3 className="text-lg font-semibold mb-2">SWE-bench</h3>
                                <p className="text-sm text-zinc-500">
                                    Use instance IDs from the SWE-bench dataset
                                </p>
                            </button>

                            <button
                                onClick={() => handleModeSelect("github")}
                                className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-8 hover:border-blue-500 hover:bg-zinc-900/70 transition-all group"
                            >
                                <Github className="w-12 h-12 text-zinc-600 group-hover:text-blue-500 mx-auto mb-4 transition-colors" />
                                <h3 className="text-lg font-semibold mb-2">GitHub</h3>
                                <p className="text-sm text-zinc-500">
                                    Use repository and issue URLs from GitHub
                                </p>
                            </button>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="input-form"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-8 backdrop-blur-sm"
                        >
                            <div className="flex items-center justify-between mb-6">
                                <div className="flex items-center gap-3">
                                    {mode === "swebench" ? (
                                        <Database className="w-5 h-5 text-blue-500" />
                                    ) : (
                                        <Github className="w-5 h-5 text-blue-500" />
                                    )}
                                    <span className="text-sm font-medium text-zinc-400">
                                        {mode === "swebench" ? "SWE-bench Mode" : "GitHub Mode"}
                                    </span>
                                </div>
                                <button
                                    onClick={() => handleModeSelect(null)}
                                    className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                                >
                                    Change Mode
                                </button>
                            </div>

                            <form onSubmit={onSubmit} className="space-y-6">
                                {mode === "swebench" ? (
                                    <div>
                                        <label className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2 block">
                                            Instance ID
                                        </label>
                                        <input
                                            type="text"
                                            value={instanceId}
                                            onChange={(e) => setInstanceId(e.target.value)}
                                            placeholder="django__django-11001"
                                            required
                                            className="w-full bg-black/50 border border-zinc-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-zinc-200 font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                                        />
                                        <p className="text-xs text-zinc-600 mt-2">
                                            Issue descriptions are loaded from SWE-bench dataset
                                        </p>
                                    </div>
                                ) : (
                                    <>
                                        <div>
                                            <label className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2 block">
                                                GitHub Issue URL
                                            </label>
                                            <input
                                                type="url"
                                                value={githubIssueUrl}
                                                onChange={(e) => setGithubIssueUrl(e.target.value)}
                                                placeholder="https://github.com/owner/repo/issues/123"
                                                required
                                                className="w-full bg-black/50 border border-zinc-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-zinc-200 font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                                            />
                                            <p className="text-xs text-zinc-600 mt-2">
                                                Repository URL is auto-extracted from the issue URL
                                            </p>
                                        </div>

                                        <div>
                                            <label className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2 block">
                                                Repository URL (Optional)
                                            </label>
                                            <input
                                                type="url"
                                                value={githubRepoUrl}
                                                onChange={(e) => setGithubRepoUrl(e.target.value)}
                                                placeholder="https://github.com/owner/repo"
                                                className="w-full bg-black/50 border border-zinc-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-zinc-200 font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                                            />
                                            <p className="text-xs text-zinc-600 mt-2">
                                                Override if repo URL differs from issue URL
                                            </p>
                                        </div>
                                    </>
                                )}

                                <div>
                                    <label className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2 block">
                                        Additional Context (Optional)
                                    </label>
                                    <p className="text-xs text-zinc-600 mb-2">
                                        {mode === "swebench"
                                            ? "Issue descriptions are loaded from SWE-bench. Add extra context here if needed."
                                            : "Provide additional context or specific instructions for the agent."
                                        }
                                    </p>
                                    <textarea
                                        value={context}
                                        onChange={(e) => setContext(e.target.value)}
                                        placeholder="Optional: Provide additional context or specific instructions..."
                                        rows={5}
                                        className="w-full bg-black/50 border border-zinc-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-zinc-200 font-mono text-sm rounded px-3 py-2 outline-none transition-colors resize-none"
                                    />
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <button
                                        type="submit"
                                        disabled={loading || ideLoading}
                                        className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-3 rounded-md border-t border-white-20 border-b border-blue-800 transition-all active:scale-95 disabled:opacity-50"
                                    >
                                        <span className="flex items-center justify-center gap-2">
                                            {loading ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                    Deploying...
                                                </>
                                            ) : (
                                                <>
                                                    <Rocket className="w-4 h-4" />
                                                    Deploy Agent
                                                </>
                                            )}
                                        </span>
                                    </button>

                                    <button
                                        type="button"
                                        disabled={loading || ideLoading}
                                        onClick={onOpenIDE}
                                        className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-6 py-3 rounded-md border-t border-white-20 border-b border-emerald-800 transition-all active:scale-95 disabled:opacity-50"
                                    >
                                        <span className="flex items-center justify-center gap-2">
                                            {ideLoading ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                    Opening IDE...
                                                </>
                                            ) : (
                                                <>
                                                    <Monitor className="w-4 h-4" />
                                                    Open in IDE
                                                </>
                                            )}
                                        </span>
                                    </button>
                                </div>
                            </form>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
}