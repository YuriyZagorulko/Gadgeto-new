/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Public storefront origin — product "View" links open here (admin is on a
// different host/port in dev and production). Defaults to localhost:3000.
const STORE_URL = process.env.NEXT_PUBLIC_STORE_URL || 'http://localhost:3000';
if (process.env.NODE_ENV !== 'production') {
  process.env.NEXT_PUBLIC_STORE_URL = STORE_URL;
}

const nextConfig = {
  output: 'standalone',
  // Allow overriding the build dir (e.g. when .next is owned by the Docker dev container).
  distDir: process.env.NEXT_DIST_DIR || '.next',
  async redirects() {
    return [
      // Suppliers/mappings moved under the "Імпорт" section (admin sidebar).
      { source: '/mappings', destination: '/imports/mappings', permanent: false },
      { source: '/suppliers', destination: '/imports/suppliers', permanent: false },
      // Legacy import routes consolidated into /imports/history and /imports/settings
      { source: '/imports', destination: '/imports/history', permanent: false },
      { source: '/imports/global', destination: '/imports/settings?tab=global', permanent: false },
      { source: '/settings/global-actions', destination: '/imports/settings?tab=global', permanent: false },
    ];
  },
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${API_URL}/api/v1/admin/:path*` },
      // Serve uploaded media through the backend static mount
      { source: '/media/:path*', destination: `${API_URL}/media/:path*` },
    ];
  },
};
module.exports = nextConfig;
