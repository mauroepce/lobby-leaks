/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The Cosmograph webgl package ships with a couple of CommonJS modules
  // that Next 14 doesn't tree-shake well; transpiling them explicitly
  // avoids a "process is not defined" runtime error in dev.
  transpilePackages: ["@cosmograph/cosmograph", "@cosmograph/react"],
};

export default nextConfig;
