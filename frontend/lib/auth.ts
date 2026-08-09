// Auth utilities for client-side

export function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie.split("; ");
  const csrfCookie = cookies.find((c) => c.startsWith("grokcsrf="));
  return csrfCookie ? csrfCookie.split("=")[1] : null;
}

export function getAuthHeaders(): Record<string, string> {
  const csrfToken = getCsrfToken();
  return csrfToken ? { "X-CSRF-Token": csrfToken } : {};
}