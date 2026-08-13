"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/lib/auth-store";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { checkAuth } = useAuthStore();
  const hasCheckedRef = useRef(false);

  // Only run initial auth check once on app load
  useEffect(() => {
    if (hasCheckedRef.current) return;
    hasCheckedRef.current = true;
    checkAuth();
  }, [checkAuth]);

  return <>{children}</>;
}