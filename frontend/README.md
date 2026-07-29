# Frontend

This document explains how to install, run, build, and configure the React SPA used to submit SEC filing URLs and inspect extraction results and confidence scores.

## Stack

- React
- Vite
- Plain CSS

## Setup

From the repository root:

```bash
cd frontend
npm install
```

## Run

Start the backend first:

```bash
cd backend
source .venv/bin/activate
python main.py
```

Then start the frontend in another terminal:

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

The Vite development server proxies `/api` to:

```text
http://127.0.0.1:8000
```

## Production Build

```bash
npm run build
```

The generated static application is written to `frontend/dist/`.

## API Configuration

For a backend hosted on another origin, create `frontend/.env.local`:

```text
VITE_API_BASE_URL=https://api.example.com
```

When this variable is empty, the SPA uses same-origin `/api` requests and the Vite development proxy.

## Features

- SEC filing URL input.
- Modern HTML and historical TXT examples.
- Loading and API error states.
- Filing-level confidence and selected extraction layer.
- Item navigation with individual scores.
- Heading, Body-versus-TOC, and section confidence details.
- Structured filing content and HTML table rendering.
- Responsive desktop and mobile layouts.
