"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, BookOpen, Plus, Save } from "lucide-react";
import Link from "next/link";

import { api, type Plan, type PostVisibility, type Publication } from "../../lib/api";

export default function NewPost() {
  const router = useRouter();
  const [publications, setPublications] = useState<Publication[]>([]);
  const [publicationId, setPublicationId] = useState("");
  const [publicationName, setPublicationName] = useState("");
  const [publicationHandle, setPublicationHandle] = useState("");
  const [publicationDescription, setPublicationDescription] = useState("");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [planName, setPlanName] = useState("");
  const [planPrice, setPlanPrice] = useState("500");
  const [planOpenAmount, setPlanOpenAmount] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<PostVisibility>("free");
  const [loading, setLoading] = useState(true);
  const [submittingPublication, setSubmittingPublication] = useState(false);
  const [submittingPlan, setSubmittingPlan] = useState(false);
  const [submittingPost, setSubmittingPost] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listPublications({ owner: "me" })
      .then((list) => {
        if (cancelled) return;
        setPublications(list.items);
        setPublicationId(list.items[0]?.id ?? "");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load publications");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!publicationId) {
      return;
    }

    let cancelled = false;
    api
      .listPlans(publicationId)
      .then((items) => {
        if (!cancelled) setPlans(items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load plans");
      });

    return () => {
      cancelled = true;
    };
  }, [publicationId]);

  const createPublication = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmittingPublication(true);
    try {
      const publication = await api.createPublication({
        name: publicationName,
        handle: publicationHandle,
        description: publicationDescription || null,
      });
      setPublications((current) => [publication, ...current]);
      setPublicationId(publication.id);
      setPublicationName("");
      setPublicationHandle("");
      setPublicationDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create publication");
    } finally {
      setSubmittingPublication(false);
    }
  };

  const createPlan = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmittingPlan(true);
    try {
      const price = Number.parseInt(planPrice, 10);
      const plan = await api.createPlan(publicationId, {
        name: planName,
        monthly_price_cents: Number.isFinite(price) ? price : 0,
        allow_open_amount: planOpenAmount,
      });
      setPlans((current) => [...current, plan].sort((a, b) => a.monthly_price_cents - b.monthly_price_cents));
      setPlanName("");
      setPlanPrice("500");
      setPlanOpenAmount(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create plan");
    } finally {
      setSubmittingPlan(false);
    }
  };

  const createPost = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmittingPost(true);
    try {
      const post = await api.createPost(publicationId, { title, body, visibility });
      router.replace(`/posts/${post.id}/edit`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create post");
    } finally {
      setSubmittingPost(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <Link href="/home" className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
        <ArrowLeft size={16} />
        Dashboard
      </Link>

      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">New Post</h1>
        <p className="mt-2 text-sm text-slate-400">
          Create a publication if needed, then save a draft post.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-6">
          <form onSubmit={createPublication} className="rounded-lg border border-white/10 bg-slate-900/50 p-5">
            <div className="mb-4 flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-violet-300" />
              <h2 className="text-lg font-semibold text-white">Publication</h2>
            </div>
            <div className="space-y-4">
              <div>
                <label htmlFor="publicationName" className="mb-2 block text-sm text-slate-300">
                  Name
                </label>
                <input
                  id="publicationName"
                  value={publicationName}
                  onChange={(event) => setPublicationName(event.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Engineering Notes"
                />
              </div>
              <div>
                <label htmlFor="publicationHandle" className="mb-2 block text-sm text-slate-300">
                  Handle
                </label>
                <input
                  id="publicationHandle"
                  value={publicationHandle}
                  onChange={(event) => setPublicationHandle(event.target.value.toLowerCase())}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="engineering-notes"
                  pattern="[a-z0-9-]{3,32}"
                />
              </div>
              <div>
                <label htmlFor="publicationDescription" className="mb-2 block text-sm text-slate-300">
                  Description
                </label>
                <textarea
                  id="publicationDescription"
                  value={publicationDescription}
                  onChange={(event) => setPublicationDescription(event.target.value)}
                  className="min-h-24 w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Short publication summary"
                />
              </div>
              <button
                type="submit"
                disabled={submittingPublication || !publicationName.trim() || !publicationHandle.trim()}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-white/10 px-4 py-3 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-60"
              >
                <Plus size={16} />
                {submittingPublication ? "Creating..." : "Create publication"}
              </button>
            </div>
          </form>

          <form onSubmit={createPlan} className="rounded-lg border border-white/10 bg-slate-900/50 p-5">
            <h2 className="mb-4 text-lg font-semibold text-white">Subscription plan</h2>
            <div className="mb-4 space-y-2">
              {plans.length === 0 ? (
                <p className="text-sm text-slate-400">No plans for the selected publication.</p>
              ) : (
                plans.map((plan) => (
                  <div key={plan.id} className="rounded-md border border-white/10 px-3 py-2">
                    <div className="text-sm font-medium text-white">{plan.name}</div>
                    <div className="text-xs text-slate-500">
                      ${(plan.monthly_price_cents / 100).toFixed(2)} / month
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="space-y-4">
              <div>
                <label htmlFor="planName" className="mb-2 block text-sm text-slate-300">
                  Name
                </label>
                <input
                  id="planName"
                  value={planName}
                  onChange={(event) => setPlanName(event.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Supporter"
                />
              </div>
              <div>
                <label htmlFor="planPrice" className="mb-2 block text-sm text-slate-300">
                  Monthly price cents
                </label>
                <input
                  id="planPrice"
                  type="number"
                  min="0"
                  step="1"
                  value={planPrice}
                  onChange={(event) => setPlanPrice(event.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={planOpenAmount}
                  onChange={(event) => setPlanOpenAmount(event.target.checked)}
                  className="h-4 w-4 rounded border-white/20 bg-white/5"
                />
                Allow readers to pay above the floor
              </label>
              <button
                type="submit"
                disabled={
                  submittingPlan ||
                  !publicationId ||
                  !planName.trim() ||
                  !planPrice.trim() ||
                  Number.isNaN(Number.parseInt(planPrice, 10)) ||
                  Number.parseInt(planPrice, 10) < 0
                }
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-white/10 px-4 py-3 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-60"
              >
                <Plus size={16} />
                {submittingPlan ? "Creating..." : "Create plan"}
              </button>
            </div>
          </form>
        </div>

        <form onSubmit={createPost} className="rounded-lg border border-white/10 bg-slate-900/50 p-5">
          <h2 className="mb-5 text-lg font-semibold text-white">Draft</h2>
          {loading ? (
            <div className="text-sm text-slate-400">Loading publications...</div>
          ) : (
            <div className="space-y-5">
              <div>
                <label htmlFor="publication" className="mb-2 block text-sm text-slate-300">
                  Publish under
                </label>
                <select
                  id="publication"
                  value={publicationId}
                  onChange={(event) => {
                    const nextPublicationId = event.target.value;
                    setPublicationId(nextPublicationId);
                    if (!nextPublicationId) setPlans([]);
                  }}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  {publications.length === 0 && <option value="">Create a publication first</option>}
                  {publications.map((publication) => (
                    <option key={publication.id} value={publication.id} className="bg-slate-900">
                      {publication.name}
                    </option>
                  ))}
                </select>
              </div>
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
                  placeholder="A clear post title"
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
                  className="min-h-80 w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm leading-6 text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Write the draft body..."
                />
              </div>
              <button
                type="submit"
                disabled={submittingPost || !publicationId || !title.trim() || !body.trim()}
                className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-3 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-60"
              >
                <Save size={16} />
                {submittingPost ? "Saving..." : "Save draft"}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
