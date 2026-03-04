"use client";

import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Download } from "lucide-react";

export default function Results({ status, patch, onReset }: { status: string; patch: string; onReset: () => void }) {
    const isSuccess = status === "completed";

    const downloadPatch = () => {
        if (!patch) return;
        const blob = new Blob([patch], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "fix.patch";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    return (
        <motion.div
            key="result"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="max-w-5xl mx-auto px-6 py-12"
        >
            <div className="text-center mb-12">
                {isSuccess ? (
                    <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto mb-4" />
                ) : (
                    <XCircle className="w-16 h-16 text-rose-500 mx-auto mb-4" />
                )}

                <h2 className="text-3xl font-bold mb-2">
                    {isSuccess ? "Issue Resolved" : "Fix Failed"}
                </h2>
                <p className="text-zinc-500 text-sm">
                    {isSuccess
                        ? "Successfully generated and verified patch"
                        : "Agent encountered an error or could not resolve the issue"}
                </p>
            </div>

            {isSuccess && patch && (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg overflow-hidden mb-8 backdrop-blur-sm">
                    <div className="bg-zinc-950/80 px-4 py-2 border-b border-zinc-800 flex justify-between items-center">
                        <span className="font-mono text-xs text-zinc-500">Generated Patch</span>
                        <span className="font-mono text-xs text-zinc-600">{patch.split('\n').length} lines</span>
                    </div>
                    <div className="p-4 font-mono text-xs overflow-x-auto max-h-96 overflow-y-auto">
                        <pre className="text-zinc-300 whitespace-pre-wrap">{patch}</pre>
                    </div>
                </div>
            )}

            <div className="flex gap-3">
                <button
                    onClick={onReset}
                    className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-white font-medium px-6 py-2.5 rounded-md border-t border-white/10 transition-all"
                >
                    New Session
                </button>
                {isSuccess && patch && (
                    <button
                        onClick={downloadPatch}
                        className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2.5 rounded-md border-t border-white/20 border-b border-blue-800 transition-all flex items-center justify-center gap-2"
                    >
                        <Download className="w-4 h-4" />
                        Download Patch
                    </button>
                )}
            </div>
        </motion.div>
    );
}
