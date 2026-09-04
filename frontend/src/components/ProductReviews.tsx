'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';

// Use relative /api prefix — goes through Next.js rewrite to backend
// (works in browser even when backend hostname is docker-internal)
const API_BASE = '/api';

type Review = {
  id: number;
  rating: number;
  text: string;
  author: { name: string };
  created_at: string;
};

type ReviewStats = {
  average_rating: number;
  total_reviews: number;
  rating_distribution: Record<number, number>;
};

type MyReview = {
  id: number;
  rating: number;
  text: string;
  status: string;
  created_at: string;
} | null;

function StarDisplay({ rating, size = 'md' }: { rating: number; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClass = size === 'lg' ? 'text-2xl' : size === 'sm' ? 'text-sm' : 'text-lg';
  return (
    <span className={`${sizeClass} text-amber-400`} aria-label={`${rating} з 5 зірок`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= rating ? 'text-amber-400' : 'text-gray-300'}>★</span>
      ))}
    </span>
  );
}

function StarRatingInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="Оцінка">
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          type="button"
          onClick={() => onChange(i)}
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(0)}
          className={`text-2xl transition ${(hover || value) >= i ? 'text-amber-400' : 'text-gray-300'} hover:text-amber-400`}
          aria-label={`${i} з 5 зірок`}
          aria-pressed={value === i}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function RatingBar({ stars, count, total }: { stars: number; count: number; total: number }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-8 text-gray-600">{stars}★</span>
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-amber-400 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-gray-500 text-right">{count}</span>
    </div>
  );
}

export default function ProductReviews({ productId }: { productId: number }) {
  const t = useTranslations('reviews');
  const [reviews, setReviews] = useState<Review[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [myReview, setMyReview] = useState<MyReview>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [user, setUser] = useState<any>(null);

  // Form state
  const [rating, setRating] = useState(0);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  // Check auth
  const fetchUser = useCallback(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setUser(null);
      return null;
    }
    return fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) {
          localStorage.removeItem('auth_token');
          setUser(null);
          return null;
        }
        return r.json();
      })
      .then((d) => {
        if (d) setUser(d);
        return d;
      })
      .catch(() => null);
  }, []);

  const fetchReviews = useCallback(async () => {
    try {
      const [reviewsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/products/${productId}/reviews?page=1&page_size=10`),
        fetch(`${API_BASE}/products/${productId}/reviews/stats`),
      ]);
      if (reviewsRes.ok) {
        const data = await reviewsRes.json();
        setReviews(data.items || []);
      }
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch {
      setError('Не вдалося завантажити відгуки');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  const fetchMyReview = useCallback(async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/products/${productId}/reviews/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setMyReview(await res.json());
      }
    } catch {
      // ignore
    }
  }, [productId]);

  useEffect(() => {
    setLoading(true);
    Promise.resolve(fetchUser()).then(() => {
      fetchReviews();
      fetchMyReview();
    });
  }, [fetchUser, fetchReviews, fetchMyReview]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');

    if (rating === 0) {
      setFormError('Оберіть оцінку');
      return;
    }
    if (!text.trim()) {
      setFormError('Напишіть текст відгуку');
      return;
    }

    const token = localStorage.getItem('auth_token');
    if (!token) {
      setFormError('Необхідна автентифікація');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/products/${productId}/reviews`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ rating, text: text.trim() }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(data?.detail || 'Помилка при надсиланні відгуку');
      }

      setFormSuccess('Ваш відгук надіслано на модерацію.');
      setText('');
      setRating(0);
      // Refresh my review status
      fetchMyReview();
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('uk-UA', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const getStatusMessage = () => {
    if (!myReview) return null;
    switch (myReview.status) {
      case 'PENDING':
        return { text: 'Ваш відгук очікує модерації.', tone: 'yellow' as const };
      case 'APPROVED':
        return { text: 'Ваш відгук уже опублікований.', tone: 'green' as const };
      case 'REJECTED':
        return { text: 'Ваш відгук було відхилено модератором.', tone: 'red' as const };
      default:
        return null;
    }
  };

  const statusMessage = getStatusMessage();

  return (
    <section className="mt-8 border-t pt-6" aria-labelledby="reviews-heading">
      <h2 id="reviews-heading" className="text-xl font-bold mb-4">Відгуки</h2>

      {/* Rating Summary */}
      {stats && stats.total_reviews > 0 && (
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <div className="flex flex-col sm:flex-row gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-gray-900">{stats.average_rating}</div>
              <StarDisplay rating={Math.round(stats.average_rating)} />
              <div className="text-sm text-gray-500 mt-1">{stats.total_reviews} відгуків</div>
            </div>
            <div className="flex-1 space-y-1">
              {[5, 4, 3, 2, 1].map((stars) => (
                <RatingBar
                  key={stars}
                  stars={stars}
                  count={stats.rating_distribution[stars] || 0}
                  total={stats.total_reviews}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* My Review Status */}
      {statusMessage && (
        <div className={`rounded-lg p-3 mb-4 text-sm ${
          statusMessage.tone === 'yellow' ? 'bg-yellow-50 text-yellow-800' :
          statusMessage.tone === 'green' ? 'bg-green-50 text-green-800' :
          'bg-red-50 text-red-800'
        }`}>
          {statusMessage.text}
        </div>
      )}

      {/* Review Form or Auth Prompt */}
      {!myReview && (
        <div className="mb-6">
          {user ? (
            <form onSubmit={handleSubmit} className="bg-white border rounded-lg p-4 space-y-4">
              <h3 className="font-semibold">Залишити відгук</h3>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Ваша оцінка</label>
                <StarRatingInput value={rating} onChange={setRating} />
              </div>

              <div>
                <label htmlFor="review-text" className="block text-sm text-gray-600 mb-1">Ваш відгук</label>
                <textarea
                  id="review-text"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={4}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Розкажіть про свій досвід використання товару..."
                  maxLength={5000}
                />
              </div>

              {formError && <p className="text-sm text-red-600">{formError}</p>}
              {formSuccess && <p className="text-sm text-green-600">{formSuccess}</p>}

              <button
                type="submit"
                disabled={submitting}
                className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Надсилання...' : 'Надіслати відгук'}
              </button>
            </form>
          ) : (
            <div className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-sm text-gray-600 mb-2">Щоб залишити відгук, увійдіть у свій акаунт.</p>
              <Link
                href="/login"
                className="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
              >
                Увійти
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Reviews List */}
      {loading ? (
        <div className="text-center py-8 text-gray-500">Завантаження відгуків...</div>
      ) : error ? (
        <div className="text-center py-8 text-red-500">{error}</div>
      ) : reviews.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500">Поки що немає відгуків.</p>
          <p className="text-gray-400 text-sm">Будьте першим, хто залишить відгук!</p>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((review) => (
            <div key={review.id} className="border-b pb-4 last:border-0">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <StarDisplay rating={review.rating} size="sm" />
                  <span className="font-medium text-sm">{review.author.name}</span>
                </div>
                <span className="text-xs text-gray-400">{formatDate(review.created_at)}</span>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{review.text}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
