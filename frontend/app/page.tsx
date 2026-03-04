"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { Code2, Search, Wrench, TestTube, Sparkles } from "lucide-react";
import { Input, AgentView, Results, StatusBar } from "@/components";

const API_BASE = typeof window !== 'undefined'
  ? `http://${window.location.hostname}:8000`
  : 'http://localhost:8000';

const steps = [
  { id: "init", label: "Initialize", icon: Sparkles },
  { id: "analyze", label: "Analyze", icon: Search },
  { id: "reproduce", label: "Reproduce", icon: Code2 },
  { id: "locate", label: "Locate Files", icon: Search },
  { id: "fix", label: "Generate Fix", icon: Wrench },
  { id: "verify", label: "Verify", icon: TestTube },
];

type InputMode = "swebench" | "github" | null;

function extractRepoUrl(issueUrl: string): string {
  const match = issueUrl.match(
    /^https:\/\/github\.com\/([^/]+)\/([^/]+)\/issues\/\d+/
  );
  if (match) {
    return `https://github.com/${match[1]}/${match[2]}`;
  }
  return "";
}

export default function Home() {
  const [view, setView] = useState("input");
  const [mode, setMode] = useState<InputMode>(null);
  const [instanceId, setInstanceId] = useState("");
  const [githubRepoUrl, setGithubRepoUrl] = useState("");
  const [githubIssueUrl, setGithubIssueUrl] = useState("");
  const [context, setContext] = useState("");
  const [runId, setRunId] = useState("");
  const [status, setStatus] = useState("idle");
  const [currentStep, setCurrentStep] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [patch, setPatch] = useState("");
  const [ideLoading, setIdeLoading] = useState(false);
  const router = useRouter();

  // Poll for agent status and logs
  useEffect(() => {
    if (view !== "hud" || !runId) return;

    const pollInterval = setInterval(async () => {
      try {
        const statusResponse = await fetch(`http://localhost:8000/api/status/${runId}`);
        const data = await statusResponse.json();

        if (data.error) {
          clearInterval(pollInterval);
          setStatus("failed");
          setView("result");
          return;
        }

        // Update logs and current step
        setLogs(data.logs || []);
        setCurrentStep(data.current_step || 0);
        setStatus(data.status);
        setPatch(data.patch || "");

        // If completed or failed, show results
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(pollInterval);
          setTimeout(() => {
            setView("result");
          }, 1000);
        }
      } catch (error) {
        console.error("Error polling status:", error);
        clearInterval(pollInterval);
        setStatus("failed");
        setView("result");
      }
    }, 1500); // Poll every 1.5 seconds

    return () => clearInterval(pollInterval);
  }, [view, runId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setLogs([]);
    setCurrentStep(0);
    setStatus("pending");

    try {
      // For SWE-bench mode, check if Docker image exists first
      if (mode === "swebench" && instanceId) {
        setLogs(["Checking Docker image status..."]);
        const dockerStatus = await fetch(`http://localhost:8000/api/docker/status/${instanceId}`);
        const dockerData = await dockerStatus.json();

        if (!dockerData.image_exists) {
          const confirmBuild = confirm(
            `Docker image for "${instanceId}" is not available.\n\n` +
            `Would you like to build it now? This process is fully automated but may take 5-10 minutes.\n\n` +
            `Click OK to build, or Cancel to abort.`
          );

          if (confirmBuild) {
            setStatus("building");
            setView("hud");
            setLogs(["Building Docker image... This may take 5-10 minutes.", "Please wait..."]);

            // Build synchronously 
            const buildResponse = await fetch(`http://localhost:8000/api/docker/build/${instanceId}`, {
              method: "POST"
            });
            const buildResult = await buildResponse.json();

            if (!buildResult.success) {
              // If automatic build fails, suggest manual fallback
              const command = `./build_image.sh ${instanceId}`;
              prompt(
                `Automatic build failed: ${buildResult.message}\n` +
                `You can try building manually with this script:\n`,
                command
              );
              throw new Error(buildResult.message || "Docker build failed");
            }

            setLogs(prev => [...prev, "Docker image built successfully! Starting agent..."]);
          } else {
            setLoading(false);
            setStatus("idle");
            return;
          }
        }
      }

      // Prepare request based on mode
      let requestBody;

      if (mode === "github") {
        requestBody = {
          mode: "github",
          github_url: githubRepoUrl,
          issue_url: githubIssueUrl,
          problem_statement: context || null,
        };
      } else {
        // SWE-bench mode
        requestBody = {
          mode: "swebench",
          instance_id: instanceId,
          problem_statement: context || null,
        };
      }

      console.log("Sending request:", requestBody);

      // Call the backend API to start agent run
      const response = await fetch("http://localhost:8000/api/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log("Response from backend:", data);

      if (data.run_id) {
        setRunId(data.run_id);
        setStatus("processing");
        setView("hud");
      } else {
        throw new Error(JSON.stringify(data));
      }
    } catch (error) {
      console.error("Error starting agent:", error);
      setStatus("failed");

      let errorMessage = "Failed to start agent. ";
      if (error instanceof Error) {
        errorMessage += error.message;
      } else {
        errorMessage += "Unknown error occurred";
      }
      errorMessage += "\n\nMake sure the backend is running on port 8000.";

      alert(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setView("input");
    setMode(null);
    setInstanceId("");
    setGithubRepoUrl("");
    setGithubIssueUrl("");
    setContext("");
    setRunId("");
    setStatus("idle");
    setLogs([]);
    setCurrentStep(0);
    setPatch("");
  };

  const handleOpenIDE = async () => {
    if (!mode) return;

    setIdeLoading(true);
    try {
      let requestBody: any = { mode };

      if (mode === "swebench") {
        if (!instanceId) {
          alert("Please enter a SWE-bench instance ID");
          return;
        }

        const dockerStatus = await fetch(`${API_BASE}/api/docker/status/${instanceId}`);
        const dockerData = await dockerStatus.json();

        if (!dockerData.image_exists) {
          const confirmBuild = confirm(
            `Docker image for "${instanceId}" is not available.\n\n` +
            `Would you like to build it now? This may take 5-10 minutes.\n\n` +
            `Click OK to build, or Cancel to abort.`
          );

          if (confirmBuild) {
            const buildResponse = await fetch(`${API_BASE}/api/docker/build/${instanceId}`, {
              method: "POST"
            });
            const buildResult = await buildResponse.json();
            if (!buildResult.success) {
              throw new Error(buildResult.message || "Docker build failed");
            }
          } else {
            setIdeLoading(false);
            return;
          }
        }

        requestBody.instance_id = instanceId;
      } else if (mode === "github") {
        const repoUrl = githubRepoUrl || extractRepoUrl(githubIssueUrl);
        if (!repoUrl) {
          alert("Please enter a GitHub issue URL or repository URL");
          return;
        }
        requestBody.github_url = repoUrl;
      }

      const response = await fetch(`${API_BASE}/api/ide/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      if (data.session_id) {
        router.push(`/ide?session=${data.session_id}`);
      } else {
        throw new Error("No session ID returned");
      }
    } catch (error) {
      console.error("Error opening IDE:", error);
      let errorMessage = "Failed to open IDE. ";
      if (error instanceof Error) errorMessage += error.message;
      errorMessage += "\n\nMake sure the backend is running on port 8000.";
      alert(errorMessage);
    } finally {
      setIdeLoading(false);
    }
  };

  return (
    <div className="min-h-screen text-white flex flex-col">
      <header className="glassmorphism border-b border-zinc-800/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <h1 className="text-xl font-bold">SudoDev</h1>
        </div>
      </header>

      <div className="flex-1">
        <AnimatePresence mode="wait">
          {view === "input" && (
            <Input
              mode={mode}
              setMode={setMode}
              instanceId={instanceId}
              setInstanceId={setInstanceId}
              githubRepoUrl={githubRepoUrl}
              setGithubRepoUrl={setGithubRepoUrl}
              githubIssueUrl={githubIssueUrl}
              setGithubIssueUrl={setGithubIssueUrl}
              context={context}
              setContext={setContext}
              loading={loading}
              onSubmit={handleSubmit}
              onOpenIDE={handleOpenIDE}
              ideLoading={ideLoading}
            />
          )}

          {view === "hud" && (
            <AgentView steps={steps} currentStep={currentStep} logs={logs} />
          )}

          {view === "result" && <Results status={status} patch={patch} onReset={reset} />}
        </AnimatePresence>
      </div>

      <StatusBar status={status} runId={runId} />
    </div>
  );
}