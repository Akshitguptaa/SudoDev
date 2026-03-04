"use client";

import { useState, useRef, useCallback } from "react";
import FileExplorer from "./FileExplorer";
import CodeEditor from "./CodeEditor";
import IDETerminal from "./IDETerminal";

interface OpenTab {
    path: string;
    name: string;
    content: string;
    modified: boolean;
    loading: boolean;
}

interface IDELayoutProps {
    sessionId: string;
    apiBase: string;
    wsBase: string;
}

export default function IDELayout({ sessionId, apiBase, wsBase }: IDELayoutProps) {
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
    const [activeTab, setActiveTab] = useState<string | null>(null);

    const [explorerWidth, setExplorerWidth] = useState(240);
    const [terminalHeight, setTerminalHeight] = useState(250);

    const containerRef = useRef<HTMLDivElement>(null);
    const isDraggingVertical = useRef(false);
    const isDraggingHorizontal = useRef(false);

    const handleFileSelect = useCallback((path: string) => {
        setSelectedFile(path);
    }, []);

    const startVerticalDrag = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        isDraggingVertical.current = true;

        const startX = e.clientX;
        const startWidth = explorerWidth;

        const onMove = (me: MouseEvent) => {
            if (!isDraggingVertical.current) return;
            const delta = me.clientX - startX;
            const newWidth = Math.max(180, Math.min(500, startWidth + delta));
            setExplorerWidth(newWidth);
        };

        const onUp = () => {
            isDraggingVertical.current = false;
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };

        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    }, [explorerWidth]);

    const startHorizontalDrag = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        isDraggingHorizontal.current = true;

        const startY = e.clientY;
        const startHeight = terminalHeight;

        const onMove = (me: MouseEvent) => {
            if (!isDraggingHorizontal.current) return;
            const delta = startY - me.clientY;
            const newHeight = Math.max(120, Math.min(600, startHeight + delta));
            setTerminalHeight(newHeight);
        };

        const onUp = () => {
            isDraggingHorizontal.current = false;
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };

        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    }, [terminalHeight]);

    return (
        <div ref={containerRef} className="flex-1 flex overflow-hidden">
            <div style={{ width: explorerWidth, minWidth: 180 }} className="shrink-0">
                <FileExplorer
                    sessionId={sessionId}
                    apiBase={apiBase}
                    onFileSelect={handleFileSelect}
                    selectedFile={activeTab}
                />
            </div>

            <div
                className="w-1 bg-zinc-800 hover:bg-blue-500/50 cursor-col-resize transition-colors shrink-0"
                onMouseDown={startVerticalDrag}
            />

            <div className="flex-1 flex flex-col min-w-0">
                <div className="flex-1 min-h-0">
                    <CodeEditor
                        sessionId={sessionId}
                        apiBase={apiBase}
                        filePath={selectedFile}
                        openTabs={openTabs}
                        setOpenTabs={setOpenTabs}
                        activeTab={activeTab}
                        setActiveTab={setActiveTab}
                    />
                </div>

                <div
                    className="h-1 bg-zinc-800 hover:bg-blue-500/50 cursor-row-resize transition-colors shrink-0"
                    onMouseDown={startHorizontalDrag}
                />

                <div style={{ height: terminalHeight, minHeight: 120 }} className="shrink-0">
                    <IDETerminal sessionId={sessionId} wsBase={wsBase} />
                </div>
            </div>
        </div>
    );
}
