import { Mail, ArrowRight, Zap, Users, TrendingUp, Star } from "lucide-react";
import Link from "next/link";

export default function Home() {
  const featuredPosts = [
    {
      title: "The Renaissance of Creative AI",
      excerpt:
        "Exploring how artificial intelligence is transforming the creative landscape and empowering artists to push boundaries.",
      author: "Sarah Chen",
      avatar: "SC",
      date: "May 28, 2026",
      readTime: "8 min",
      category: "Technology",
      gradient: "from-violet-500 to-purple-500",
    },
    {
      title: "Building Products People Love",
      excerpt:
        "The secret isn't in the features. It's in understanding the human connection behind every interaction.",
      author: "Marcus Johnson",
      avatar: "MJ",
      date: "May 25, 2026",
      readTime: "6 min",
      category: "Design",
      gradient: "from-cyan-500 to-blue-500",
    },
    {
      title: "The New Era of Digital Communities",
      excerpt:
        "How decentralized platforms are reshaping the way we connect, collaborate, and build together online.",
      author: "Elena Rodriguez",
      avatar: "ER",
      date: "May 22, 2026",
      readTime: "10 min",
      category: "Culture",
      gradient: "from-fuchsia-500 to-pink-500",
    },
  ];

  const stats = [
    { icon: Users, label: "Active Readers", value: "50K+" },
    { icon: TrendingUp, label: "Stories Published", value: "10K+" },
    { icon: Star, label: "Creator Earnings", value: "$2M+" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Hero Section */}
      <section className="py-20 sm:py-32">
        <div className="text-center max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-500/10 border border-violet-500/20 mb-8">
            <Zap className="w-4 h-4 text-violet-400" />
            <span className="text-sm text-violet-300">Join 50,000+ readers</span>
          </div>

          <h1 className="text-5xl sm:text-7xl lg:text-8xl font-bold mb-6 leading-tight">
            <span className="bg-gradient-to-r from-white via-violet-200 to-cyan-200 bg-clip-text text-transparent">
              Stories that
            </span>
            <br />
            <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
              inspire change
            </span>
          </h1>

          <p className="text-xl text-slate-400 mb-12 max-w-2xl mx-auto leading-relaxed">
            Discover curated insights from visionary creators, innovators, and thought leaders shaping tomorrow&apos;s world.
          </p>

          {/* Email Signup */}
          <div className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto mb-4">
            <input
              type="email"
              placeholder="Enter your email"
              className="flex-1 px-5 py-4 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent backdrop-blur-sm"
            />
            <button className="px-6 py-4 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-xl text-white hover:shadow-lg hover:shadow-violet-500/50 transition-all flex items-center justify-center gap-2 whitespace-nowrap group">
              <Mail size={18} />
              <span>Subscribe</span>
              <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
          <p className="text-sm text-slate-500">
            Free forever. Unsubscribe with one click.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-20 max-w-3xl mx-auto">
          {stats.map((stat, index) => (
            <div key={index} className="relative group">
              <div className="absolute inset-0 bg-gradient-to-r from-violet-600/20 to-fuchsia-600/20 rounded-2xl blur-xl group-hover:blur-2xl transition-all"></div>
              <div className="relative bg-slate-900/50 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-center hover:border-violet-500/50 transition-all">
                <stat.icon className="w-8 h-8 mx-auto mb-3 text-violet-400" />
                <div className="text-3xl font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent mb-1">
                  {stat.value}
                </div>
                <div className="text-sm text-slate-400">{stat.label}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Featured Posts */}
      <section className="py-20">
        <div className="flex items-center justify-between mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-white">Featured Stories</h2>
          <button className="text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-2">
            View all
            <ArrowRight size={16} />
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {featuredPosts.map((post, index) => (
            <article key={index} className="group relative">
              <div className={`absolute inset-0 bg-gradient-to-r ${post.gradient} opacity-0 group-hover:opacity-10 rounded-3xl blur-xl transition-all`}></div>
              <div className="relative bg-slate-900/50 backdrop-blur-sm border border-white/10 rounded-3xl p-6 hover:border-white/20 transition-all h-full flex flex-col">
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-10 h-10 rounded-full bg-gradient-to-r ${post.gradient} flex items-center justify-center text-white text-sm font-bold`}>
                    {post.avatar}
                  </div>
                  <div>
                    <div className="text-sm text-white">{post.author}</div>
                    <div className="text-xs text-slate-500">{post.date}</div>
                  </div>
                </div>

                <div className={`inline-flex items-center px-3 py-1 rounded-full bg-gradient-to-r ${post.gradient} bg-opacity-10 text-xs mb-4 w-fit`}>
                  <span className="text-white">{post.category}</span>
                </div>

                <h3 className="text-xl font-bold text-white mb-3 group-hover:text-transparent group-hover:bg-gradient-to-r group-hover:from-violet-400 group-hover:to-cyan-400 group-hover:bg-clip-text transition-all cursor-pointer">
                  {post.title}
                </h3>

                <p className="text-slate-400 mb-4 leading-relaxed flex-grow">
                  {post.excerpt}
                </p>

                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <span className="text-sm text-slate-500">{post.readTime} read</span>
                  <button className="text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1 group">
                    Read more
                    <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-3xl blur-2xl opacity-20 group-hover:opacity-30 transition-all"></div>
          <div className="relative bg-gradient-to-br from-slate-900 to-slate-800 border border-white/10 rounded-3xl p-12 sm:p-16 text-center overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/10 rounded-full blur-3xl"></div>
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl"></div>

            <div className="relative z-10">
              <h2 className="text-4xl sm:text-5xl font-bold mb-4">
                <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                  Start your creative journey
                </span>
              </h2>
              <p className="text-slate-400 mb-8 max-w-xl mx-auto text-lg">
                Join a community of passionate creators. Share your story, build your audience, and earn from your craft.
              </p>
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-full text-white hover:shadow-lg hover:shadow-violet-500/50 transition-all group"
              >
                <span>Start Writing Today</span>
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
