"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { IDEHeader, IDELayout } from "@/components/ide";

const API_BASE = typeof window !== 'undefined'
    ? `http://${window.location.hostname}:8000`
    : 'http://localhost:8000';
const WS_BASE = API_BASE.replace(/^http/, "ws");

interface SessionInfo {
    session_id: string;
    status: string;
    mode: string;
    instance_id?: string;
    github_url?: string;
    created_at?: string;
}

export default function IDEContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const sessionId = searchParams.get("session");

    const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [stopping, setStopping] = useState(false);

    useEffect(() => {
        if (!sessionId) {
            setError("No session ID provided");
            setLoading(false);
            return;
        }

        async function fetchSession() {
            try {
                const res = await fetch(`${API_BASE}/api/ide/session/${sessionId}`);
                if (!res.ok) throw new Error("Session not found");
                const data = await res.json();
                setSessionInfo(data);
            } catch (e: any) {
                setError(e.message || "Failed to load session");
            } finally {
                setLoading(false);
            }
        }

        fetchSession();
    }, [sessionId]);

    const handleStop = async () => {
        if (!sessionId) return;
        setStopping(true);
        try {
            await fetch(`${API_BASE}/api/ide/session/${sessionId}`, {
                method: "DELETE",
            });
            router.push("/");
        } catch (e) {
            console.error("Failed to stop session:", e);
        } finally {
            setStopping(false);
        }
    };

    const handleBack = () => {
        router.push("/");
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex flex-col items-center gap-4"
                >
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <p className="text-sm text-zinc-500 font-mono">
                        Connecting to IDE session...
                    </p>
                </motion.div>
            </div>
        );
    }

    if (error || !sessionInfo) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center"
                >
                    <p className="text-rose-400 text-lg mb-4">{error || "Unknown error"}</p>
                    <button
                        onClick={handleBack}
                        className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-md text-sm transition-colors"
                    >
                        Go Back
                    </button>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="h-screen flex flex-col bg-[#09090b] text-white">
            <IDEHeader
                sessionId={sessionId!}
                mode={sessionInfo.mode}
                instanceId={sessionInfo.instance_id}
                githubUrl={sessionInfo.github_url}
                status={sessionInfo.status}
                onStop={handleStop}
                onBack={handleBack}
                stopping={stopping}
            />
            <IDELayout
                sessionId={sessionId!}
                apiBase={API_BASE}
                wsBase={WS_BASE}
            />
        </div>
    );
}
