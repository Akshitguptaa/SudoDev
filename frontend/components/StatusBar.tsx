"use client";

const STATUS_COLORS: Record<string, string> = {
    idle: "bg-zinc-500",
    processing: "bg-amber-500",
    completed: "bg-emerald-500",
    error: "bg-rose-500",
};

export default function StatusBar({ status, runId }: { status: string; runId: string }) {
    const color = STATUS_COLORS[status] || STATUS_COLORS.error;

    return (
        <div className="h-8 bg-zinc-900 border-t border-zinc-800 flex items-center px-4 text-xs font-mono">
            <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${color}`} />
                <span className="text-zinc-500 uppercase tracking-wide">{status}</span>
            </div>
            {runId && <span className="ml-4 text-zinc-600">Run: {runId.slice(0, 8)}</span>}
        </div>
    );
}
