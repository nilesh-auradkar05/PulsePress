"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Compass, Search } from "lucide-react";

import { api, type Post, type Publication } from "../lib/api";
import { formatDate, initials } from "../lib/content";

type DiscoverablePost = Post & {
  publication: Publication;
};

async function fetchExploreData(): Promise<DiscoverablePost[]> {
  const publicationList = await api.listPublications();
  const postLists = await Promise.all(
    publicationList.items.map(async (publication) => {
      const list = await api.listPosts(publication.id, { status: "published" });
      return list.items
        .filter((post) => post.status === "published")
        .map((post) => ({ ...post, publication }));
    }),
  );
  return postLists.flat();
}

export default function Explore() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const [posts, setPosts] = useState<DiscoverablePost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchExploreData()
      .then((items) => {
        if (!cancelled) setPosts(items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load published posts");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return posts;
    return posts.filter((post) => {
      const haystack = `${post.title} ${post.slug} ${post.publication.name} ${post.publication.handle}`;
      return haystack.toLowerCase().includes(needle);
    });
  }, [posts, query]);

  const updateSearch = (value: string) => {
    const next = value.trim();
    router.replace(next ? `/explore?q=${encodeURIComponent(next)}` : "/explore");
  };

  const submitSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const next = String(formData.get("q") ?? "").trim();
    router.push(next ? `/explore?q=${encodeURIComponent(next)}` : "/explore");
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto mb-10 max-w-2xl text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-500/20 bg-violet-500/10 px-4 py-2">
          <Compass className="h-4 w-4 text-violet-400" />
          <span className="text-sm text-violet-300">Explore</span>
        </div>
        <h1 className="mb-4 text-4xl font-bold sm:text-5xl">
          <span className="bg-gradient-to-r from-white via-violet-200 to-cyan-200 bg-clip-text text-transparent">
            Published PulsePress stories
          </span>
        </h1>
        <p className="text-lg text-slate-400">
          Database-backed posts from active publications.
        </p>
      </div>

      <form onSubmit={submitSearch} className="mx-auto mb-8 flex max-w-xl gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            name="q"
            type="search"
            value={query}
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="Search title or publication"
            className="w-full rounded-lg border border-white/10 bg-white/5 py-3 pl-11 pr-4 text-sm text-white placeholder:text-slate-500 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet-500"
          />
        </div>
      </form>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-8 text-slate-300">
          Loading published posts...
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-10 text-center text-slate-400">
          No published posts match this view.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {visible.map((post) => (
            <article
              key={post.id}
              className="rounded-lg border border-white/10 bg-slate-900/50 p-6 transition-colors hover:border-white/20"
            >
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-violet-600 text-sm font-bold text-white">
                  {initials(post.publication.name)}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm text-white">{post.publication.name}</div>
                  <div className="text-xs text-slate-500">
                    Published {formatDate(post.published_at)}
                  </div>
                </div>
              </div>

              <div className="mb-4 inline-flex rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                {post.visibility}
              </div>

              <h2 className="mb-3 text-xl font-bold text-white">{post.title}</h2>
              <p className="mb-5 text-sm text-slate-400">@{post.publication.handle}</p>

              <Link
                href={`/posts/${post.id}`}
                className="inline-flex items-center gap-1 text-sm text-violet-300 hover:text-violet-200"
              >
                Read more
                <ArrowRight size={14} />
              </Link>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
