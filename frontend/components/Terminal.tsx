"use client";

import { useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Terminal as TerminalIcon } from "lucide-react";

export default function Terminal({ logs }: { logs: string[] }) {
    const terminalRef = useRef<HTMLDivElement>(null);

    // auto-scroll to bottom when new logs come in
    useEffect(() => {
        if (terminalRef.current) {
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
    }, [logs]);

    const getLogColor = (log: string) => {
        if (log?.includes("✓")) return "text-emerald-400";
        if (log?.includes("[ERROR]")) return "text-rose-400";
        if (log?.includes("[FIX]")) return "text-amber-400";
        return "text-zinc-400";
    };

    return (
        <div className="col-span-9 bg-zinc-900/50 border border-zinc-800 rounded-lg overflow-hidden flex flex-col backdrop-blur-sm">
            <div className="bg-zinc-950/80 px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                <TerminalIcon className="w-3.5 h-3.5 text-zinc-500" />
                <span className="font-mono text-xs text-zinc-500">TERMINAL</span>
                <div className="flex gap-1.5 ml-auto">
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                </div>
            </div>

            <div
                ref={terminalRef}
                className="flex-1 p-4 overflow-auto bg-black font-mono text-xs leading-relaxed"
            >
                {logs.map((log, i) => (
                    <div key={i} className="mb-1.5 terminal-line">
                        <span className="text-zinc-600">&gt; </span>
                        <span className={getLogColor(log)}>{log}</span>
                    </div>
                ))}

                {/* blinking cursor */}
                <motion.div
                    animate={{ opacity: [1, 0] }}
                    transition={{ repeat: Infinity, duration: 1 }}
                    className="inline-block w-1.5 h-3.5 bg-blue-500 ml-1"
                />
            </div>
        </div>
    );
}
