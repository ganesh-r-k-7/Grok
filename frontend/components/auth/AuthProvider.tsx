"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/lib/auth-store";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoading, checkAuth } = useAuthStore();
  const hasCheckedRef = useRef(false);

  // Only run initial auth check once on app load, not on every navigation or isLoading change
  useEffect(() => {
    if (hasCheckedRef.current) return;
    if (isLoading) return;
    
    hasCheckedRef.current = true;
    checkAuth();
  }, [checkAuth, isLoading]);

  return <>{children}</>;
}