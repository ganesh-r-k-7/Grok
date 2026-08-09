"use client";

import { useSearchParams } from "next/navigation";
import { RegisterForm } from "./RegisterForm";

export function SearchParamsWrapper() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/dashboard";

  return <RegisterForm callbackUrl={callbackUrl} />;
}