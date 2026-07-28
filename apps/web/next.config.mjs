/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
    remotePatterns: [
      { protocol: 'https', hostname: 'a.espncdn.com' },
      { protocol: 'https', hostname: 'a1.espncdn.com' },
      { protocol: 'https', hostname: 'a2.espncdn.com' },
      { protocol: 'https', hostname: 'a3.espncdn.com' },
      { protocol: 'https', hostname: 'a4.espncdn.com' },
      { protocol: 'https', hostname: 'upload.wikimedia.org' },
    ],
    domains: [
      'a.espncdn.com',
      'a1.espncdn.com',
      'a2.espncdn.com',
      'a3.espncdn.com',
      'a4.espncdn.com',
      'upload.wikimedia.org',
    ],
  },
}

export default nextConfig
