"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Archive, ArrowLeft, Eye, Save, Send } from "lucide-react";

import { useAuth } from "../../../components/AuthProvider";
import { api, type PostRead, type PostVisibility } from "../../../lib/api";

export default function EditPost() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [post, setPost] = useState<PostRead | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<PostVisibility>("free");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const postId = params.id;

  const loadPost = useCallback(async () => {
    try {
      const nextPost = await api.getPost(postId);
      setPost(nextPost);
      setTitle(nextPost.title);
      setBody(nextPost.body ?? "");
      setVisibility(nextPost.visibility);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load post");
    } finally {
      setLoading(false);
    }
  }, [postId]);

  useEffect(() => {
    let cancelled = false;
    api
      .getPost(postId)
      .then((nextPost) => {
        if (cancelled) return;
        setPost(nextPost);
        setTitle(nextPost.title);
        setBody(nextPost.body ?? "");
        setVisibility(nextPost.visibility);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load post");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [postId]);

  const isOwner = Boolean(user && post && user.id === post.author_user_id);

  const savePost = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      const updated = await api.updatePost(postId, { title, body, visibility });
      setPost((current) => (current ? { ...current, ...updated, body } : current));
      setNotice("Post saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save post");
    } finally {
      setBusy(false);
    }
  };

  const publishPost = async () => {
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      await api.publishPost(postId);
      await loadPost();
      setNotice("Post published.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish post");
    } finally {
      setBusy(false);
    }
  };

  const archivePost = async () => {
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      await api.archivePost(postId);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to archive post");
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      <Link href="/home" className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
        <ArrowLeft size={16} />
        Dashboard
      </Link>

      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Edit Post</h1>
          <p className="mt-2 text-sm text-slate-400">Changes are plain CRUD until publish.</p>
        </div>
        {post && (
          <Link
            href={`/posts/${post.id}`}
            className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/15"
          >
            <Eye size={16} />
            Preview
          </Link>
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-6 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {notice}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-8 text-slate-300">
          Loading editor...
        </div>
      ) : !post ? null : !isOwner ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-8 text-slate-300">
          This post belongs to another user.
        </div>
      ) : (
        <form onSubmit={savePost} className="space-y-5 rounded-lg border border-white/10 bg-slate-900/50 p-5">
          <div>
            <label htmlFor="title" className="mb-2 block text-sm text-slate-300">
              Title
            </label>
            <input
              id="title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>

          <div>
            <label htmlFor="visibility" className="mb-2 block text-sm text-slate-300">
              Visibility
            </label>
            <select
              id="visibility"
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as PostVisibility)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="free" className="bg-slate-900">
                Free
              </option>
              <option value="paid" className="bg-slate-900">
                Paid
              </option>
            </select>
          </div>

          <div>
            <label htmlFor="body" className="mb-2 block text-sm text-slate-300">
              Body
            </label>
            <textarea
              id="body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              required
              className="min-h-96 w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm leading-6 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>

          <div className="flex flex-wrap gap-2 border-t border-white/10 pt-5">
            <button
              type="submit"
              disabled={busy || !title.trim() || !body.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-3 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-60"
            >
              <Save size={16} />
              {busy ? "Saving..." : "Save"}
            </button>
            {post.status === "draft" && (
              <button
                type="button"
                onClick={() => void publishPost()}
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
              >
                <Send size={16} />
                Publish
              </button>
            )}
            <button
              type="button"
              onClick={() => void archivePost()}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-4 py-3 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-60"
            >
              <Archive size={16} />
              Archive
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
