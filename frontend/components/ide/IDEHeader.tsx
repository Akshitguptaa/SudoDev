"use client";

import { motion } from "framer-motion";
import {
    ArrowLeft,
    Square,
    Play,
    Monitor,
    Wifi,
    WifiOff,
    Loader2,
    GitBranch,
} from "lucide-react";

interface IDEHeaderProps {
    sessionId: string;
    mode: string;
    instanceId?: string;
    githubUrl?: string;
    status: string;
    onStop: () => void;
    onBack: () => void;
    stopping: boolean;
}

export default function IDEHeader({
    sessionId,
    mode,
    instanceId,
    githubUrl,
    status,
    onStop,
    onBack,
    stopping,
}: IDEHeaderProps) {
    const isConnected = status === "running";

    const title =
        mode === "swebench"
            ? instanceId || "SWE-bench Instance"
            : githubUrl
                ? githubUrl.split("/").slice(-2).join("/")
                : "GitHub Repo";

    return (
        <header className="bg-zinc-950/90 border-b border-zinc-800 backdrop-blur-xl">
            <div className="flex items-center justify-between px-4 py-2.5">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onBack}
                        className="text-zinc-500 hover:text-zinc-300 transition-colors p-1 rounded hover:bg-zinc-800/50"
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </button>

                    <div className="flex items-center gap-2">
                        <Monitor className="w-4 h-4 text-blue-500" />
                        <h1 className="text-sm font-semibold text-zinc-200">{title}</h1>
                    </div>

                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-zinc-900 border border-zinc-800">
                        <span className="text-[10px] font-mono text-zinc-500 uppercase">
                            {mode}
                        </span>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {isConnected ? (
                        <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                        <WifiOff className="w-3.5 h-3.5 text-rose-400" />
                    )}
                    <span
                        className={`text-xs font-mono ${isConnected ? "text-emerald-400" : "text-rose-400"}`}
                    >
                        {isConnected ? "Connected" : "Disconnected"}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={onStop}
                        disabled={stopping}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 rounded-md transition-all disabled:opacity-50"
                    >
                        {stopping ? (
                            <>
                                <Loader2 className="w-3 h-3 animate-spin" />
                                Stopping...
                            </>
                        ) : (
                            <>
                                <Square className="w-3 h-3" />
                                Stop Session
                            </>
                        )}
                    </button>
                </div>
            </div>
        </header>
    );
}
