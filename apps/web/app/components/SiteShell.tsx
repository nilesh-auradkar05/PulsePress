"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ComponentType } from "react";
import { useEffect, useState } from "react";
import {
  ChevronDown,
  LifeBuoy,
  LogOut,
  Menu,
  Monitor,
  Moon,
  PenSquare,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  Sun,
  UserCircle,
  X,
} from "lucide-react";

import { useAuth } from "./AuthProvider";
import { RouteGuard } from "./RouteGuard";
import { initials } from "../lib/content";

type AppearanceMode = "current" | "system" | "light";
type ProfilePanel = "menu" | "settings" | "support";

const APPEARANCE_OPTIONS: {
  value: AppearanceMode;
  label: string;
  icon: ComponentType<{ size?: number; className?: string }>;
}[] = [
  { value: "current", label: "Current", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
];

/**
 * Shared page chrome (animated background, header nav, footer). Ported from the
 * developer-provided design's `Layout.tsx` (react-router) to the Next.js App
 * Router: `<Outlet/>` → `{children}`, outlet context → `useAuth()`.
 */
export function SiteShell({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, user, logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [profilePanel, setProfilePanel] = useState<ProfilePanel>("menu");
  const [appearance, setAppearance] = useState<AppearanceMode>(() => {
    if (typeof window === "undefined") return "current";
    const stored = window.localStorage.getItem("pulsepress_appearance");
    return stored === "current" || stored === "system" || stored === "light"
      ? stored
      : "current";
  });
  const router = useRouter();

  useEffect(() => {
    const applyTheme = () => {
      const systemLight = window.matchMedia("(prefers-color-scheme: light)").matches;
      const resolved = appearance === "system" && systemLight ? "light" : appearance;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved === "light" ? "light" : "dark";
      window.localStorage.setItem("pulsepress_appearance", appearance);
    };

    applyTheme();

    if (appearance !== "system") {
      return;
    }

    const media = window.matchMedia("(prefers-color-scheme: light)");
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [appearance]);

  const handleLogout = () => {
    setIsProfileOpen(false);
    logout();
    router.push("/");
  };

  const handleSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchQuery.trim();
    router.push(query ? `/explore?q=${encodeURIComponent(query)}` : "/explore");
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    const query = value.trim();
    router.replace(query ? `/explore?q=${encodeURIComponent(query)}` : "/explore");
  };

  const openProfile = () => {
    setIsProfileOpen((open) => {
      const next = !open;
      if (next) {
        setProfilePanel("menu");
      }
      return next;
    });
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
      <header className="relative z-50 border-b border-white/10 backdrop-blur-sm bg-slate-950/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link href={isLoggedIn ? "/home" : "/"} className="flex items-center gap-2 group">
            <div className="relative">
              <Sparkles className="w-7 h-7 text-violet-400 group-hover:text-cyan-400 transition-colors" />
              <div className="absolute inset-0 bg-violet-400 blur-xl opacity-20 group-hover:opacity-40 transition-opacity"></div>
            </div>
            <span className="text-2xl bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent font-bold tracking-tight">
              PulsePress
            </span>
          </Link>

          {/* Search (signed-in only) */}
          {isLoggedIn && (
            <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-md mx-8">
              <div className="relative w-full">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(event) => handleSearchChange(event.target.value)}
                  placeholder="Search published posts..."
                  className="w-full pl-11 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-full text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
                />
              </div>
            </form>
          )}

          {/* Desktop navigation */}
          <nav className="hidden sm:flex items-center gap-6">
            {isLoggedIn ? (
              <>
                <Link href="/home" className="text-slate-300 hover:text-white transition-colors">
                  Dashboard
                </Link>
                <Link href="/explore" className="text-slate-300 hover:text-white transition-colors">
                  Explore
                </Link>
                <Link
                  href="/posts/new"
                  className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-full text-sm text-white hover:shadow-lg hover:shadow-violet-500/50 transition-all"
                >
                  <PenSquare size={16} />
                  <span>New Post</span>
                </Link>
                {user && (
                  <div className="relative z-[110]">
                    <button
                      type="button"
                      onClick={openProfile}
                      className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 p-1 pr-2 text-sm text-white hover:bg-white/10"
                      aria-expanded={isProfileOpen}
                      aria-label="Open profile menu"
                    >
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 text-sm font-bold text-white">
                        {initials(user.display_name)}
                      </span>
                      <ChevronDown size={14} className="text-slate-400" />
                    </button>
                    {isProfileOpen && (
                      <div className="absolute right-0 top-12 z-[120] w-[360px] max-w-[calc(100vw-2rem)] rounded-lg border border-white/10 bg-slate-950 p-3 opacity-100 shadow-2xl shadow-black/60 ring-1 ring-black/40">
                        <div className="flex items-start justify-between gap-3 border-b border-white/10 px-2 pb-3">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-white">{user.display_name}</div>
                            <div className="truncate text-xs text-slate-400">{user.email}</div>
                          </div>
                          {profilePanel !== "menu" && (
                            <button
                              type="button"
                              onClick={() => {
                                setProfilePanel("menu");
                              }}
                              className="rounded-md p-1 text-slate-400 hover:bg-white/5 hover:text-white"
                              aria-label="Back to profile menu"
                            >
                              <X size={16} />
                            </button>
                          )}
                        </div>

                        {profilePanel === "menu" && (
                          <>
                            <div className="border-b border-white/10 py-3">
                              <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                                Appearance
                              </div>
                              <div className="grid grid-cols-3 gap-2">
                                {APPEARANCE_OPTIONS.map((option) => {
                                  const Icon = option.icon;
                                  return (
                                    <button
                                      key={option.value}
                                      type="button"
                                      onClick={() => setAppearance(option.value)}
                                      className={`flex flex-col items-center gap-1 rounded-md border px-2 py-2 text-xs transition-colors ${
                                        appearance === option.value
                                          ? "border-violet-400/50 bg-violet-500/15 text-white"
                                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white"
                                      }`}
                                    >
                                      <Icon size={16} />
                                      {option.label}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>

                            <div className="border-b border-white/10 py-2">
                              <Link
                                href="/home"
                                onClick={() => setIsProfileOpen(false)}
                                className="flex items-center gap-2 rounded-md px-2 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white"
                              >
                                <UserCircle size={16} />
                                Dashboard
                              </Link>
                              <button
                                type="button"
                                onClick={() => setProfilePanel("settings")}
                                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-slate-300 hover:bg-white/5 hover:text-white"
                              >
                                <Settings size={16} />
                                Settings
                              </button>
                              <button
                                type="button"
                                onClick={() => setProfilePanel("support")}
                                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-slate-300 hover:bg-white/5 hover:text-white"
                              >
                                <LifeBuoy size={16} />
                                Support
                              </button>
                            </div>

                            <button
                              type="button"
                              onClick={handleLogout}
                              className="mt-2 flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-slate-300 hover:bg-white/5 hover:text-white"
                            >
                              <LogOut size={16} />
                              Sign out
                            </button>
                          </>
                        )}

                        {profilePanel === "settings" && (
                          <div className="space-y-3 py-3">
                            <button
                              type="button"
                              disabled
                              className="flex w-full items-center justify-between rounded-md border border-white/10 bg-white/5 px-3 py-2 text-left text-sm text-slate-500"
                            >
                              Change password
                              <span className="text-xs text-slate-500">Cognito workflow required</span>
                            </button>
                            <button
                              type="button"
                              disabled
                              className="flex w-full items-center justify-between rounded-md border border-white/10 bg-white/5 px-3 py-2 text-left text-sm text-slate-500"
                            >
                              Change username
                              <span className="text-xs text-slate-500">Profile API required</span>
                            </button>
                            <button
                              type="button"
                              disabled
                              className="flex w-full items-center justify-between rounded-md border border-white/10 bg-white/5 px-3 py-2 text-left text-sm text-slate-500"
                            >
                              Unsubscribe all publications
                              <span className="text-xs text-slate-500">Bulk API required</span>
                            </button>
                            <button
                              type="button"
                              disabled
                              className="flex w-full items-center gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-left text-sm text-amber-200/60"
                            >
                              <ShieldAlert size={16} />
                              Delete all owned published publications
                            </button>
                            <button
                              type="button"
                              disabled
                              className="flex w-full items-center gap-2 rounded-md border border-red-500/25 bg-red-500/10 px-3 py-2 text-left text-sm text-red-200/60"
                            >
                              <ShieldAlert size={16} />
                              Delete account permanently
                            </button>
                          </div>
                        )}

                        {profilePanel === "support" && (
                          <div className="space-y-3 py-3 text-sm">
                            <div className="rounded-md border border-white/10 bg-white/5 px-3 py-2">
                              <div className="text-xs uppercase tracking-wide text-slate-500">Email</div>
                              <a
                                href="mailto:support@pulsepress.test"
                                className="mt-1 block text-cyan-200 hover:text-cyan-100"
                              >
                                support@pulsepress.test
                              </a>
                            </div>
                            <div className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-slate-300">
                              <div className="mb-2 font-semibold text-white">Troubleshooting</div>
                              <p className="text-xs leading-5 text-slate-400">
                                Refresh the page, confirm the API is running on port 8000, sign out and
                                back in, then retry the action. If content is missing, check that you
                                are signed in as the publication owner.
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
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
                  {user && (
                    <span className="text-slate-400">Hi, {user.display_name}</span>
                  )}
                  <Link
                    href="/home"
                    className="text-slate-300 hover:text-white transition-colors"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    Dashboard
                  </Link>
                  <Link
                    href="/posts/new"
                    className="text-slate-300 hover:text-white transition-colors"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    New Post
                  </Link>
                  <Link
                    href="/explore"
                    className="text-slate-300 hover:text-white transition-colors"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    Explore
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
      <main className="relative z-10">
        <RouteGuard>{children}</RouteGuard>
      </main>

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
          </div>
          <div className="mt-8 text-sm text-slate-500">
            © 2026 PulsePress. Crafted with passion.
          </div>
        </div>
      </footer>
    </div>
  );
}
