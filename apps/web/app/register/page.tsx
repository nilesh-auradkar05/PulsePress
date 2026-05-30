"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Lock, Mail, User, CheckCircle2 } from "lucide-react";

import { useAuth } from "../components/AuthProvider";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const router = useRouter();
  const { login } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Placeholder auth — real Cognito PKCE flow lands in a later sprint.
    login();
    router.push("/");
  };

  const benefits = [
    "Access to exclusive premium content",
    "Weekly curated newsletter",
    "Connect with thought leaders",
    "Ad-free reading experience",
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-16 sm:py-24">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        {/* Left Side - Benefits */}
        <div className="hidden lg:block">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-3xl blur-2xl opacity-20"></div>
            <div className="relative bg-slate-900/50 backdrop-blur-sm border border-white/10 rounded-3xl p-10">
              <h2 className="text-3xl font-bold mb-6">
                <span className="bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
                  Join the community
                </span>
              </h2>
              <p className="text-slate-400 mb-8 leading-relaxed">
                Become part of a growing community of readers and creators shaping the future of storytelling.
              </p>

              <div className="space-y-4 mb-8">
                {benefits.map((benefit, index) => (
                  <div key={index} className="flex items-start gap-3">
                    <div className="mt-1">
                      <CheckCircle2 className="w-5 h-5 text-violet-400" />
                    </div>
                    <span className="text-slate-300">{benefit}</span>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-4 pt-8 border-t border-white/10">
                <div>
                  <div className="text-2xl font-bold text-white mb-1">50K+</div>
                  <div className="text-sm text-slate-400">Active readers</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-white mb-1">10K+</div>
                  <div className="text-sm text-slate-400">Stories shared</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side - Form */}
        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-3xl blur-2xl opacity-20"></div>
          <div className="relative bg-slate-900/50 backdrop-blur-sm border border-white/10 rounded-3xl p-8 sm:p-10">
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold mb-3">
                <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                  Create account
                </span>
              </h1>
              <p className="text-slate-400">Start your journey in seconds</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="name" className="block mb-2 text-slate-300">
                  Full name
                </label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
                    placeholder="John Doe"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="email" className="block mb-2 text-slate-300">
                  Email address
                </label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
                    placeholder="your@email.com"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="block mb-2 text-slate-300">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
                    placeholder="Create a password"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-2">Must be at least 8 characters</p>
              </div>

              <div className="text-sm">
                <label className="flex items-start gap-2 cursor-pointer text-slate-400">
                  <input
                    type="checkbox"
                    required
                    className="w-4 h-4 mt-0.5 rounded border-white/10 bg-white/5 text-violet-600 focus:ring-violet-500 focus:ring-offset-0"
                  />
                  <span>
                    I agree to the{" "}
                    <a href="#" className="text-violet-400 hover:text-violet-300 transition-colors">
                      Terms of Service
                    </a>{" "}
                    and{" "}
                    <a href="#" className="text-violet-400 hover:text-violet-300 transition-colors">
                      Privacy Policy
                    </a>
                  </span>
                </label>
              </div>

              <button
                type="submit"
                className="w-full py-3.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl text-white hover:shadow-lg hover:shadow-violet-500/50 transition-all flex items-center justify-center gap-2 group"
              >
                <span>Create account</span>
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </button>
            </form>

            <div className="mt-8 text-center text-sm">
              <span className="text-slate-400">Already have an account? </span>
              <Link href="/login" className="text-violet-400 hover:text-violet-300 transition-colors">
                Sign in
              </Link>
            </div>

            <div className="mt-8 pt-8 border-t border-white/10">
              <p className="text-center text-sm text-slate-500 mb-6">Or continue with</p>
              <div className="flex gap-3">
                <button className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all flex items-center justify-center gap-2 text-slate-300 hover:text-white">
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path
                      fill="currentColor"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="currentColor"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="currentColor"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="currentColor"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                </button>
                <button className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all flex items-center justify-center gap-2 text-slate-300 hover:text-white">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
