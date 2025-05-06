/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'export',       // Enable static HTML export
    images: {
	unoptimized: true,  // Required for static export
    },
    // Enable CORS and proxy requests to Agentic backend
    async rewrites() {
	return [
	    {
		source: '/api/:path*',
		destination: 'http://localhost:8086/:path*',
	    },
	];
    },
    
    // Enable React strict mode for better development experience
    reactStrictMode: true,
}

module.exports = nextConfig;
