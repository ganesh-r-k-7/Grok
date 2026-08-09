import { redirect } from "next/navigation";
import { Card } from "@/components/ui/Card";

export default function CallbackPage() {
  redirect("/dashboard");

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
      <Card className="w-full max-w-md p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent mx-auto mb-4"></div>
        <p className="text-slate-600 dark:text-slate-400">Completing sign in...</p>
      </Card>
    </div>
  );
}