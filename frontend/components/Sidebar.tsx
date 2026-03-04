"use client";

import { CheckCircle2, Loader2, GitBranch } from "lucide-react";

export default function Sidebar({ steps, currentStep }: { steps: any[]; currentStep: number }) {
    return (
        <div className="col-span-3 bg-zinc-900/50 border border-zinc-800 rounded-lg p-6 overflow-auto backdrop-blur-sm">
            <h3 className="text-sm font-semibold mb-6 flex items-center gap-2 text-zinc-400">
                <GitBranch className="w-4 h-4" />
                PIPELINE
            </h3>

            <div className="space-y-3">
                {steps.map((step, idx) => {
                    const Icon = step.icon;
                    const isActive = idx === currentStep;
                    const isDone = idx < currentStep;

                    return (
                        <div
                            key={step.id}
                            className={`flex items-center gap-3 p-2.5 rounded transition-all ${isActive
                                ? "bg-blue-500/10 border border-blue-500/30"
                                : isDone
                                    ? "bg-zinc-800/30"
                                    : ""
                                }`}
                        >
                            {isDone ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                            ) : isActive ? (
                                <Loader2 className="w-4 h-4 text-blue-500 animate-spin flex-shrink-0" />
                            ) : (
                                <Icon className="w-4 h-4 text-zinc-600 flex-shrink-0" />
                            )}

                            <span
                                className={`text-xs font-medium ${isActive ? "text-blue-400" : isDone ? "text-zinc-400" : "text-zinc-600"
                                    }`}
                            >
                                {step.label}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
