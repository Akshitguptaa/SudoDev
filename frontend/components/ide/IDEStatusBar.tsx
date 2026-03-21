"use client";

import { GitBranch, Cpu, Circle } from "lucide-react";

interface IDEStatusBarProps {
    mode: string;
    status: string;
    branch?: string;
    sandboxStatus?: "active" | "idle" | "disconnected";
    activeFile?: string | null;
}

export default function IDEStatusBar({
    mode,
    status,
    branch = "main",
    sandboxStatus = "active",
    activeFile,
}: IDEStatusBarProps) {
    const isConnected = status === "running";

    return (
        <div className="h-6 flex items-center justify-between px-3 bg-[var(--vscode-statusbar-bg)] text-white text-[11px] font-mono shrink-0 select-none">
            <div className="flex items-center gap-3">
                {/* Connection status */}
                <div className="flex items-center gap-1">
                    {isConnected ? (
                        <>
                            <Circle className="w-2 h-2 fill-emerald-400 text-emerald-400" />
                            <span>Running</span>
                        </>
                    ) : (
                        <>
                            <Circle className="w-2 h-2 fill-rose-400 text-rose-400" />
                            <span>Disconnected</span>
                        </>
                    )}
                </div>

                {/* Branch */}
                <div className="flex items-center gap-1">
                    <GitBranch className="w-3 h-3" />
                    <span>{branch}</span>
                </div>

                {/* Mode */}
                <span className="uppercase opacity-75">{mode}</span>
            </div>

            <div className="flex items-center gap-3">
                {/* Active file language */}
                {activeFile && (
                    <span className="opacity-75">
                        {getLanguageLabel(activeFile)}
                    </span>
                )}

                {/* E2B Sandbox status */}
                <div className="flex items-center gap-1">
                    <Cpu className="w-3 h-3" />
                    <span>E2B: {sandboxStatus}</span>
                </div>
            </div>
        </div>
    );
}

function getLanguageLabel(filepath: string): string {
    const ext = filepath.split(".").pop()?.toLowerCase() || "";
    const labels: Record<string, string> = {
        py: "Python",
        js: "JavaScript",
        jsx: "JavaScript JSX",
        ts: "TypeScript",
        tsx: "TypeScript JSX",
        json: "JSON",
        yml: "YAML",
        yaml: "YAML",
        md: "Markdown",
        css: "CSS",
        html: "HTML",
        go: "Go",
        rs: "Rust",
        java: "Java",
        sh: "Shell",
        toml: "TOML",
    };
    return labels[ext] || ext.toUpperCase() || "Plain Text";
}
