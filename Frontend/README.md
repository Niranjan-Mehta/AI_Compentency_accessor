# Frontend

React application built with Vite. Run commands from the `Frontend/` directory.

## Prerequisites

- Node.js compatible with Vite 8 (use a current Node.js LTS release).
- npm (the repository includes `package-lock.json`).
- The Django backend running locally or reachable at the configured API URL.

## Install dependencies

```powershell
npm ci
```

## Environment configuration

Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` to the backend API root, including `/api` (for example, `http://127.0.0.1:8000/api`). If unset, the API client uses that same local default. Vite exposes variables prefixed with `VITE_` to browser code, so never place secrets or provider keys in this file.

## Development server

```powershell
npm run dev
```

The package script starts Vite on port `3000` and binds to `0.0.0.0`. Open the address printed by Vite. The backend's default CORS origins include local ports 3000 and 5173.

## Production build

```powershell
npm run build
```

Vite writes production output to `dist/`. To locally preview that build:

```powershell
npm run preview
```

## TypeScript check

```powershell
npm run lint
```

Despite the script name, this command runs `tsc --noEmit`; it is a TypeScript check and does not run an ESLint rule set. The project contains JSX and allows JavaScript in TypeScript configuration.

## Backend API connection

`src/services/api.js` reads `VITE_API_BASE_URL` and defaults to `http://127.0.0.1:8000/api`. Ensure Django is running and that its `CORS_ALLOWED_ORIGINS` includes the frontend origin. For deployment, set an HTTPS API URL and configure backend CORS and allowed hosts for the deployed domains.
