"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, BookOpen, Eye, Layers, Pencil, Send, TrendingUp } from "lucide-react";

import { api, type Post, type PostStatus, type PostVisibility, type Publication } from "../lib/api";
import { formatDate, statusLabel } from "../lib/content";

type StatusFilter = "all" | "published" | "draft" | "archived";
type VisibilityFilter = "all" | PostVisibility;

type DashboardPost = Post & {
  publication: Publication;
};

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All Status" },
  { value: "published", label: "Published" },
  { value: "draft", label: "Draft" },
  { value: "archived", label: "Archived" },
];

function statusClasses(status: PostStatus): string {
  if (status === "published") {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  }
  if (status === "draft") {
    return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  }
  return "border-slate-500/20 bg-slate-500/10 text-slate-300";
}

async function fetchDashboardData(): Promise<{
  publications: Publication[];
  posts: DashboardPost[];
}> {
  const publicationList = await api.listPublications({ owner: "me" });
  const postLists = await Promise.all(
    publicationList.items.map(async (publication) => {
      const list = await api.listPosts(publication.id);
      return list.items.map((post) => ({ ...post, publication }));
    }),
  );
  return { publications: publicationList.items, posts: postLists.flat() };
}

export default function Home() {
  const [status, setStatus] = useState<StatusFilter>("all");
  const [visibility, setVisibility] = useState<VisibilityFilter>("all");
  const [publications, setPublications] = useState<Publication[]>([]);
  const [posts, setPosts] = useState<DashboardPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyPostId, setBusyPostId] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      const data = await fetchDashboardData();
      setPublications(data.publications);
      setPosts(data.posts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchDashboardData()
      .then((data) => {
        if (cancelled) return;
        setPublications(data.publications);
        setPosts(data.posts);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load dashboard");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(
    () =>
      posts.filter(
        (post) =>
          (status === "all" || post.status === status) &&
          (visibility === "all" || post.visibility === visibility),
      ),
    [posts, status, visibility],
  );

  const categoryStats = useMemo(
    () => [
      {
        label: "All posts",
        count: posts.length,
        onClick: () => {
          setStatus("all");
          setVisibility("all");
        },
        active: status === "all" && visibility === "all",
      },
      {
        label: "Published",
        count: posts.filter((post) => post.status === "published").length,
        onClick: () => {
          setStatus("published");
          setVisibility("all");
        },
        active: status === "published" && visibility === "all",
      },
      {
        label: "Drafts",
        count: posts.filter((post) => post.status === "draft").length,
        onClick: () => {
          setStatus("draft");
          setVisibility("all");
        },
        active: status === "draft" && visibility === "all",
      },
      {
        label: "Archived",
        count: posts.filter((post) => post.status === "archived").length,
        onClick: () => {
          setStatus("archived");
          setVisibility("all");
        },
        active: status === "archived" && visibility === "all",
      },
      {
        label: "Free",
        count: posts.filter((post) => post.visibility === "free").length,
        onClick: () => {
          setStatus("all");
          setVisibility("free");
        },
        active: status === "all" && visibility === "free",
      },
      {
        label: "Paid",
        count: posts.filter((post) => post.visibility === "paid").length,
        onClick: () => {
          setStatus("all");
          setVisibility("paid");
        },
        active: status === "all" && visibility === "paid",
      },
    ],
    [posts, status, visibility],
  );

  const trendingPosts = useMemo(
    () =>
      posts
        .filter((post) => post.status === "published")
        .toSorted((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
        .slice(0, 4),
    [posts],
  );

  const publishPost = async (postId: string) => {
    setBusyPostId(postId);
    setError(null);
    try {
      await api.publishPost(postId);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish post");
    } finally {
      setBusyPostId(null);
    }
  };

  const archivePost = async (postId: string) => {
    setBusyPostId(postId);
    setError(null);
    try {
      await api.archivePost(postId);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to archive post");
    } finally {
      setBusyPostId(null);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white sm:text-3xl">Your Publications</h1>
          <p className="mt-2 text-sm text-slate-400">
            Draft, publish, and archive posts owned by the current account.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as StatusFilter);
              setVisibility("all");
            }}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet-500"
            aria-label="Filter posts by status"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value} className="bg-slate-900">
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-8 text-slate-300">
          Loading dashboard...
        </div>
      ) : publications.length === 0 ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-10 text-center">
          <BookOpen className="mx-auto mb-4 h-8 w-8 text-violet-300" />
          <h2 className="text-lg font-semibold text-white">No publications yet</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
            Use the header New Post button to create a publication and first draft.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          <section className="space-y-4 lg:col-span-2">
            {visible.map((post) => (
              <article
                key={post.id}
                className="rounded-lg border border-white/10 bg-slate-900/50 p-5 transition-colors hover:border-violet-500/40"
              >
                <div className="mb-3 flex flex-wrap items-center gap-3">
                  <span className={`rounded-full border px-3 py-1 text-xs ${statusClasses(post.status)}`}>
                    {statusLabel(post.status)}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                    {post.visibility}
                  </span>
                  <span className="text-xs text-slate-500">
                    {post.publication.name} · Updated {formatDate(post.updated_at)}
                  </span>
                </div>

                <h2 className="text-lg font-bold text-white">{post.title}</h2>
                <p className="mt-2 text-sm text-slate-400">/{post.slug}</p>

                <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-white/10 pt-4">
                  <Link
                    href={`/posts/${post.id}`}
                    className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white"
                  >
                    <Eye size={15} />
                    Read
                  </Link>
                  <Link
                    href={`/posts/${post.id}/edit`}
                    className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-violet-300 hover:bg-white/5 hover:text-violet-200"
                  >
                    <Pencil size={15} />
                    Edit
                  </Link>
                  {post.status === "draft" && (
                    <button
                      type="button"
                      onClick={() => void publishPost(post.id)}
                      disabled={busyPostId === post.id}
                      className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-emerald-300 hover:bg-white/5 hover:text-emerald-200 disabled:opacity-60"
                    >
                      <Send size={15} />
                      Publish
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void archivePost(post.id)}
                    disabled={busyPostId === post.id}
                    className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-slate-400 hover:bg-white/5 hover:text-white disabled:opacity-60"
                  >
                    <Archive size={15} />
                    Archive
                  </button>
                </div>
              </article>
            ))}

            {visible.length === 0 && (
              <div className="rounded-lg border border-white/10 bg-slate-900/50 p-10 text-center text-slate-400">
                No matching posts yet.
              </div>
            )}
          </section>

          <aside className="space-y-6">
            <div className="rounded-lg border border-white/10 bg-slate-900/50 p-5">
              <div className="mb-5 flex items-center gap-2">
                <Layers className="h-5 w-5 text-violet-300" />
                <h2 className="text-lg font-bold text-white">Categories</h2>
              </div>
              <ul className="space-y-1">
                {categoryStats.map((category) => (
                  <li key={category.label}>
                    <button
                      type="button"
                      onClick={category.onClick}
                      className={`flex w-full items-center justify-between rounded-md px-3 py-2.5 text-left text-sm transition-colors ${
                        category.active
                          ? "bg-violet-500/15 text-white"
                          : "text-slate-300 hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      <span>{category.label}</span>
                      <span className="text-xs text-slate-500">{category.count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg border border-white/10 bg-slate-900/50 p-5">
              <div className="mb-5 flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-cyan-300" />
                <h2 className="text-lg font-bold text-white">Trending Topics</h2>
              </div>
              {trendingPosts.length === 0 ? (
                <p className="text-sm text-slate-400">No published posts yet.</p>
              ) : (
                <ul className="space-y-3">
                  {trendingPosts.map((post, index) => (
                    <li key={post.id}>
                      <Link
                        href={`/posts/${post.id}`}
                        className="flex items-center gap-3 rounded-md p-2 text-slate-300 hover:bg-white/5 hover:text-white"
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-cyan-500/15 text-xs font-bold text-cyan-200">
                          {index + 1}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm">{post.title}</span>
                          <span className="block truncate text-xs text-slate-500">
                            {post.publication.name} · {formatDate(post.updated_at)}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border border-white/10 bg-slate-900/50 p-5">
              <div className="mb-3 flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-fuchsia-300" />
                <h2 className="text-lg font-bold text-white">Publications</h2>
              </div>
              <ul className="space-y-3">
                {publications.map((publication) => (
                  <li key={publication.id} className="rounded-md border border-white/10 p-3">
                    <div className="text-sm font-semibold text-white">{publication.name}</div>
                    <div className="mt-1 text-xs text-slate-500">@{publication.handle}</div>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
