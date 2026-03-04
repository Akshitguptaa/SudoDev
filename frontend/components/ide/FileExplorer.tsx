"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
    FolderOpen,
    File,
    ChevronRight,
    ChevronDown,
    FileCode,
    FileText,
    FileJson,
    Loader2,
} from "lucide-react";

interface FileEntry {
    name: string;
    path: string;
    is_dir: boolean;
    size: number;
    permissions: string;
}

interface FileExplorerProps {
    sessionId: string;
    apiBase: string;
    onFileSelect: (path: string) => void;
    selectedFile: string | null;
}

function getFileIcon(name: string, isDir: boolean) {
    if (isDir) return FolderOpen;
    const ext = name.split(".").pop()?.toLowerCase();
    switch (ext) {
        case "py":
        case "js":
        case "ts":
        case "tsx":
        case "jsx":
        case "go":
        case "rs":
        case "c":
        case "cpp":
        case "java":
            return FileCode;
        case "json":
        case "yaml":
        case "yml":
        case "toml":
            return FileJson;
        default:
            return FileText;
    }
}

function getFileColor(name: string, isDir: boolean) {
    if (isDir) return "text-blue-400";
    const ext = name.split(".").pop()?.toLowerCase();
    switch (ext) {
        case "py":
            return "text-yellow-400";
        case "js":
        case "jsx":
            return "text-yellow-300";
        case "ts":
        case "tsx":
            return "text-blue-300";
        case "json":
            return "text-green-400";
        case "md":
            return "text-zinc-300";
        default:
            return "text-zinc-400";
    }
}

interface TreeNodeProps {
    entry: FileEntry;
    depth: number;
    sessionId: string;
    apiBase: string;
    onFileSelect: (path: string) => void;
    selectedFile: string | null;
}

function TreeNode({
    entry,
    depth,
    sessionId,
    apiBase,
    onFileSelect,
    selectedFile,
}: TreeNodeProps) {
    const [expanded, setExpanded] = useState(false);
    const [children, setChildren] = useState<FileEntry[]>([]);
    const [loading, setLoading] = useState(false);

    const toggleExpand = async () => {
        if (!entry.is_dir) {
            onFileSelect(entry.path);
            return;
        }

        if (!expanded && children.length === 0) {
            setLoading(true);
            try {
                const res = await fetch(
                    `${apiBase}/api/ide/session/${sessionId}/files?path=${encodeURIComponent(entry.path)}`
                );
                const data = await res.json();
                setChildren(data.files || []);
            } catch (e) {
                console.error("Failed to load directory:", e);
            } finally {
                setLoading(false);
            }
        }
        setExpanded(!expanded);
    };

    const Icon = getFileIcon(entry.name, entry.is_dir);
    const color = getFileColor(entry.name, entry.is_dir);
    const isSelected = selectedFile === entry.path;

    return (
        <div>
            <button
                onClick={toggleExpand}
                className={`w-full flex items-center gap-1.5 px-2 py-1 text-xs font-mono hover:bg-zinc-800/60 transition-colors rounded-sm ${isSelected ? "bg-blue-500/15 text-blue-300" : "text-zinc-300"
                    }`}
                style={{ paddingLeft: `${depth * 16 + 8}px` }}
            >
                {entry.is_dir ? (
                    expanded ? (
                        <ChevronDown className="w-3 h-3 text-zinc-500 shrink-0" />
                    ) : (
                        <ChevronRight className="w-3 h-3 text-zinc-500 shrink-0" />
                    )
                ) : (
                    <span className="w-3 shrink-0" />
                )}
                {loading ? (
                    <Loader2 className="w-3.5 h-3.5 text-zinc-500 animate-spin shrink-0" />
                ) : (
                    <Icon className={`w-3.5 h-3.5 ${color} shrink-0`} />
                )}
                <span className="truncate">{entry.name}</span>
            </button>

            {expanded &&
                children.map((child) => (
                    <TreeNode
                        key={child.path}
                        entry={child}
                        depth={depth + 1}
                        sessionId={sessionId}
                        apiBase={apiBase}
                        onFileSelect={onFileSelect}
                        selectedFile={selectedFile}
                    />
                ))}
        </div>
    );
}

export default function FileExplorer({
    sessionId,
    apiBase,
    onFileSelect,
    selectedFile,
}: FileExplorerProps) {
    const [rootFiles, setRootFiles] = useState<FileEntry[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadRoot() {
            try {
                const res = await fetch(
                    `${apiBase}/api/ide/session/${sessionId}/files?path=/testbed`
                );
                const data = await res.json();
                setRootFiles(data.files || []);
            } catch (e) {
                console.error("Failed to load root files:", e);
            } finally {
                setLoading(false);
            }
        }
        loadRoot();
    }, [sessionId, apiBase]);

    return (
        <div className="h-full flex flex-col bg-zinc-950/60 border-r border-zinc-800">
            <div className="px-3 py-2.5 border-b border-zinc-800 flex items-center gap-2">
                <FolderOpen className="w-3.5 h-3.5 text-zinc-500" />
                <span className="font-mono text-xs text-zinc-500 uppercase tracking-wider">
                    Explorer
                </span>
            </div>

            <div className="flex-1 overflow-auto py-1">
                {loading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-4 h-4 text-zinc-500 animate-spin" />
                    </div>
                ) : rootFiles.length === 0 ? (
                    <div className="text-xs text-zinc-600 text-center py-8">
                        No files found
                    </div>
                ) : (
                    rootFiles.map((entry) => (
                        <TreeNode
                            key={entry.path}
                            entry={entry}
                            depth={0}
                            sessionId={sessionId}
                            apiBase={apiBase}
                            onFileSelect={onFileSelect}
                            selectedFile={selectedFile}
                        />
                    ))
                )}
            </div>
        </div>
    );
}
