"use client";

import {
    Files,
    Search,
    Bot,
    Settings,
    GitBranch,
} from "lucide-react";

export type SidebarView = "files" | "search" | "agent" | "settings";

interface ActivityBarProps {
    activeView: SidebarView;
    onViewChange: (view: SidebarView) => void;
}

const ACTIVITY_ITEMS: { id: SidebarView; icon: typeof Files; label: string }[] = [
    { id: "files", icon: Files, label: "Explorer" },
    { id: "search", icon: Search, label: "Search" },
    { id: "agent", icon: Bot, label: "Agent" },
    { id: "settings", icon: Settings, label: "Settings" },
];

export default function ActivityBar({ activeView, onViewChange }: ActivityBarProps) {
    return (
        <div className="h-full flex flex-col items-center py-1 bg-[var(--vscode-activitybar-bg)] border-r border-[var(--vscode-border)]"
            style={{ width: 48 }}
        >
            {ACTIVITY_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = activeView === item.id;
                return (
                    <button
                        key={item.id}
                        onClick={() => onViewChange(item.id)}
                        title={item.label}
                        className={`w-full flex items-center justify-center py-3 transition-colors relative ${
                            isActive
                                ? "text-white"
                                : "text-[var(--vscode-text-muted)] hover:text-[var(--vscode-text)]"
                        }`}
                    >
                        {isActive && (
                            <div className="absolute left-0 top-1 bottom-1 w-0.5 bg-white rounded-r" />
                        )}
                        <Icon className="w-5 h-5" />
                    </button>
                );
            })}

            <div className="mt-auto pb-2">
                <button
                    title="Source Control"
                    className="w-full flex items-center justify-center py-3 text-[var(--vscode-text-muted)] hover:text-[var(--vscode-text)] transition-colors"
                >
                    <GitBranch className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}
