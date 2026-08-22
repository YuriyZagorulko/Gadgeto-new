/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/v1/admin/:path*' },
    ];
  },
};
module.exports = nextConfig;
