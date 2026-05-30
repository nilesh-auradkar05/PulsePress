"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X, Sparkles } from "lucide-react";

import { useAuth } from "./AuthProvider";

/**
 * Shared page chrome (animated background, header nav, footer). Ported from the
 * developer-provided design's `Layout.tsx` (react-router) to the Next.js App
 * Router: `<Outlet/>` → `{children}`, outlet context → `useAuth()`.
 */
export function SiteShell({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Animated background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-violet-500/10 rounded-full blur-3xl animate-pulse"></div>
        <div
          className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-cyan-500/10 rounded-full blur-3xl animate-pulse"
          style={{ animationDelay: "1s" }}
        ></div>
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-white/10 backdrop-blur-sm bg-slate-950/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="relative">
              <Sparkles className="w-7 h-7 text-violet-400 group-hover:text-cyan-400 transition-colors" />
              <div className="absolute inset-0 bg-violet-400 blur-xl opacity-20 group-hover:opacity-40 transition-opacity"></div>
            </div>
            <span className="text-2xl bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent font-bold tracking-tight">
              PulsePress
            </span>
          </Link>

          {/* Desktop navigation */}
          <nav className="hidden sm:flex items-center gap-6">
            {isLoggedIn ? (
              <>
                <Link href="/" className="text-slate-300 hover:text-white transition-colors">
                  Home
                </Link>
                <button
                  onClick={handleLogout}
                  className="text-slate-300 hover:text-white transition-colors"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="text-slate-300 hover:text-white transition-colors">
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="relative px-6 py-2.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-full text-white hover:shadow-lg hover:shadow-violet-500/50 transition-all group overflow-hidden"
                >
                  <span className="relative z-10">Get Started</span>
                  <div className="absolute inset-0 bg-gradient-to-r from-fuchsia-600 to-cyan-600 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                </Link>
              </>
            )}
          </nav>

          {/* Mobile menu button */}
          <button
            className="sm:hidden text-slate-300 hover:text-white"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-label="Toggle menu"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile navigation */}
        {isMenuOpen && (
          <div className="sm:hidden border-t border-white/10 bg-slate-950/80 backdrop-blur-sm">
            <nav className="px-4 py-4 flex flex-col gap-4">
              {isLoggedIn ? (
                <>
                  <Link
                    href="/"
                    className="text-slate-300 hover:text-white transition-colors"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    Home
                  </Link>
                  <button
                    onClick={() => {
                      handleLogout();
                      setIsMenuOpen(false);
                    }}
                    className="text-left text-slate-300 hover:text-white transition-colors"
                  >
                    Sign out
                  </button>
                </>
              ) : (
                <>
                  <Link
                    href="/login"
                    className="text-slate-300 hover:text-white transition-colors"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    Sign in
                  </Link>
                  <Link
                    href="/register"
                    className="bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white px-6 py-2.5 rounded-full hover:shadow-lg hover:shadow-violet-500/50 transition-all text-center"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    Get Started
                  </Link>
                </>
              )}
            </nav>
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="relative z-10">{children}</main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-6 h-6 text-violet-400" />
                <span className="text-2xl bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent font-bold">
                  PulsePress
                </span>
              </div>
              <p className="text-slate-400 text-sm">
                Where ideas converge and stories come alive
              </p>
            </div>
            <div className="flex gap-6 text-sm text-slate-400">
              <a href="#" className="hover:text-white transition-colors">
                About
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Privacy
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Terms
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Contact
              </a>
            </div>
          </div>
          <div className="mt-8 text-sm text-slate-500">
            © 2026 PulsePress. Crafted with passion.
          </div>
        </div>
      </footer>
    </div>
  );
}
