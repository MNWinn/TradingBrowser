# GitHub Pages Deployment

This document describes how to deploy the TradingBrowser frontend to GitHub Pages.

## Overview

The frontend is automatically deployed to GitHub Pages whenever changes are pushed to the `main` branch.

## Setup Instructions

### 1. Enable GitHub Pages

1. Go to your repository on GitHub: `https://github.com/MNWinn/TradingBrowser`
2. Navigate to **Settings** → **Pages**
3. Under **Build and deployment**:
   - Source: Select **GitHub Actions**

### 2. Configure Repository Permissions

Ensure the workflow has the necessary permissions (already configured in `.github/workflows/deploy.yml`):

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

### 3. Deployment URL

Once deployed, your site will be available at:

```
https://mnwinn.github.io/TradingBrowser/
```

## Manual Deployment

You can also trigger a manual deployment:

1. Go to **Actions** tab in your repository
2. Select **Deploy to GitHub Pages** workflow
3. Click **Run workflow**

## Local Build Testing

To test the production build locally:

```bash
cd frontend
npm install
npm run build
```

The static files will be generated in `frontend/dist/`.

To preview the production build:

```bash
cd frontend
npx serve dist
```

## Configuration Details

### next.config.ts

The Next.js configuration includes:

- `output: 'export'` - Enables static HTML export
- `distDir: 'dist'` - Output directory for static files
- `basePath: '/TradingBrowser'` - Base path for GitHub Pages (repository name)
- `assetPrefix: '/TradingBrowser/'` - Prefix for static assets
- `images.unoptimized: true` - Required for static export

### GitHub Actions Workflow

The workflow (`.github/workflows/deploy.yml`):

1. Triggers on push to `main` or manual dispatch
2. Sets up Node.js 20
3. Installs dependencies from `frontend/package-lock.json`
4. Builds the Next.js app with static export
5. Uploads the `dist` folder as a Pages artifact
6. Deploys to GitHub Pages

## Troubleshooting

### Build Failures

Check the Actions tab for build logs. Common issues:

- Missing dependencies: Ensure `package-lock.json` is committed
- TypeScript errors: Run `npm run build` locally to catch errors early

### 404 Errors on Assets

If assets are not loading (CSS, JS files):

- Verify `basePath` and `assetPrefix` in `next.config.ts` match your repository name
- Ensure the repository name in the URL matches exactly (case-sensitive)

### Custom Domain (Optional)

To use a custom domain instead of `github.io`:

1. Add a `CNAME` file to the `frontend/public/` directory with your domain
2. Update DNS records to point to GitHub Pages
3. Remove or modify the `basePath` and `assetPrefix` settings in `next.config.ts`

## Notes

- The backend API is not deployed to GitHub Pages (static hosting only)
- For full functionality including backend features, deploy the backend separately
- Consider using services like Vercel, Railway, or Render for the backend deployment
