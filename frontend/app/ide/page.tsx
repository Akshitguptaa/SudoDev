"use client";

import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import IDEContent from "./IDEContent";

function LoadingFallback() {
    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="flex flex-col items-center gap-4">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-sm text-zinc-500 font-mono">
                    Loading IDE...
                </p>
            </div>
        </div>
    );
}

export default function IDEPage() {
    return (
        <Suspense fallback={<LoadingFallback />}>
            <IDEContent />
        </Suspense>
    );
}
