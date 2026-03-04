"use client";

import { useEffect, useRef, useCallback } from "react";
import { Terminal as TerminalIcon } from "lucide-react";

const XTERM_STYLES = `
.xterm { position: relative; user-select: none; }
.xterm.focus, .xterm:focus { outline: none; }
.xterm .xterm-helpers { position: absolute; top: 0; z-index: 5; }
.xterm .xterm-helper-textarea { padding: 0; border: 0; margin: 0; position: absolute; opacity: 0; left: -9999em; top: 0; width: 0; height: 0; z-index: -5; white-space: nowrap; overflow: hidden; resize: none; }
.xterm .composition-view { display: none; position: absolute; white-space: nowrap; z-index: 1; }
.xterm .xterm-viewport { background-color: transparent; overflow-y: scroll; cursor: default; position: absolute; right: 0; left: 0; top: 0; bottom: 0; scrollbar-width: thin; }
.xterm .xterm-screen { position: relative; }
.xterm .xterm-screen canvas { position: absolute; left: 0; top: 0; }
.xterm .xterm-decoration-container .xterm-decoration { z-index: 6; position: absolute; }
.xterm .xterm-rows { position: absolute; left: 0; top: 0; }
.xterm .xterm-scroll-area { visibility: hidden; }
.xterm-char-measure-element { display: inline-block; visibility: hidden; position: absolute; top: 0; left: -9999em; line-height: normal; }
.xterm.enable-mouse-events { cursor: default; }
.xterm .xterm-cursor-pointer { cursor: pointer; }
.xterm .xterm-cursor-crosshair { cursor: crosshair; }
.xterm.xterm-cursor-style-block, .xterm.xterm-cursor-style-underline, .xterm.xterm-cursor-style-bar { cursor: none; }
`;

if (typeof document !== "undefined") {
    const styleId = "xterm-base-styles";
    if (!document.getElementById(styleId)) {
        const style = document.createElement("style");
        style.id = styleId;
        style.textContent = XTERM_STYLES;
        document.head.appendChild(style);
    }
}
interface IDETerminalProps {
    sessionId: string;
    wsBase: string;
}

export default function IDETerminal({ sessionId, wsBase }: IDETerminalProps) {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<any>(null);
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (!terminalRef.current || !sessionId) return;

        let term: any;
        let fitAddon: any;
        let cleanup = false;

        async function initTerminal() {
            const { Terminal } = await import("@xterm/xterm");
            const { FitAddon } = await import("@xterm/addon-fit");

            if (cleanup) return;

            term = new Terminal({
                cursorBlink: true,
                cursorStyle: "bar",
                fontSize: 13,
                fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
                theme: {
                    background: "#09090b",
                    foreground: "#d4d4d8",
                    cursor: "#3b82f6",
                    cursorAccent: "#09090b",
                    selectionBackground: "#3b82f640",
                    black: "#09090b",
                    red: "#f87171",
                    green: "#4ade80",
                    yellow: "#fbbf24",
                    blue: "#60a5fa",
                    magenta: "#c084fc",
                    cyan: "#22d3ee",
                    white: "#d4d4d8",
                    brightBlack: "#52525b",
                    brightRed: "#fca5a5",
                    brightGreen: "#86efac",
                    brightYellow: "#fde047",
                    brightBlue: "#93c5fd",
                    brightMagenta: "#d8b4fe",
                    brightCyan: "#67e8f9",
                    brightWhite: "#fafafa",
                },
                allowProposedApi: true,
                scrollback: 5000,
            });

            fitAddon = new FitAddon();
            term.loadAddon(fitAddon);
            term.open(terminalRef.current!);
            fitAddon.fit();

            xtermRef.current = term;

            const wsUrl = `${wsBase}/api/ide/terminal/ws/${sessionId}`;
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.binaryType = "arraybuffer";

            ws.onopen = () => {
                term.writeln("\x1b[1;34m● Connected to container terminal\x1b[0m\r\n");
            };

            ws.onmessage = (event) => {
                if (event.data instanceof ArrayBuffer) {
                    term.write(new Uint8Array(event.data));
                } else {
                    term.write(event.data);
                }
            };

            ws.onclose = () => {
                term.writeln("\r\n\x1b[1;31m● Terminal disconnected\x1b[0m");
            };

            ws.onerror = () => {
                term.writeln("\r\n\x1b[1;31m● Connection error\x1b[0m");
            };

            term.onData((data: string) => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(new TextEncoder().encode(data));
                }
            });

            const resizeObserver = new ResizeObserver(() => {
                try {
                    fitAddon.fit();
                } catch (e) { }
            });
            if (terminalRef.current) {
                resizeObserver.observe(terminalRef.current);
            }

            (term as any)._resizeObserver = resizeObserver;
        }

        initTerminal();

        return () => {
            cleanup = true;
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            if (xtermRef.current) {
                const ro = (xtermRef.current as any)._resizeObserver;
                if (ro) ro.disconnect();
                xtermRef.current.dispose();
                xtermRef.current = null;
            }
        };
    }, [sessionId, wsBase]);

    return (
        <div className="h-full flex flex-col bg-zinc-950/60 border-t border-zinc-800">
            <div className="bg-zinc-950/80 px-4 py-2 border-b border-zinc-800 flex items-center gap-2">
                <TerminalIcon className="w-3.5 h-3.5 text-zinc-500" />
                <span className="font-mono text-xs text-zinc-500 uppercase tracking-wider">
                    Terminal
                </span>
                <div className="flex gap-1.5 ml-auto">
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                </div>
            </div>
            <div ref={terminalRef} className="flex-1 p-1 bg-[#09090b]" />
        </div>
    );
}
