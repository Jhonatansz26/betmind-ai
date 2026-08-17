/** @type {import('next').NextConfig} */
const nextConfig = {
  // Acceso en dev desde otros dispositivos de la LAN (p. ej. 192.168.18.156).
  allowedDevOrigins: ['192.168.18.156'],
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
  },
}

export default nextConfig
