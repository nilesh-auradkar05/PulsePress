"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sparkles } from "lucide-react";

import { useAuth } from "./AuthProvider";

// Routes anyone may see. Everything else requires a valid session.
const PUBLIC_ROUTES = new Set(["/", "/login", "/register"]);
const HOME_ROUTE = "/home";

function isPublic(pathname: string): boolean {
  return PUBLIC_ROUTES.has(pathname);
}

/**
 * Client-side route guard. Gates every non-public route behind a valid auth
 * session and keeps that decision correct across browser back/forward:
 *
 * - SPA back/forward re-renders this component, so a signed-out user pressing
 *   Back to `/home` is bounced to `/login` before any protected content paints.
 * - `pageshow` (with `persisted`) catches bfcache restores, where React state is
 *   frozen — we re-sync against the stored token via `revalidate()`.
 *
 * This is defense-in-depth for the demo UX, not a security boundary: the API
 * validates the JWT on every request and is the real authority.
 */
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, loading, revalidate } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        revalidate();
      }
    };

    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, [revalidate]);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!isLoggedIn && !isPublic(pathname)) {
      router.replace("/login");
      return;
    }

    // Already authenticated: keep auth screens out of reach (incl. via Back).
    if (isLoggedIn && (pathname === "/login" || pathname === "/register")) {
      router.replace(HOME_ROUTE);
    }
  }, [isLoggedIn, loading, pathname, router]);

  const blocked =
    (!isLoggedIn && !isPublic(pathname)) ||
    (isLoggedIn && (pathname === "/login" || pathname === "/register"));

  // While auth is resolving, or while a redirect is in flight, never flash the
  // protected (or wrong) page.
  if ((loading && !isPublic(pathname)) || blocked) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Sparkles className="h-8 w-8 animate-pulse text-violet-400" />
      </div>
    );
  }

  return <>{children}</>;
}
