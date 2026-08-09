"use client";

import { useSearchParams } from "next/navigation";
import { LoginForm } from "./LoginForm";

export function SearchParamsWrapper() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/dashboard";

  return <LoginForm callbackUrl={callbackUrl} />;
}