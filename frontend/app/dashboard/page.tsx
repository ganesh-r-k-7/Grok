"use client";

import { useState, useEffect } from "react";
import { format, formatDistanceToNow, isPast } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import { tasksApi, Task, TaskStatus } from "@/lib/api";

const mockEvents = [
  { id: "1", title: "Team Standup", start: "2026-08-08T09:00:00-07:00", end: "2026-08-08T09:30:00-07:00", location: "Zoom" },
  { id: "2", title: "Project Review", start: "2026-08-08T11:00:00-07:00", end: "2026-08-08T12:00:00-07:00", location: "Conference Room A" },
  { id: "3", title: "Client Call", start: "2026-08-08T14:00:00-07:00", end: "2026-08-08T15:00:00-07:00", location: "Phone" },
];

const mockEmails = [
  { id: "1", from: "Sarah Chen", subject: "Action Required: Budget approval", snippet: "Please review the Q3 budget...", important: true },
  { id: "2", from: "GitHub", subject: "PR #234 needs review", snippet: "Your review is requested...", important: true },
];

function TimeDate() {
  const [now, setNow] = useState<Date | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  if (!mounted || !now) {
    return (
      <div className="card p-6 lg:p-8">
        <div className="mb-2 text-sm text-slate-500 dark:text-slate-400">--:--:--</div>
        <div className="text-6xl lg:text-7xl font-light text-slate-900 dark:text-slate-100 tabular-nums">--:--:--</div>
        <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">--:--</div>
      </div>
    );
  }

  return (
    <div className="card p-6 lg:p-8">
      <div className="mb-2 text-sm text-slate-500 dark:text-slate-400">{format(now, "EEEE, MMMM d, yyyy")}</div>
      <div className="text-6xl lg:text-7xl font-light text-slate-900 dark:text-slate-100 tabular-nums">{format(now, "HH:mm:ss")}</div>
      <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">{format(now, "zzzz")} • {format(now, "XXX")}</div>
    </div>
  );
}

function NextEvent() {
  const [now, setNow] = useState<Date | null>(null);
  const [mounted, setMounted] = useState(false);
  const event = mockEvents[0];

  useEffect(() => {
    setMounted(true);
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const startTime = new Date(event.start);
  const isUpcoming = now ? startTime > now : true;
  const distance = isUpcoming ? formatDistanceToNow(startTime, { addSuffix: true }) : "Ongoing";

  if (!mounted) {
    return (
      <div className="card p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-1">
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-full text-xs">Upcoming</span>
              <span>--:--:--</span>
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{event.title}</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(startTime)} – {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(event.end))}
            </p>
            {event.location && (
              <p className="text-sm text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                {event.location}
              </p>
            )}
          </div>
          <div className="flex-shrink-0"><button className="btn-secondary text-sm">Join</button></div>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-1">
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-full text-xs">{isUpcoming ? "Upcoming" : "Now"}</span>
            <span>{distance}</span>
          </div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{event.title}</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(startTime)} – {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(event.end))}
          </p>
          {event.location && (
            <p className="text-sm text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              {event.location}
            </p>
          )}
        </div>
        <div className="flex-shrink-0"><button className="btn-secondary text-sm">Join</button></div>
      </div>
    </div>
  );
}

function TodaySchedule() {
  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">Today's Schedule</h3>
      <div className="space-y-4">
        {mockEvents.map((event) => {
          const start = new Date(event.start);
          const end = new Date(event.end);
          return (
            <div key={event.id} className="flex gap-4 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
              <div className="flex-shrink-0 w-20 text-right text-sm text-slate-500 dark:text-slate-400">
                {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(start)}
              </div>
              <div className="flex-1 border-l-2 border-slate-200 dark:border-slate-700 pl-4">
                <p className="font-medium text-slate-900 dark:text-slate-100">{event.title}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(start)} - {new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", hour12: true }).format(end)}
                  {event.location && ` • ${event.location}`}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TaskList({ title, tasks, emptyMessage, showOverdueOnly = false }: { title: string; tasks: Task[]; emptyMessage: string; showOverdueOnly?: boolean }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const filteredTasks = showOverdueOnly
    ? tasks.filter((task) => task.status !== "completed" && task.due_at && isPast(new Date(task.due_at)))
    : tasks;

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">{title}</h3>
      {filteredTasks.length > 0 ? (
        <ul className="space-y-3">
          {filteredTasks.map((task) => {
            const isOverdue = mounted && task.due_at && task.status !== "completed" && isPast(new Date(task.due_at));
            return (
              <li key={task.id} className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <input
                  type="checkbox"
                  checked={task.status === "completed"}
                  readOnly
                  className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{task.title}</p>
                  {task.due_at && (
                    <p className={`text-xs ${isOverdue ? "text-red-600 dark:text-red-400" : "text-slate-500 dark:text-slate-400"}`}>
                      Due {formatDistanceToNow(new Date(task.due_at), { addSuffix: true })}
                    </p>
                  )}
                </div>
                {isOverdue && (
                  <span className="px-2 py-0.5 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 rounded-full text-xs">Overdue</span>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-4">{emptyMessage}</p>
      )}
    </div>
  );
}

function EmailList({ title, emails }: { title: string; emails: any[] }) {
  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">{title}</h3>
      <ul className="space-y-3">
        {emails.map((email) => (
          <li key={email.id} className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{email.from}</p>
                <p className="text-sm text-slate-600 dark:text-slate-300 truncate">{email.subject}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-1">{email.snippet}</p>
              </div>
              {email.important && (
                <span className="px-2 py-0.5 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 rounded-full text-xs">Important</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function QuickActions() {
  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">Quick Actions</h3>
      <div className="grid grid-cols-2 gap-3">
        <button className="btn-secondary w-full justify-start gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          New Task
        </button>
        <button className="btn-secondary w-full justify-start gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
          New Event
        </button>
        <button className="btn-secondary w-full justify-start gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
          Compose Email
        </button>
        <button className="btn-primary w-full justify-start gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          Morning Briefing
        </button>
      </div>
    </div>
  );
}

function AIRecommendation({ pendingCount, overdueCount }: { pendingCount: number; overdueCount: number }) {
  return (
    <div className="card p-6 border-primary-200 dark:border-primary-800 bg-primary-50/50 dark:bg-primary-900/10">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
          <svg className="w-5 h-5 text-primary-700 dark:text-primary-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">AI Recommendation</h3>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
            {overdueCount > 0
              ? `You have <strong>${overdueCount} overdue task${overdueCount !== 1 ? "s" : ""}</strong> that need immediate attention.`
              : pendingCount > 0
              ? `Focus on your <strong>${pendingCount} pending task${pendingCount !== 1 ? "s" : ""}</strong> for today.`
              : "All caught up! Enjoy your free time."}
          </p>
          <button className="btn-ghost text-sm mt-2">Chat about this</button>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: tasksData, isLoading: tasksLoading, error: tasksError, refetch: refetchTasks } = useQuery({
    queryKey: ["dashboard-tasks"],
    queryFn: () => tasksApi.list({ page_size: 50 }),
    staleTime: 1000 * 60 * 2,
  });

  const tasks = tasksData?.tasks || [];
  const now = new Date();

  const pendingTasks = tasks.filter((t) => t.status !== "completed" && (!t.due_at || new Date(t.due_at) >= now));
  const overdueTasks = tasks.filter((t) => t.status !== "completed" && t.due_at && new Date(t.due_at) < now);
  const completedTasks = tasks.filter((t) => t.status === "completed");
  const importantEmails = mockEmails.filter((e) => e.important);

  if (tasksLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6"><TimeDate /><NextEvent /></div>
          <div className="space-y-6"><AIRecommendation pendingCount={0} overdueCount={0} /><QuickActions /></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6"><TodaySchedule /><TaskList title="Pending Tasks" tasks={[]} emptyMessage="Loading..." /></div>
          <div className="space-y-6"><TaskList title="Overdue Tasks (0)" tasks={[]} emptyMessage="Loading..." showOverdueOnly /><EmailList title="Important Emails" emails={[]} /><EmailList title="Action Required" emails={[]} /></div>
        </div>
      </div>
    );
  }

  if (tasksError) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6"><TimeDate /><NextEvent /></div>
          <div className="space-y-6"><AIRecommendation pendingCount={0} overdueCount={0} /><QuickActions /></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6"><TodaySchedule /><TaskList title="Pending Tasks" tasks={[]} emptyMessage="Failed to load tasks" /></div>
          <div className="space-y-6"><TaskList title="Overdue Tasks (0)" tasks={[]} emptyMessage="Failed to load tasks" showOverdueOnly /><EmailList title="Important Emails" emails={importantEmails} /><EmailList title="Action Required" emails={mockEmails.filter((e) => e.subject.includes("Action"))} /></div>
        </div>
        <div className="card p-6 text-center text-red-600 dark:text-red-400">
          Failed to load tasks: {tasksError instanceof Error ? tasksError.message : "Unknown error"}
          <button onClick={() => refetchTasks()} className="btn-primary mt-4">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6"><TimeDate /><NextEvent /></div>
        <div className="space-y-6"><AIRecommendation pendingCount={pendingTasks.length} overdueCount={overdueTasks.length} /><QuickActions /></div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <TodaySchedule />
          <TaskList title="Pending Tasks" tasks={pendingTasks.slice(0, 5)} emptyMessage="No pending tasks" />
        </div>
        <div className="space-y-6">
          {overdueTasks.length > 0 && (
            <TaskList title={`Overdue Tasks (${overdueTasks.length})`} tasks={overdueTasks.slice(0, 3)} emptyMessage="No overdue tasks" showOverdueOnly />
          )}
          <EmailList title="Important Emails" emails={importantEmails} />
          <EmailList title="Action Required" emails={mockEmails.filter((e) => e.subject.includes("Action"))} />
        </div>
      </div>
    </div>
  );
}