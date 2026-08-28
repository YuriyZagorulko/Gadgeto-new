import { Link } from '@/i18n/navigation';

/**
 * Server-rendered pagination for catalog/search listings.
 * Builds hrefs from the current single-value params, replacing only `page`,
 * so every active filter survives navigation.
 */
export default function CatalogPagination({
  basePath,
  params,
  page,
  totalPages,
}: {
  basePath: string;
  params: Record<string, string>;
  page: number;
  totalPages: number;
}) {
  if (totalPages <= 1) return null;

  const href = (p: number) => {
    const sp = new URLSearchParams(params);
    if (p > 1) sp.set('page', String(p));
    else sp.delete('page');
    const qs = sp.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };

  // Window of page numbers around the current page (max 5, plus edges).
  const window_: number[] = [];
  const lo = Math.max(2, page - 2);
  const hi = Math.min(totalPages - 1, page + 2);
  for (let p = lo; p <= hi; p++) window_.push(p);

  const cls = (active: boolean) =>
    'min-w-9 px-3 py-1.5 text-center text-sm rounded-md border ' +
    (active
      ? 'border-blue-600 bg-blue-600 text-white'
      : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50');

  return (
    <nav className="mt-6 flex flex-wrap items-center justify-center gap-1.5">
      {page > 1 && (
        <Link href={href(page - 1)} className={cls(false)} scroll={false}>
          ←
        </Link>
      )}
      <Link href={href(1)} className={cls(page === 1)} scroll={false}>
        1
      </Link>
      {lo > 2 && <span className="px-1 text-gray-400">…</span>}
      {window_.map((p) => (
        <Link key={p} href={href(p)} className={cls(p === page)} scroll={false}>
          {p}
        </Link>
      ))}
      {hi < totalPages - 1 && <span className="px-1 text-gray-400">…</span>}
      {totalPages > 1 && (
        <Link href={href(totalPages)} className={cls(page === totalPages)} scroll={false}>
          {totalPages}
        </Link>
      )}
      {page < totalPages && (
        <Link href={href(page + 1)} className={cls(false)} scroll={false}>
          →
        </Link>
      )}
    </nav>
  );
}
