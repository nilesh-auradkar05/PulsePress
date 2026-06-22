"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, ArrowLeft, CreditCard, Gift, Lock, Pencil, Send } from "lucide-react";

import { useAuth } from "../../components/AuthProvider";
import { api, type Plan, type PostRead } from "../../lib/api";
import { formatDate, statusLabel } from "../../lib/content";

export default function PostDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [post, setPost] = useState<PostRead | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [giftAmount, setGiftAmount] = useState("500");
  const [giftMessage, setGiftMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [commerceNotice, setCommerceNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const postId = params.id;

  const loadPost = useCallback(async () => {
    try {
      setPost(await api.getPost(postId));
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
        if (!cancelled) setPost(nextPost);
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
  const paidPlans = useMemo(
    () => plans.filter((plan) => plan.monthly_price_cents > 0),
    [plans],
  );

  useEffect(() => {
    if (!post || isOwner) {
      return;
    }

    let cancelled = false;
    api
      .listPlans(post.publication_id)
      .then((items) => {
        if (!cancelled) setPlans(items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load subscription plans");
      });

    return () => {
      cancelled = true;
    };
  }, [isOwner, post]);

  const publishPost = async () => {
    if (!post) return;
    setBusy(true);
    setError(null);
    try {
      await api.publishPost(post.id);
      await loadPost();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish post");
    } finally {
      setBusy(false);
    }
  };

  const archivePost = async () => {
    if (!post) return;
    setBusy(true);
    setError(null);
    try {
      await api.archivePost(post.id);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to archive post");
      setBusy(false);
    }
  };

  const subscribeToPlan = async (plan: Plan) => {
    if (!post) return;
    setBusy(true);
    setError(null);
    setCommerceNotice(null);
    try {
      await api.createSubscription({
        publication_id: post.publication_id,
        plan_id: plan.id,
        amount_cents: plan.monthly_price_cents,
      });
      await loadPost();
      setCommerceNotice(`Subscribed to ${plan.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to subscribe");
    } finally {
      setBusy(false);
    }
  };

  const sendGift = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!post) return;
    setBusy(true);
    setError(null);
    setCommerceNotice(null);
    try {
      const amount = Number.parseInt(giftAmount, 10);
      const result = await api.sendGift({
        publication_id: post.publication_id,
        amount_cents: Number.isFinite(amount) ? amount : 0,
        message: giftMessage.trim() || null,
      });
      setCommerceNotice(
        `Gift queued. Total charged $${(result.bill.total_charged_cents / 100).toFixed(2)}.`,
      );
      setGiftAmount("500");
      setGiftMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send gift");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <Link href="/home" className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
        <ArrowLeft size={16} />
        Dashboard
      </Link>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {commerceNotice && (
        <div className="mb-6 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {commerceNotice}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border border-white/10 bg-slate-900/50 p-8 text-slate-300">
          Loading post...
        </div>
      ) : post ? (
        <article className="rounded-lg border border-white/10 bg-slate-900/50 p-6 sm:p-8">
          <div className="mb-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
              {statusLabel(post.status)}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
              {post.visibility}
            </span>
            <span>Updated {formatDate(post.updated_at)}</span>
          </div>

          <h1 className="text-3xl font-bold text-white sm:text-4xl">{post.title}</h1>
          {post.published_at && (
            <p className="mt-3 text-sm text-slate-500">Published {formatDate(post.published_at)}</p>
          )}

          {isOwner && (
            <div className="mt-6 flex flex-wrap gap-2 border-y border-white/10 py-4">
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
                  onClick={() => void publishPost()}
                  disabled={busy}
                  className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-emerald-300 hover:bg-white/5 hover:text-emerald-200 disabled:opacity-60"
                >
                  <Send size={15} />
                  Publish
                </button>
              )}
              <button
                type="button"
                onClick={() => void archivePost()}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white disabled:opacity-60"
              >
                <Archive size={15} />
                Archive
              </button>
            </div>
          )}

          {post.entitled ? (
            <div className="prose prose-invert mt-8 max-w-none whitespace-pre-wrap text-slate-200">
              {post.body}
            </div>
          ) : (
            <div className="mt-8 rounded-lg border border-amber-500/20 bg-amber-500/10 p-5 text-amber-100">
              <div className="mb-2 flex items-center gap-2 font-semibold">
                <Lock size={16} />
                Paid post
              </div>
              <p className="text-sm text-amber-100/80">
                Subscribe to a paid plan to unlock the full body.
              </p>
            </div>
          )}

          {!isOwner && (
            <div className="mt-8 grid gap-4 border-t border-white/10 pt-6 md:grid-cols-2">
              <section className="rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="mb-3 flex items-center gap-2 font-semibold text-white">
                  <CreditCard size={16} />
                  Subscribe
                </div>
                {paidPlans.length === 0 ? (
                  <p className="text-sm text-slate-400">No paid plans are available for this publication.</p>
                ) : (
                  <div className="space-y-2">
                    {paidPlans.map((plan) => (
                      <button
                        key={plan.id}
                        type="button"
                        onClick={() => void subscribeToPlan(plan)}
                        disabled={busy}
                        className="flex w-full items-center justify-between rounded-md border border-white/10 bg-slate-950/40 px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/10 disabled:opacity-60"
                      >
                        <span>{plan.name}</span>
                        <span>${(plan.monthly_price_cents / 100).toFixed(2)}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <form onSubmit={sendGift} className="rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="mb-3 flex items-center gap-2 font-semibold text-white">
                  <Gift size={16} />
                  Send gift
                </div>
                <div className="space-y-3">
                  <input
                    type="number"
                    min="50"
                    step="1"
                    value={giftAmount}
                    onChange={(event) => setGiftAmount(event.target.value)}
                    className="w-full rounded-md border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    aria-label="Gift amount cents"
                  />
                  <textarea
                    value={giftMessage}
                    onChange={(event) => setGiftMessage(event.target.value)}
                    maxLength={280}
                    className="min-h-20 w-full rounded-md border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="Optional message"
                  />
                  <button
                    type="submit"
                    disabled={
                      busy ||
                      !giftAmount.trim() ||
                      Number.isNaN(Number.parseInt(giftAmount, 10)) ||
                      Number.parseInt(giftAmount, 10) < 50
                    }
                    className="inline-flex items-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-60"
                  >
                    <Gift size={15} />
                    {busy ? "Sending..." : "Send gift"}
                  </button>
                </div>
              </form>
            </div>
          )}
        </article>
      ) : null}
    </div>
  );
}
