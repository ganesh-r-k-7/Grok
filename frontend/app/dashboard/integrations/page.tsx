"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

interface IntegrationStatus {
  provider: string;
  connected: boolean;
  email?: string;
  name?: string;
  last_synced_at?: string;
}

export default function IntegrationsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuthStore();
  const [googleConnected, setGoogleConnected] = useState(false);
  const [googleIdentity, setGoogleIdentity] = useState<{ email?: string; name?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const connected = searchParams.get("connected");
    const errorParam = searchParams.get("error");
    const details = searchParams.get("details");

    if (connected === "google") {
      setSuccess("Google Calendar connected successfully!");
      router.replace("/dashboard/integrations");
    } else if (errorParam) {
      setError(`Connection failed: ${errorParam}${details ? ` (${details})` : ""}`);
      router.replace("/dashboard/integrations");
    }

    checkGoogleConnection();
  }, [searchParams, router]);

  const checkGoogleConnection = async () => {
    try {
      const response = await api.get<IntegrationStatus>("/auth/google/status");
      setGoogleConnected(response.connected);
      if (response.connected) {
        setGoogleIdentity({ email: response.email, name: response.name });
      }
    } catch {
      setGoogleConnected(false);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const response = await api.post<{ authorization_url: string }>("/auth/google/connect", {});
      window.location.href = response.authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initiate connection");
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    setError(null);
    try {
      await api.delete<void>("/auth/google/disconnect");
      setGoogleConnected(false);
      setGoogleIdentity(null);
      setSuccess("Google Calendar disconnected successfully!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disconnect");
    } finally {
      setDisconnecting(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
          Integrations
        </h1>
        <p className="text-slate-600 dark:text-slate-400 mt-1">
          Connect external services to enhance your GROK experience.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-300">
          {success}
        </div>
      )}

      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.327,0-6.033-2.706-6.033-6.033s2.706-6.033,6.033-6.033c1.498,0,2.866,0.539,3.921,1.453l2.814-2.814C17.478,0.927,15.235,0,12.545,0C7.057,0,2.558,4.5,2.558,9.997c0,2.572,1.011,4.923,2.643,6.637L5.22,19.331C3.324,17.127,2.557,14.199,2.557,10.925C2.557,6.392,6.157,2.792,10.69,2.792c2.392,0,4.524,1.022,6.027,2.637L12.545,10.239z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Google Calendar
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Read-only access to view your calendar events
              </p>
            </div>
          </div>

          {loading ? (
            <div className="animate-spin rounded-full h-8 w-8 border-3 border-primary-500 border-t-transparent" />
          ) : googleConnected ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                <span>Connected</span>
              </div>
              {googleIdentity?.email && (
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  {googleIdentity.email}
                </span>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={handleDisconnect}
                disabled={disconnecting}
              >
                {disconnecting ? "Disconnecting..." : "Disconnect"}
              </Button>
            </div>
          ) : (
            <Button onClick={handleConnect} disabled={connecting}>
              {connecting ? "Connecting..." : "Connect Google Calendar"}
            </Button>
          )}
        </div>

        {!loading && !googleConnected && (
          <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
            <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-2">
              Permissions Requested
            </h4>
            <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-1">
              <li>• View your calendars (read-only)</li>
              <li>• View your calendar events (read-only)</li>
              <li>• View your basic profile info (name, email, picture)</li>
            </ul>
            <p className="text-xs text-slate-500 dark:text-slate-500 mt-3">
              GROK will never modify, create, or delete your calendar events.
              You can disconnect at any time.
            </p>
          </div>
        )}
      </Card>

      <Card className="p-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">
          Coming Soon
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg opacity-60">
            <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-3">
              <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
              </svg>
            </div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100">Gmail</h4>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Read-only email access</p>
          </div>
          <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg opacity-60">
            <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-3">
              <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M9 11l3 3L22 4 15 5 9 11z" />
              </svg>
            </div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100">Google Tasks</h4>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Read-only tasks access</p>
          </div>
        </div>
      </Card>
    </div>
  );
}