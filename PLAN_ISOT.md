# PLAN_ISOT.md — Kill Feed Generator → isot111.com Theme

Purpose: add an optional **isot** visual theme to the FastAPI/Jinja kill feed generator, gated behind `?layout=isot`, that mirrors `https://isot111.com/` exactly. Preserve all existing behavior/logic/data; theming is a pure presentational layer added on top.

---

## 0. Golden rules (read first)

1. **Do not touch** any generation logic (`generator.py`, `rev_generator.py`, `self_kill_generator.py`, `revive_generator.py`) or any route's data/form handling. This is styling-only.
2. The default layout must be **byte-for-byte unchanged** so existing users are unaffected. `?layout=isot` (or `layout=isot111`) is the opt-in switch. Any other/missing value → current look.
3. Keep it **single-source-of-hidden**: mark ALL isot-specific CSS with a short banner comment block (`/* ===== ISOT THEME (layout=isot) ===== */`) so it's obvious and easy to revert.
4. Never break keyboard access, form labels, or the generated-preview display.
5. Prefer **CSS custom properties** for all colors. Light theme optional; primary target is dark isot look.

---

## 1. Entry-point wiring (server side)

**File:** `main.py` — the `GET "/"` route (`form_page`) currently:
```python
@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
```
Add an optional query flag and pass it into the Jinja context, so the server can emit a `<html … data-layout="isot">` (or `<body data-layout="isot">`) marker on the rendered page:

- Accept `layout: str = Query("default")` on the GET route.
- Normalize: `layout = layout if layout in ("isot", "isot111") else "default"`.
- Inject into the `context` dict sent to `templates.TemplateResponse` (key e.g. `layout`).
- Note: the POST route rendering the same `form.html` should also re-derive/preserve the layout from a hidden form field, so a form submission doesn't drop the theme back to default. (Hidden input carrying `?layout=isot` is acceptable; do not alter the POST handler's validation logic.)

---

## 2. Template marker

**File:** `templates/form.html`
- On `<body>` (already exists), emit a data attribute only when isot is active:
  ```html
  <body data-layout="{{ layout }}" ...>
  ```
  If `layout == "default"`, the attribute value should just be `default` so CSS scoping below never matches.
- Confirm the existing structure stays identical when layout is default.
- Do NOT reorder the DOM; only add the attribute + optionally a small wrapper class if needed for the "screen-app" look.

---

## 3. Theme tokens (copy these EXACT values from isot111.com)

These are the real tokens read from `isot111.com/css/styles.css`. Use them verbatim in the isot-scoped CSS.

```css
/* Design tokens — isot111.com "Clear Sky Serenity" */
--bg-grad: radial-gradient(130% 100% at 30% 0%, #1E6FA8 0%, #1a3d34 45%, #0a1710 100%);
--accent: #6FA8D4;
--accent-ink: #2F4A22;
--gold: #7A9E4B;
--gold-ink: #2F4A22;
--ink: #CFE4F2;
--ink-soft: rgba(207,228,242,.82);
--ink-mute: rgba(207,228,242,.58);
--card: #16281f;
--card-hi: #1f3a2c;
--card-border: rgba(111,168,212,.45);
--radius: 18px;
--radius-lg: 24px;
--radius-sm: 12px;
--shadow: 0 10px 30px rgba(0,0,0,.25);
--maxw-wide: 1080px;
--gap: 14px;
--font: 'Nunito', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
--font-display: 'Chakra Petch', var(--font);
--gold: #FFD84D;          /* primary CTA / highlight amber */
--gold-text: #FFD84D;     /* section-title span accent */
```

**Accent/highlight amber used throughout isot:** `#FFD84D`.
**Section accents:** `#FFD84D` on headings/spans and primary buttons; buttons use `background:#FFD84D; color:#141a12;`.
**Dark text-on-gold:** `#141a12`.

### Fonts (load from Google Fonts, matching isot)
- Body / UI: **Nunito** weights 400,600,700,800,900.
- Display / headings / labels / monospace-ish stats: **Chakra Petch** weights 600,700.
- Google Fonts URL isot uses:
  `https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Chakra+Petch:wght@600;700&display=swap`
- Add `<link rel="preconnect">` for `fonts.googleapis.com` and `fonts.gstatic.com` (crossorigin) and the stylesheet link, gated to the isot layout (or always include but only apply under isot scope — recommend gating to avoid altering default).

### Glass-card recipe (used by every card/panel on isot)
```css
background:rgba(255,255,255,.14);
backdrop-filter:blur(16px);
-webkit-backdrop-filter:blur(16px);
border-radius:var(--radius-lg);
box-shadow:inset 0 0 0 1px rgba(111,168,212,.45), 0 10px 30px rgba(0,0,0,.25);
```
Topbar & hero use `backdrop-filter:blur(16px)` with subtle glass.

---

## 4. What to restyle under `[data-layout="isot"]` (or `html[data-layout="isot"] body …`)

Scope **every** isot override under a `[data-layout="isot"]` ancestor selector so the default theme is never touched. Layer order proposed:

- **Page background:** replace flat `#0D0D0F` with `var(--bg-grad)`. Keep the existing `.bg-overlay` noise but tone it to the blue→green gradient. The center-of-page flex layout can stay, but make the app read like a floating glass panel on the gradient.
- **Root font:** `font-family: var(--font)` (Nunito) globally under isot.
- **Headings / titles / labels / buttons:** `font-family: var(--font-display)` (Chakra Petch), `font-weight:700`, letter-spacing ~`.03em–.04em`; uppercase for breadcrumb-y labels like isot does (`.menu-name`, section labels).
- **Primary buttons / active tabs / selected segmented option:** isot uses a SOLID amber pill: `background:#FFD84D; color:#141a12; border-radius:999px or var(--radius-lg);` Hover → slightly stronger amber with glow (`text-shadow`/`box-shadow` amber glow). Map the tool's existing `.btn`-equivalent and any `.active`/selected states to this pill.
- **Cards / panels / inputs:** isot uses frosted **glass** (recipe above) with subtle 1px light-blue inner border (`rgba(111,168,212,.45)`) and soft shadow; radii 18–24px. Convert the tool's panels, field groups, and the preview frame to this glass treatment.
- **Inputs & selects:** translucent white fill (`rgba(255,255,255,.08–.14)`), `backdrop-filter:blur(12–16px)`, `border:1px solid rgba(111,168,212,.45)`, `border-radius:var(--radius-sm/12px)`, light text `#CFE4F2`, focus → amber/blue ring. Placeholder color `rgba(207,228,242,.58)`.
- **Primary accent color** for focus rings, links, and secondary highlights: `#6FA8D4` (the isot blue accent).
- **Text hierarchy:** headings `#fff`; body `var(--ink)#CFE4F2`; secondary `var(--ink-soft)`; muted/labels `var(--ink-mute)`.
- **Preview canvas note / "topbar"** of the preview panel: match the isot glass topbar look; keep any scanline/noise effect but tint it.
- **Skeletons/skeleton-app** (the loading shimmer, if present in `form.html`): restyle shimmer color to a soft blue/amber-tinted sweep so it still reads on the dark glass — optional, do not delay load.

---

## 5. Deliverables

1. `main.py`: add `layout` query param + context injection + hidden-field round-trip on POST. Minimal diff.
2. `templates/form.html`: add `data-layout="{{ layout }}"` on `<body>` + a hidden input to preserve layout across POST; add Google Fonts links.
3. `static/isot.css` (NEW file) OR a clearly-bannered appended section in `static/style.css` — **recommend a new `static/isot.css`** gated entirely under `[data-layout="isot"]` and only linked when isot is active (conditionally included in the template), so default CSS stays untouched.
4. Serve `isot.css` with the same long-cache approach (the project already sets `Cache-Control: max-age` on `/static`). If using a cache-busting `?v=` versioning (the codebase already does `file_version`), follow the same pattern for `isot.css`.
5. Test matrix:
   - `GET /` → default look (no regressions).
   - `GET /?layout=isot` → isot theme, all controls usable.
   - Submit the form under isot → theme persists (hidden field), image still generates & previews & downloads.
   - Mobile viewport narrow width → glass layout stays responsive, no horizontal overflow.

---

## 6. Explicit non-goals (do NOT do these)

- No change to any kill feed image output (the generated PNG must be identical).
- No change to `/api/preview`, `/api/stats`, `/download/*`, or cookie/visitor logic.
- No editing `generator*.py`, `revive_generator.py`, `self_kill_generator.py`, `stats.py`.
- No removal or "improvement" flash of the default theme outside the `data-layout="isot"` scope.
- No analytics, tracking, or new dependencies unless already present.

---

## 7. Verification checklist

- [ ] `GET http://localhost:PORT/` identical to current site.
- [ ] `GET http://localhost:PORT/?layout=isot` renders isot theme.
- [ ] Fonts load (Nunito + Chakra Petch), amber `#FFD84D` accents present.
- [ ] Background gradient blue→green matches isot.
- [ ] All form fields / segmented controls usable & focusable.
- [ ] Kill feed preview still appears inside its frame after generation in both modes.
- [ ] No broken image paths introduced.
- [ ] Files: main.py (+layout), templates/form.html (+data-layout, hidden field, fonts), static/isot.css (new) — commit only styling-related diffs.
