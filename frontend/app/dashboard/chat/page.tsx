"use client";

import { Card } from "@/components/ui/Card";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">AI Chat</h1>
      </div>
      <Card className="p-6 text-center text-slate-500 dark:text-slate-400">
        AI Chat coming in Phase 2
      </Card>
    </div>
  );
}