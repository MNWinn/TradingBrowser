import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: {
    unoptimized: true,
  },
  output: 'export',
  distDir: 'dist',
  basePath: process.env.NODE_ENV === 'production' ? '/TradingBrowser' : '',
  assetPrefix: process.env.NODE_ENV === 'production' ? '/TradingBrowser/' : '',
}

export default nextConfig
