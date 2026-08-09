"use client";

import { Suspense } from "react";
import { SearchParamsWrapper } from "./SearchParamsWrapper";

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent" />
        </div>
      }
    >
      <SearchParamsWrapper />
    </Suspense>
  );
}