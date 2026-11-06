# MyTadbir: UI prompt for Stitch

Paste **Part 1** first so Stitch learns the design system. Then paste one screen from **Part 2** at a time; Stitch does better with one screen per prompt than with all of them at once. Part 3 lists the data each screen shows, so the generated UI can be wired to our backend without renaming fields.

---

## Part 1 — Design system (paste first)

Design a web application called **MyTadbir**, a Malaysian public-service desk where a citizen makes one request and the system routes it to the right government department and carries it out. It is used by citizens only; officers work in their own back-office systems, and their decisions appear in MyTadbir as case updates. It must feel like a serious, trustworthy, production government service, calm and precise, not a startup landing page and not an AI demo.

**Brand and tone**
- Monochrome brand: black, white and a disciplined grey scale. The interface chrome (backgrounds, text, borders, icons, buttons) is black and white only.
- Colour appears only where it carries meaning: status, severity, charts, map layers and department identity. Never use colour as decoration.
- No gradients, no glow, no glassmorphism, no purple, no sparkles or "magic" icons, no robot or brain illustrations, no emoji. Nothing should look AI-generated.
- Do not use the Malaysian coat of arms, any real ministry or agency logo, or any real government crest. MyTadbir has its own wordmark.
- Wordmark: "MyTadbir" set in the display face, with a small solid black square mark containing a white "M". Inverted (white on black) in dark areas.
- Voice: short, plain, helpful. Bahasa Malaysia and English with a BM / EN switch; every label exists in both languages. Default language follows the user's setting.

**Colour tokens (light theme)**
- `--bg` #FFFFFF, `--surface` #FAFAFA, `--surface-2` #F4F4F5, `--line` #E4E4E7, `--line-strong` #D4D4D8
- `--ink` #09090B (primary text, primary buttons), `--ink-2` #3F3F46, `--muted` #71717A
- Primary button: black background, white text. Secondary: white background, 1px `--line-strong` border, black text. Destructive: black text with a red outline.
- **Status** (text + 10% tint background for pills): success #15803D, warning #B45309, danger #B91C1C, info #1D4ED8, neutral #52525B.
- **Department colours** (used only for small dots, chart series, map layers and the 3px left edge of department chips): Health #DC2626, Education #2563EB, Local Government #0F766E, Immigration #7C3AED, Road Transport (JPJ) #EA580C, Inland Revenue (LHDN) #CA8A04, Social Welfare (JKM) #DB2777, Police / Home Affairs #1E3A8A, Agriculture & Environment #16A34A, Cross-Agency #475569.
- **Dark theme**: `--bg` #09090B, `--surface` #111113, `--surface-2` #18181B, `--line` #27272A, `--ink` #FAFAFA, primary button white with black text. Status and department colours keep their hue, lightened one step for contrast.

**Typography**
- Headings and wordmark: **"Plus Jakarta Sans"** 600–700, letter-spacing −1%. Do not use Inter, Roboto or Space Grotesk.
- Body and UI: **"IBM Plex Sans"** 400/500, 15px base, 1.5 line height.
- Numbers, IDs, case numbers, hashes, timestamps: **"IBM Plex Mono"** 500, tabular figures.
- Type scale: 12 / 13 / 15 / 17 / 20 / 24 / 32. Uppercase section labels at 11px, 600, letter-spacing 0.08em, `--muted`.

**Icons**
- One line-icon family only (Lucide), 1.5px stroke, 18px in navigation, 16px inline. Icons always use `currentColor`, so they are black in light mode and white in dark mode. Never coloured icons, except a status dot.
- Section expand / collapse uses a **chevron-down** that rotates 180° when open. Never "+" or "−".

**Shape, spacing, depth**
- 8px spacing grid. Radius: 10px cards, 8px inputs and buttons, 999px pills. 1px borders instead of shadows; one soft shadow (0 8px 24px rgba(0,0,0,.08)) only on floating layers (menus, drawers, dialogs).
- Dense but breathable: tables 44px rows, cards 16–20px padding.

**Motion** (smooth and quiet; respect `prefers-reduced-motion`)
- 160ms ease-out for hover and press; 220ms cubic-bezier(.2,.8,.2,1) for drawers, popovers and section expand.
- Chat messages and case steps fade up 6px as they arrive. Live steps show a small pulsing dot while running, then a check.
- Skeleton loaders in `--surface-2` with a slow shimmer; no spinners except inside buttons.
- Numbers on dashboards count up once on first load.

**Layout and responsiveness**
- Desktop (≥1280px): resizable sidebar | main workspace | collapsible right panel (Live agent trace).
- Tablet (768–1279px): sidebar stays; the right panel becomes a slide-over drawer.
- Phone (<768px): sidebar becomes a left drawer opened from a menu button; right panel becomes a bottom sheet; tables turn into stacked cards; the chat input stays pinned to the bottom above the keyboard.
- Accessibility: WCAG 2.1 AA contrast, visible 2px black focus ring, all actions reachable by keyboard, 44px minimum touch targets.

---

## Part 2 — Screens (paste one at a time)

### Screen 1 — Sign in
Calm, simple and official. Lots of white space; nothing crowded.
- Centered card, 400px wide, on a white page. Above it: the MyTadbir wordmark and one line, "Satu pintu untuk semua perkhidmatan kerajaan" / "One front door to government services".
- Primary action: a full-width black button "Log masuk dengan MyDigital ID" with a small shield icon.
- A thin divider "atau / or", then two fields (MyKad number or username, password), a "Show password" eye toggle, "Remember this device" checkbox, and a secondary "Log masuk" button. "Lupa kata laluan?" link under the password.
- Top-right: BM / EN segmented switch. Bottom of the page: small grey links (Privacy, Accessibility, Help, Contact) and "© 2026 MyTadbir".
- No marketing copy, no feature lists, no demo account hints, no illustrations.
- States: loading button, error message under the form ("Nombor MyKad atau kata laluan tidak sah"), locked account.

### Screen 2 — App shell and sidebar (chat-app pattern, like ChatGPT or Claude)
- **Resizable sidebar**: drag handle on its right edge (min 220px, max 420px, default 272px); double-click the handle to reset; a collapse button turns it into a 64px icon rail with tooltips; the width is remembered. Sidebar background `--surface`, 1px right border.
- Top of sidebar: wordmark, then a full-width black **"New request"** button (shortcut shown: Ctrl N), then a search field "Search cases and chats" (Ctrl K).
- Collapsible groups with chevron-down headers:
  - **Commands**: a single **"Departments"** button. Clicking it opens a command palette (popover anchored to the button, or a centered dialog on small screens) listing the 10 departments with their colour dot, active-case count and a searchable list of each department's services. Choosing one pins it as the target of the next request. Below it: "Quick templates" and "Track a case by ID".
  - **My activity**: My cases (with a count badge), Action centre (count badge), Payments, Documents, Calendar, Notifications (unread badge).
  - **Live views**: Service map, Impact dashboard.
  - **Transparency**: Policy library, Audit trail (the citizen's own cases).
  - **Conversations**: Pinned, then Today / Yesterday / Previous 7 days / Older. Each row shows the auto title and case IDs in mono; hover shows a "⋯" menu (Rename, Pin, Share case link, Delete).
- Sidebar footer: avatar, name, a small "MyDigital ID verified" check; clicking opens a menu: Profile, Settings, Language, Theme (Light / Dark / System), Help & feedback, Sign out.
- Top bar of the workspace: page title, active case chip (e.g. "MT-26-000123 · In progress"), the agent status pill (pulsing dot + "Local Government · Incident dispatcher"), BM/EN switch, and a toggle for the right panel.

### Screen 3 — Console (the main chat workspace)
A chat workspace where every reply is a structured, actionable card, not plain prose.
- **Empty state**: greeting with the user's first name, one line of help text, and 4–6 **suggested request chips** generated for this user (e.g. "Report a clogged drain", "Renew my road tax", "Check my summons", "Book a clinic appointment"). Chips use the user's chosen language and change with context (time of year, open cases, recent activity).
- **Input composer** pinned at the bottom: accepts only **text, images and files** (PDF, DOC/DOCX). An attach button opens a menu with "Photo" and "File"; drag-and-drop and paste are supported; attachments show as removable chips with a type icon, name and size, and image thumbnails. Show the accepted types in the empty attachment hint. A department chip appears inside the composer when a department was chosen from Commands. Send button black; Enter to send, Shift+Enter for a new line.
- **Suggested follow-up chips** appear above the composer after each answer (e.g. "Track contractor", "Download work ticket", "Add more photos"), in the user's language.
- **Message types**:
  1. Citizen message bubble (right aligned, black background, white text) with image thumbnails or file chips.
  2. **Router card**: "2 requests found" with one row per request: department chip with colour edge, service name, a small confidence bar with %, and a "Will be verified by an officer" badge when confidence is low. A note row when the run order was changed ("Summons first: an unpaid summons may block renewal").
  3. **Clarifying question card**: one question and 2–4 answer chips.
  4. **Case card**: case ID (mono) with copy button, status pill, a small **complexity level** badge ("Level 4 · Legal judgement", 1–5 shown as five small bars, with a tooltip listing why and which model each step used), department chain (Local Government → Agriculture & Environment) as connected chips, a vertical **step list** that fills in live (check icon when done, pulsing dot while running), a **Policy basis** block with numbered citations (document title, page, link to the official source; assumptions shown with an amber left border), **artifacts** row (work ticket PDF, receipt) with preview on click, an **action box** when a human decision is needed ("Confirm RM150.00 payment" with Confirm / Cancel), and a closing **summary with next steps**.
  5. System notices (handoff, reconnecting) as quiet centered grey text.
- Per-message actions on hover: copy, export case as PDF, helpful / not helpful.
- **Right panel — Live agent trace**: chronological list of agent steps for the current conversation; each row shows time (mono), a layer tag (Router, Case manager, Department, Service, Sub-module), the actor, a one-line description, and the model used for that step in small mono text ("deepseek-flash · low · 412 tok"); rows expand to show the raw JSON. Filter chips by layer; a "Follow live" toggle that auto-scrolls.

### Screen 4 — My cases
- Toggle between **Board** (columns: Received, In progress, Waiting for you, Waiting for officer, Resolved) and **Table**.
- Each case shows case ID, department colour dot and name, request summary, current stage, SLA timer (green / amber / red by remaining time), last update.
- Filters: department, status, date range, search. Saved filter chips.
- Clicking a case opens a right drawer: summary, department chain, timeline, documents, payments, messages, "Open conversation" button.

### Screen 5 — Payments
- Top: four KPI tiles (Paid this year, Pending, Refunds received, Upcoming due) with mono figures in RM and a small sparkline.
- A stacked bar chart by month coloured by department.
- Table: date, department (dot + name), item, case ID, amount (right aligned, mono; refunds shown with "+" in green), status pill (Paid green, Pending amber, Failed red, Refunded blue), receipt button.
- Filters: department, status, date range; "Export CSV".
- Upcoming dues list ("Road tax expires in 12 days — Renew").

### Screen 6 — Documents
- Grid / list toggle. Each item: file-type icon, title, department dot, case ID, date, and **tag chips** (e.g. "drainage", "Act 133", "work-ticket", "Petaling Jaya").
- Left filter column: type (Uploads, Work tickets, Receipts, Licences, Briefs), department, tags (multi-select with counts), date.
- Preview pane on the right for PDFs and images; actions: download, share link, open case.

### Screen 7 — Calendar
- Month / Week / Agenda views; events coloured by department.
- Event detail popover: time, place, department, case ID, preparation checklist with checkboxes, "Reschedule" and "Add to my calendar (.ics)".
- Side list: "Next 7 days".

### Screen 8 — Notifications
- Grouped by case ID, newest first; unread dot; channel icon (in-app, SMS, email).
- Tabs: All, Action needed, Updates. "Mark all as read". Each group links to its case.

### Screen 9 — Service map
A full-height map (Google Maps JavaScript API, light monochrome map style; dark style in dark mode).
- **Left floating panel** with layer toggles and live counts:
  - Reported cases (by status: open, dispatched, resolved)
  - Flood (river-level stations by normal / alert / warning / danger, and flood-watch areas as translucent circles)
  - Fire and rescue incidents
  - Contractors and crews en route (animated dashed route to the incident with ETA)
  - Facilities: schools, clinics and hospitals, evacuation centres
- **Filters**: date range, department, severity, status, "Near me" radius slider; search a place or postcode.
- Toggles: heat map, marker clustering, traffic.
- Clicking a marker opens a right card: photo, case ID, severity, department, status timeline, assigned contractor and ETA, "Open case".
- Legend at bottom-left; "Last updated 2 min ago" with refresh.

### Screen 10 — Impact dashboard
- KPI row: cases handled, median time to resolve, contractors dispatched, fees processed, citizen satisfaction.
- Line chart: cases per day (last 30 days) by department; bar chart: average resolution time by department; donut: channel or request type; table: top request types.
- Department filter and date range at the top right. Charts use the department colours on a white background with light grey gridlines.

### Screen 11 — Action centre
Everything waiting on the citizen or on an officer, in one place.
- Two tabs: **Waiting for you** (confirm a payment, upload a missing document, answer a question) and **Waiting for an officer** (read-only: what the officer is reviewing, why, and the expected response time).
- Each item: case ID (mono), department dot, what is needed, why (one line plus policy citation), deadline or SLA timer, and the primary action button (e.g. "Confirm RM150.00 payment", "Upload document").
- Officer-review items show a progress state (Submitted → Under review → Decided) and the officer's decision note when it arrives.
- Count badge on the sidebar item.

### Screen 12 — Policy library
- Search bar with filters: department, document type (Act, By-law, Form, Guideline, Circular, Web page), language, access (Public / Needs login), **tags**.
- **Memory Bag status card**: active documents, passages, last full scan, next scan date, a change log (add / update / delete events with colour pills), shown read-only to the citizen as proof that sources are current.
- Results show title, agency, page, "as at" date, tag chips and an excerpt with the search terms highlighted; "Open official source" link.
- Documents table: title, agency, department, type, as-at date, access pill, last checked.

### Screen 13 — Audit trail
- Choose a case; a vertical timeline of every action (actor, action, time in mono), each with its hash (shortened, mono) and an expandable payload.
- A header badge "Hash chain verified" (green) or "Chain broken at entry #N" (red). "Export JSON" and "Export PDF".

### Screen 14 — Settings and profile
- Tabs: Profile (name, MyKad masked as 900101-10-•••• , address, phone), Language, Theme, Notifications (per channel and per type), Privacy (download my data, delete history), Connected services.

---

## Part 3 — Data the screens show (keep these field names)

| Screen | Endpoint | Fields |
|---|---|---|
| Sign in | `POST /api/auth/login`, `POST /api/auth/mydigitalid` | `token`, `user{id, role, name, mykad, verified}` |
| Console | `POST /api/requests` (multipart: `text`, `photos[]`, `files[]`, `thread_id`, `department`) | `thread_id`, `status`, `clarifying_question`, `intents[{case_id, department, submodule, confidence, verify_flag, order_note, level, level_reasons[]}]` |
| Console (live) | `GET /api/threads/{id}/trace` (Server-Sent Events) | `ts, layer, actor, event, case_id, data{…, llm{model, effort, completion_tokens}}` |
| My cases | `GET /api/cases` | `case_id, intent, current_department, chain[], status, verify_flag, created_at, updated_at, result, wrap{summary_en, summary_bm, next_steps[]}` |
| Payments | `GET /api/payments` | `id, case_id, department, description_en/bm, amount, direction, status, receipt, created_at` |
| Documents | `GET /api/documents` | `id, case_id, department, kind, title, tags[], created_at` |
| Calendar | `GET /api/appointments` | `id, department, title_en/bm, when, location, status` |
| Notifications | `GET /api/notifications` | `id, case_id, channel, en, bm, created_at` |
| Service map | `GET /api/map` | `kind (incident, contractor, flood_watch, school…), label, lat, lng, meta` |
| Impact | `GET /api/impact` | `cases, closed, dispatched, fees, pending_approvals, audit_entries` |
| Action centre | `GET /api/approvals`, `POST /api/approvals/{id}/decide` (citizen items only) | `id, case_id, action, reason, proposed, status, actor (citizen / officer)` |
| Policy library | `GET /api/policy/search`, `GET /api/policy/documents`, `GET /api/memory-bag` | `title_en/bm, page, url, as_at, agency, dept, access, tags[], excerpt`; `active_documents, chunks, last_full_scan, next_scan, recent_changes[]` |
| Audit | `GET /api/cases/{id}/timeline`, `GET /api/health` | `id, ts, actor, action, payload, hash`; `audit_chain_valid` |

Export the result as responsive HTML with Tailwind CSS, components split per screen, BM and EN strings kept in one dictionary, and no placeholder lorem ipsum: use realistic Malaysian content (Petaling Jaya, MBPJ, JPJ, RM amounts, MyKad formats with masked digits).
