# TTC Chatbot — Frontend Developer Guide

React + Vite single-page application that provides the user interface for the TTC Chatbot. In production it is served directly by the FastAPI backend. During local development it runs on its own dev server with a proxy to the backend.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Getting Started](#getting-started)
3. [Environment Variables](#environment-variables)
4. [Folder Structure](#folder-structure)
5. [Key Pages](#key-pages)
6. [Shared Components](#shared-components)
7. [API Layer](#api-layer)
8. [Auth Context](#auth-context)
9. [Routing](#routing)
10. [Branding & Colors — How to Change Them](#branding--colors--how-to-change-them)
11. [CSS Modules Convention](#css-modules-convention)
12. [Building & Serving from the Backend](#building--serving-from-the-backend)
13. [Linting](#linting)
14. [Error Handling Patterns](#error-handling-patterns)

---

## Tech Stack

| Library / Tool | Version | Purpose |
|---|---|---|
| React | 19.2.5 | UI framework |
| Vite | 8.0.10 | Build tool & dev server |
| React Router DOM | 7.14.2 | Client-side routing |
| Axios | 1.15.2 | HTTP client |
| CSS Modules | (built-in) | Scoped per-component styles |

---

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- The FastAPI backend running on `http://localhost:8000`

### Install dependencies
```bash
cd frontend
npm install
```

### Start the dev server
```bash
npm run dev
# → http://localhost:5173
```
The dev server proxies `/api`, `/chat`, and `/health` requests to the backend at `http://localhost:8000` — no CORS configuration needed during development.

### Build for production
```bash
npm run build
# Output: frontend/dist/
```
The backend serves the built output automatically (see [Building & Serving from the Backend](#building--serving-from-the-backend)).

### Other scripts
| Command | What it does |
|---|---|
| `npm run dev` | Start Vite dev server on port 5173 |
| `npm run build` | Compile & bundle into `dist/` |
| `npm run preview` | Preview the production build locally |
| `npm run lint` | Run ESLint |

---

## Environment Variables

Create or edit `frontend/.env`:

```
# Backend API base URL — used by the Axios client
VITE_API_URL=http://localhost:8000
```

- In development this defaults to `http://localhost:8000` and the Vite proxy handles requests, so changing this is usually not needed.
- In production, set `VITE_API_URL` to the deployed backend URL before running `npm run build`.

The Vite dev-server proxy is configured in `vite.config.js`:

```js
proxy: {
  "/api":    { target: "http://localhost:8000", changeOrigin: true },
  "/chat":   { target: "http://localhost:8000", changeOrigin: true },
  "/health": { target: "http://localhost:8000", changeOrigin: true },
}
```

---

## Folder Structure

```
frontend/
├── .env                  # Local environment variables (not committed)
├── vite.config.js        # Vite config + dev-server proxy
├── index.html            # HTML entry point
├── public/               # Static assets copied verbatim to dist/
└── src/
    ├── main.jsx          # React entry — renders <App /> into #root
    ├── App.jsx           # Route definitions and AuthProvider wrapper
    ├── index.css         # Global reset / base styles
    ├── api/
    │   ├── client.js     # Axios instance, JWT interceptor, 401 handler
    │   ├── auth.js       # Auth API calls (login, register, me, update…)
    │   └── chat.js       # Chat & session API calls
    ├── context/
    │   └── AuthContext.jsx  # Global auth state (user, token, login, logout)
    ├── pages/
    │   ├── LoginPage.jsx        # Login form with field-level errors
    │   ├── RegisterPage.jsx     # Registration form
    │   ├── ChatPage.jsx         # Main chat UI with sidebar session list
    │   ├── ProfilePage.jsx      # User profile viewer / editor
    │   ├── Auth.module.css      # Shared styles for Login + Register
    │   ├── ChatPage.module.css  # Styles for the chat layout
    │   └── Profile.module.css   # Styles for the profile page
    └── components/
        ├── MessageBubble.jsx        # Renders a single chat message
        ├── MessageBubble.module.css
        ├── FeedbackBar.jsx          # Star-rating feedback widget per session
        └── FeedbackBar.module.css
```

---

## Key Pages

### `LoginPage.jsx`
- Username + password form.
- Calls `authApi.login()`, stores JWT in `localStorage` under `ttc_token`.
- Error routing:
  - Unknown username → error shown on the **username field**
  - Wrong password → error shown on the **password field**
  - Inactive account → error shown in a **form-level error box** above the fields
- Helper function `buildLoginErrors(detail)` maps backend `detail` array → React state.

### `RegisterPage.jsx`
- Full name, email, username, password, confirm-password fields.
- Duplicate username / email conflicts are shown on the relevant field.

### `ChatPage.jsx`
- Two-column layout: **sidebar** (session list) + **main chat area**.
- On mobile (≤ 768 px) the sidebar is hidden behind a hamburger button (`☰`). Tapping it slides the sidebar in; a close button (`✕`) or backdrop tap closes it.
- Textarea input: **Enter** sends a message, **Shift + Enter** inserts a newline.
- Sessions are created automatically on first message if none exists.

### `ProfilePage.jsx`
- Displays: Username, Email, Role, Status (Active / Inactive), Verification status, Member Since, Last Login.
- Inline edit for Full Name.
- Change-password section with live complexity feedback.

---

## Shared Components

### `MessageBubble`
Renders a single message. Props: `role` (`"user"` | `"assistant"` | `"error"`), `content`.
- User messages: TTC blue background (`#003471`), white text.
- Assistant messages: white background, dark text.
- Error messages: light-red background, red text.

### `FeedbackBar`
Star rating (1–5) submitted per session via `chatApi.submitFeedback()`.

---

## API Layer

All HTTP calls go through a single Axios instance defined in `src/api/client.js`.

### `client.js` — Axios instance
- Base URL: `VITE_API_URL` env variable (defaults to `http://localhost:8000`).
- Timeout: 15 seconds.
- **Request interceptor**: attaches `Authorization: Bearer <token>` from `localStorage` on every request.
- **Response interceptor**: on a 401 response, if a token was present, clears `localStorage` and redirects to `/login`. This prevents login/register 401 errors from triggering a redirect.

### `auth.js`
| Function | Method | Endpoint |
|---|---|---|
| `login(data)` | POST | `/api/auth/login` |
| `register(data)` | POST | `/api/auth/register` |
| `refresh()` | POST | `/api/auth/refresh` |
| `me()` / `getMe()` | GET | `/api/auth/me` |
| `updateMe(params)` | PUT | `/api/auth/me` |
| `resetPassword(params)` | POST | `/api/auth/reset-password` |

### `chat.js`
| Function | Method | Endpoint |
|---|---|---|
| `sendMessage(data)` | POST | `/chat` |
| `createSession(data)` | POST | `/api/sessions` |
| `getSession(id)` | GET | `/api/sessions/:id` |
| `listSessions(params)` | GET | `/api/sessions` |
| `updateSession(id, data)` | PATCH | `/api/sessions/:id` |
| `submitFeedback(id, data)` | POST | `/api/sessions/:id/feedback` |

---

## Auth Context

`src/context/AuthContext.jsx` provides global authentication state via React context.

```jsx
const { user, token, login, logout, loading } = useAuth();
```

- `user` — decoded user object (`username`, `email`, `role`, etc.) or `null`.
- `token` — raw JWT string or `null`.
- `login(token)` — stores token, decodes user, sets state.
- `logout()` — clears storage, resets state, redirects to `/login`.
- `loading` — `true` while the initial token check runs on mount.

Wrap the component tree with `<AuthProvider>` in `App.jsx` (already done).

---

## Routing

Defined in `src/App.jsx` using React Router v7:

| Path | Component | Notes |
|---|---|---|
| `/` | — | Redirects to `/chat` |
| `/chat` | `ChatPage` | Requires auth |
| `/login` | `LoginPage` | Public |
| `/register` | `RegisterPage` | Public |
| `/profile` | `ProfilePage` | Requires auth |
| `*` (any other) | — | Redirects to `/chat` |

---

## Branding & Colors — How to Change Them

There is no single CSS variable file yet; the brand colors are used directly in each module. The two primary brand colors are:

| Token | Hex | Used for |
|---|---|---|
| TTC Blue | `#003471` | Sidebar background, buttons, headings, user chat bubble, active accents |
| TTC Red | `#e31937` | "Send" button, error highlights, gradient endpoint, accent borders |

### Files that contain these colors

| File | What it styles |
|---|---|
| `src/pages/Auth.module.css` | Login/Register page background gradient, logo text, button, input focus |
| `src/pages/ChatPage.module.css` | Sidebar background, send button, textarea focus |
| `src/pages/Profile.module.css` | Profile header gradient, section headings, primary buttons, error borders |
| `src/components/MessageBubble.module.css` | User bubble background, assistant accent, error bubble |

### Step-by-step: change the primary blue

1. Open each file listed above.
2. Find every occurrence of `#003471` — use VS Code's **Find in Files** (`Cmd+Shift+F`) with the search term `#003471` scoped to `frontend/src/`.
3. Replace with your new hex value (e.g. `#0057b8`).
4. Rebuild: `npm run build`.

### Step-by-step: change the primary red

Same process — search for `#e31937` across `frontend/src/` and replace.

### Recommended: add CSS custom properties (future improvement)

To make global color changes easier, add this to `src/index.css`:

```css
:root {
  --color-primary: #003471;
  --color-accent:  #e31937;
  --color-success: #28a745;
}
```

Then replace hard-coded hex values in each module CSS file with `var(--color-primary)` etc. This means future color changes only require editing one place.

### Other colors in use

| Hex | Purpose | File |
|---|---|---|
| `#28a745` | Active / verified status (green) | `Profile.module.css` |
| `#e6a817` | Neutral feedback star | `FeedbackBar.module.css` |
| `#2a7a3b` | Positive feedback star | `FeedbackBar.module.css` |
| `#c0001a` | Error text in message bubbles | `MessageBubble.module.css` |

---

## CSS Modules Convention

Each page and component has a co-located `.module.css` file. Styles are imported and applied as an object:

```jsx
import styles from "./ChatPage.module.css";
// ...
<div className={styles.sidebar}>…</div>
```

Class names are automatically scoped to the component — no naming collision between files.

Global styles (box-sizing reset, body font) live in `src/index.css`.

---

## Building & Serving from the Backend

After `npm run build`, Vite writes output to `frontend/dist/`:

```
frontend/dist/
├── index.html
└── assets/
    ├── index-<hash>.js
    └── index-<hash>.css
```

The FastAPI backend (`main.py`) serves this automatically:

- `GET /assets/*` — served from `frontend/dist/assets/` via `StaticFiles`.
- `GET /` — returns `frontend/dist/index.html`.
- `GET /{any_path}` — returns `index.html` (SPA fallback for client-side routes).

No separate web server (nginx, etc.) is needed for single-machine deployment.

---

## Linting

```bash
npm run lint
```

ESLint is configured in `eslint.config.js` with the `react-hooks` and `react-refresh` plugins. Fix lint errors before committing.

---

## Error Handling Patterns

### Field-scoped errors from the backend

The backend returns validation errors as a JSON array:

```json
{
  "detail": [
    { "loc": ["body", "username"], "msg": "Invalid username", "type": "value_error" }
  ]
}
```

The `loc` field determines where the error is shown in the UI:

| `loc[1]` value | Displayed in |
|---|---|
| `"username"` | Username field helper text |
| `"password"` | Password field helper text |
| `"email"` | Email field helper text |
| `"non_field_errors"` | Form-level error box above all fields |

`LoginPage.jsx` implements `buildLoginErrors(detail)` to parse this array and populate per-field error state. To add a new field error, add a case for the new `loc` key in that function.

