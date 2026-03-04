"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Editor from "@monaco-editor/react";
import { X, Save, Loader2, Circle } from "lucide-react";

interface OpenTab {
    path: string;
    name: string;
    content: string;
    modified: boolean;
    loading: boolean;
}

interface CodeEditorProps {
    sessionId: string;
    apiBase: string;
    filePath: string | null;
    openTabs: OpenTab[];
    setOpenTabs: React.Dispatch<React.SetStateAction<OpenTab[]>>;
    activeTab: string | null;
    setActiveTab: (path: string | null) => void;
    highlightRequest?: { filepath: string; lines?: string } | null;
}

function getLanguage(filename: string): string {
    const ext = filename.split(".").pop()?.toLowerCase() || "";
    const langMap: Record<string, string> = {
        py: "python",
        js: "javascript",
        jsx: "javascript",
        ts: "typescript",
        tsx: "typescript",
        json: "json",
        yml: "yaml",
        yaml: "yaml",
        toml: "toml",
        md: "markdown",
        css: "css",
        html: "html",
        xml: "xml",
        sh: "shell",
        bash: "shell",
        sql: "sql",
        go: "go",
        rs: "rust",
        c: "c",
        cpp: "cpp",
        h: "c",
        java: "java",
        rb: "ruby",
        txt: "plaintext",
        cfg: "ini",
        ini: "ini",
        conf: "ini",
        dockerfile: "dockerfile",
        makefile: "makefile",
    };
    return langMap[ext] || "plaintext";
}

export default function CodeEditor({
    sessionId,
    apiBase,
    filePath,
    openTabs,
    setOpenTabs,
    activeTab,
    setActiveTab,
    highlightRequest,
}: CodeEditorProps) {
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);

    const editorRef = useRef<any>(null);
    const monacoRef = useRef<any>(null);
    const decorationsRef = useRef<string[]>([]);

    const handleEditorDidMount = (editor: any, monaco: any) => {
        editorRef.current = editor;
        monacoRef.current = monaco;
    };

    useEffect(() => {
        if (!filePath) return;

        const existing = openTabs.find((t) => t.path === filePath);
        if (existing) {
            setActiveTab(filePath);
            return;
        }

        const name = filePath.split("/").pop() || filePath;
        const newTab: OpenTab = {
            path: filePath,
            name,
            content: "",
            modified: false,
            loading: true,
        };

        setOpenTabs((prev) => [...prev, newTab]);
        setActiveTab(filePath);

        fetch(
            `${apiBase}/api/ide/session/${sessionId}/file?path=${encodeURIComponent(filePath)}`
        )
            .then((res) => res.json())
            .then((data) => {
                setOpenTabs((prev) =>
                    prev.map((t) =>
                        t.path === filePath
                            ? { ...t, content: data.content || "", loading: false }
                            : t
                    )
                );
            })
            .catch((e) => {
                console.error("Failed to load file:", e);
                setOpenTabs((prev) =>
                    prev.map((t) =>
                        t.path === filePath
                            ? { ...t, content: "// Failed to load file", loading: false }
                            : t
                    )
                );
            });
    }, [filePath, sessionId, apiBase]);

    const handleSave = useCallback(async () => {
        if (!activeTab) return;
        const tab = openTabs.find((t) => t.path === activeTab);
        if (!tab || !tab.modified) return;

        setSaving(true);
        try {
            await fetch(`${apiBase}/api/ide/session/${sessionId}/file`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: tab.path, content: tab.content }),
            });
            setOpenTabs((prev) =>
                prev.map((t) => (t.path === activeTab ? { ...t, modified: false } : t))
            );
            setSaveMessage("Saved");
            setTimeout(() => setSaveMessage(null), 2000);
        } catch (e) {
            setSaveMessage("Save failed");
            setTimeout(() => setSaveMessage(null), 3000);
        } finally {
            setSaving(false);
        }
    }, [activeTab, openTabs, sessionId, apiBase]);

    useEffect(() => {
        if (!highlightRequest || !editorRef.current || !monacoRef.current || highlightRequest.filepath !== activeTab) {
            return;
        }

        const editor = editorRef.current;
        const monaco = monacoRef.current;

        let startLine = 1;
        let endLine = 1;

        if (highlightRequest.lines) {
            const match = highlightRequest.lines.match(/L(\d+)-L(\d+)/);
            if (match) {
                startLine = parseInt(match[1]);
                endLine = parseInt(match[2]);
            }
        } else {
            startLine = 1;
            endLine = editor.getModel().getLineCount();
        }

        decorationsRef.current = editor.deltaDecorations(decorationsRef.current, [
            {
                range: new monaco.Range(startLine, 1, endLine, 1),
                options: {
                    isWholeLine: true,
                    className: "bg-blue-500/20 border-l-2 border-blue-500"
                }
            }
        ]);

        editor.revealRangeInCenterIfOutsideViewport(new monaco.Range(startLine, 1, endLine, 1));

    }, [highlightRequest, activeTab]);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "s") {
                e.preventDefault();
                handleSave();
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [handleSave]);

    const closeTab = (path: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setOpenTabs((prev) => prev.filter((t) => t.path !== path));
        if (activeTab === path) {
            const remaining = openTabs.filter((t) => t.path !== path);
            setActiveTab(remaining.length > 0 ? remaining[remaining.length - 1].path : null);
        }
    };

    const currentTab = openTabs.find((t) => t.path === activeTab);

    return (
        <div className="h-full flex flex-col bg-zinc-950/40">
            <div className="flex items-center border-b border-zinc-800 bg-zinc-950/80 overflow-x-auto">
                {openTabs.map((tab) => (
                    <button
                        key={tab.path}
                        onClick={() => setActiveTab(tab.path)}
                        className={`flex items-center gap-1.5 px-3 py-2 text-xs font-mono border-r border-zinc-800 transition-colors shrink-0 ${activeTab === tab.path
                            ? "bg-zinc-900/80 text-zinc-200 border-b-2 border-b-blue-500"
                            : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/40"
                            }`}
                    >
                        {tab.modified && (
                            <Circle className="w-2 h-2 fill-blue-400 text-blue-400" />
                        )}
                        <span>{tab.name}</span>
                        <X
                            className="w-3 h-3 text-zinc-600 hover:text-zinc-300 ml-1"
                            onClick={(e) => closeTab(tab.path, e)}
                        />
                    </button>
                ))}

                {saveMessage && (
                    <span className="px-3 py-2 text-xs text-emerald-400 font-mono ml-auto">
                        {saveMessage}
                    </span>
                )}
            </div>

            <div className="flex-1 relative">
                {currentTab ? (
                    currentTab.loading ? (
                        <div className="flex items-center justify-center h-full">
                            <Loader2 className="w-6 h-6 text-zinc-500 animate-spin" />
                        </div>
                    ) : (
                        <Editor
                            height="100%"
                            language={getLanguage(currentTab.name)}
                            value={currentTab.content}
                            theme="vs-dark"
                            onMount={handleEditorDidMount}
                            onChange={(value) => {
                                setOpenTabs((prev) =>
                                    prev.map((t) =>
                                        t.path === activeTab
                                            ? { ...t, content: value || "", modified: true }
                                            : t
                                    )
                                );
                            }}
                            options={{
                                fontSize: 13,
                                fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
                                minimap: { enabled: true, scale: 1 },
                                scrollBeyondLastLine: false,
                                smoothScrolling: true,
                                cursorBlinking: "smooth",
                                cursorSmoothCaretAnimation: "on",
                                padding: { top: 12, bottom: 12 },
                                renderLineHighlight: "all",
                                bracketPairColorization: { enabled: true },
                                guides: {
                                    bracketPairs: true,
                                    indentation: true,
                                },
                                wordWrap: "on",
                                automaticLayout: true,
                            }}
                        />
                    )
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-zinc-600">
                        <div className="text-6xl mb-4 opacity-10">{"</>"}</div>
                        <p className="text-sm">Select a file to start editing</p>
                        <p className="text-xs text-zinc-700 mt-1">
                            Browse files in the explorer panel
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
