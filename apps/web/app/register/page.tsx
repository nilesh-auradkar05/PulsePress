"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Mail, User, CheckCircle2 } from "lucide-react";

import { useAuth } from "../components/AuthProvider";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();
  const { register } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, name);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setSubmitting(false);
    }
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
            <p className="text-slate-400">Create a local passwordless demo account</p>
            </div>

            {error && (
              <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

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

              <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-200">
                This local account is for development only. Production registration is handled by
                Cognito with the hosted PKCE flow.
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl text-white hover:shadow-lg hover:shadow-violet-500/50 transition-all flex items-center justify-center gap-2 group disabled:opacity-60"
              >
                <span>{submitting ? "Creating account…" : "Create account"}</span>
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </button>
            </form>

            <div className="mt-8 text-center text-sm">
              <span className="text-slate-400">Already have an account? </span>
              <Link href="/login" className="text-violet-400 hover:text-violet-300 transition-colors">
                Sign in
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
