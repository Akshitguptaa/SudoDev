"use client";

import { useState, useEffect, useRef } from "react";
import { Play, Send, Bot, User, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface AgentPanelProps {
    sessionId: string;
    wsBase: string;
    onHighlightRequest: (filepath: string, lines?: string) => void;
}

interface AgentEvent {
    type: "step" | "log" | "highlight" | "ask_user" | "done" | "error";
    data: any;
}

interface ChatMessage {
    id: string;
    role: "agent" | "system" | "user";
    text: string;
    timestamp: Date;
}

export default function AgentPanel({ sessionId, wsBase, onHighlightRequest }: AgentPanelProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [status, setStatus] = useState<"idle" | "running" | "waiting_user" | "done" | "error">("idle");
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [input, setInput] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    useEffect(() => {
        const wsUrl = `${wsBase}/api/ide/agent/ws/${sessionId}`;

        const socket = new WebSocket(wsUrl);
        setWs(socket);

        socket.onmessage = (event) => {
            try {
                const payload: AgentEvent = JSON.parse(event.data);

                switch (payload.type) {
                    case "step":
                        setMessages(prev => [...prev, {
                            id: Math.random().toString(),
                            role: "system",
                            text: `[${payload.data.name}] ${payload.data.description}`,
                            timestamp: new Date()
                        }]);
                        break;
                    case "log":
                        setMessages(prev => [...prev, {
                            id: Math.random().toString(),
                            role: "agent",
                            text: payload.data.message,
                            timestamp: new Date()
                        }]);
                        break;
                    case "highlight":
                        onHighlightRequest(payload.data.filepath, payload.data.lines);
                        break;
                    case "ask_user":
                        setStatus("waiting_user");
                        setMessages(prev => [...prev, {
                            id: Math.random().toString(),
                            role: "agent",
                            text: payload.data.prompt,
                            timestamp: new Date()
                        }]);
                        break;
                    case "done":
                        setStatus("done");
                        setMessages(prev => [...prev, {
                            id: Math.random().toString(),
                            role: "system",
                            text: payload.data.success ? "Agent finished successfully." : "Agent finished with failures.",
                            timestamp: new Date()
                        }]);
                        break;
                    case "error":
                        setStatus("error");
                        setMessages(prev => [...prev, {
                            id: Math.random().toString(),
                            role: "system",
                            text: `Error: ${payload.data.message}`,
                            timestamp: new Date()
                        }]);
                        break;
                }
            } catch (err) {
                console.error("Failed to parse agent WS message", err);
            }
        };

        return () => {
            socket.close();
        };
    }, [sessionId, wsBase, onHighlightRequest]);

    const handleStart = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "start" }));
            setStatus("running");
            setMessages(prev => [...prev, {
                id: Math.random().toString(),
                role: "system",
                text: "Agent started...",
                timestamp: new Date()
            }]);
        }
    };

    const handleSendReply = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || status !== "waiting_user" || !ws) return;

        // Send reply
        ws.send(JSON.stringify({ action: "reply", text: input.trim() }));

        setMessages(prev => [...prev, {
            id: Math.random().toString(),
            role: "user",
            text: input.trim(),
            timestamp: new Date()
        }]);

        setInput("");
        setStatus("running");

        setMessages(prev => [...prev, {
            id: Math.random().toString(),
            role: "system",
            text: "Resuming agent execution...",
            timestamp: new Date()
        }]);
    };

    return (
        <div className="flex flex-col h-full bg-[#1e1e1e] border-l border-zinc-800 text-sm">
            {/* Header */}
            <div className="h-10 shrink-0 flex items-center justify-between px-4 border-b border-zinc-800 bg-[#252526]">
                <div className="flex items-center gap-2 text-zinc-300 font-medium tracking-tight">
                    <Bot className="w-4 h-4 text-blue-400" />
                    Agent
                </div>
                <div className="flex items-center gap-2 text-xs">
                    {status === "running" && <span className="text-blue-400 flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Running</span>}
                    {status === "waiting_user" && <span className="text-amber-400 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> Needs Input</span>}
                    {status === "done" && <span className="text-green-400 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Done</span>}
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {status === "idle" && messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-zinc-500 space-y-4">
                        <Bot className="w-12 h-12 text-zinc-600 mb-2 opacity-50" />
                        <p className="text-center max-w-xs text-xs">
                            Start the agent to begin diagnosing and fixing the issue interactively.
                        </p>
                        <button
                            onClick={handleStart}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs transition-colors"
                        >
                            <Play className="w-3 h-3" />
                            Start Agent
                        </button>
                    </div>
                )}

                <AnimatePresence initial={false}>
                    {messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
                        >
                            {msg.role === "system" ? (
                                <div className="text-[11px] text-zinc-500 font-mono my-1 border-l-2 border-zinc-700 pl-2">
                                    {msg.text}
                                </div>
                            ) : (
                                <div className={`flex items-start gap-2 max-w-[95%] ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                                    <div className={`p-1.5 rounded shrink-0 ${msg.role === "user" ? "bg-blue-600/20 text-blue-400" : "bg-zinc-800 text-zinc-300"}`}>
                                        {msg.role === "user" ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                                    </div>
                                    <div className={`px-3 py-2 rounded shadow-sm text-xs whitespace-pre-wrap font-mono ${msg.role === "user"
                                        ? "bg-blue-600/20 text-blue-100 border border-blue-500/20"
                                        : "bg-zinc-800/80 text-zinc-300 border border-zinc-700/50"
                                        }`}>
                                        {msg.text}
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    ))}
                </AnimatePresence>
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="shrink-0 p-3 border-t border-zinc-800 bg-[#252526]">
                <form onSubmit={handleSendReply} className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={
                            status === "waiting_user"
                                ? "Interfere or provide input..."
                                : status === "running"
                                    ? "Agent is busy..."
                                    : "Waiting for agent..."
                        }
                        disabled={status !== "waiting_user"}
                        className="flex-1 bg-[#1e1e1e] border border-zinc-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-zinc-200 text-xs rounded px-3 py-2 outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-mono shadow-inner"
                    />
                    <button
                        type="submit"
                        disabled={status !== "waiting_user" || !input.trim()}
                        className="p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded transition-colors shadow-sm"
                    >
                        <Send className="w-3.5 h-3.5" />
                    </button>
                </form>
            </div>
        </div>
    );
}
