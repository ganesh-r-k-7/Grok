"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";

export default function SchedulePage() {
  const [events, setEvents] = useState<any[]>([]);
  const [state, setState] = useState("loading");
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const start = new Date();
    start.setDate(start.getDate() - 7);
    const end = new Date();
    end.setDate(end.getDate() + 30);
    const params = new URLSearchParams({ time_min: start.toISOString(), time_max: end.toISOString(), max_results: "50" });
    fetch(base + "/api/v1/calendar/events?" + params.toString(), { credentials: "include" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => { setEvents(data); setState("ready"); })
      .catch(() => setState("error"));
  }, []);
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Schedule</h1>
        <button className="btn-secondary" onClick={() => window.location.reload()}>Refresh</button>
      </div>
      <Card className="p-6">
        {state === "loading" && <p className="text-slate-500">Loading your calendar...</p>}
        {state === "error" && <p className="text-slate-500">Could not load events. Check your Google Calendar connection.</p>}
        {state === "ready" && events.length === 0 && <p className="text-slate-500">No upcoming events.</p>}
        {state === "ready" && events.length > 0 && <ul className="divide-y divide-slate-200 dark:divide-slate-700">
          {events.map((event) => <li key={event.id} className="py-4"><p className="font-medium text-slate-900 dark:text-slate-100">{event.summary || "Untitled event"}</p><p className="text-sm text-slate-500">{event.start.date_time ? new Date(event.start.date_time).toLocaleString() : "All day"}{event.location ? " • " + event.location : ""}</p></li>)}
        </ul>}
      </Card>
    </div>
  );
}