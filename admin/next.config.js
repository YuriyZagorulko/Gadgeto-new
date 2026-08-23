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
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${API_URL}/api/v1/admin/:path*` },
      // Serve uploaded media through the backend static mount
      { source: '/media/:path*', destination: `${API_URL}/media/:path*` },
    ];
  },
};
module.exports = nextConfig;
