# Angular Page Links — 4 pages wired together with buttons

A minimal Angular app whose only job is to show **where a button lives** and
**how it points at another page**. Copy these two patterns into your own pages.

- **Pages (components):** Home, Orders, Reports, Admin
- **Links:** every page has buttons to the other pages (+ Home)
- **Two ways to link:** `routerLink` on an `<a>`, or `(click)` + `Router.navigate`

---

## 1. Run the server

```bash
cd angular-page-links
npm install          # only the first time
npm start            # = ng serve, http://localhost:4200
```

Open **http://localhost:4200**. To expose it on your LAN:

```bash
npx ng serve --host 0.0.0.0 --port 4300   # then http://<your-ip>:4300
```

Production build (static files you can host anywhere):

```bash
npm run build
# output: dist/angular-page-links/browser
```

> Each "page" is a component, and the router swaps which component is shown.
> There is only **one** real HTML file (`src/index.html`) — the 4 pages are
> component templates, not 4 separate `.html` files. If you truly have 4
> standalone `.html` files, see section 6.

---

## 2. The route table — the addresses your buttons point to

`src/app/app.routes.ts`:

| URL       | Page component             |
|-----------|----------------------------|
| `/`       | `Home`  (`pages/home`)     |
| `/orders` | `Orders` (`pages/orders`)  |
| `/reports`| `Reports` (`pages/reports`)|
| `/admin`  | `Admin` (`pages/admin`)    |
| `**`      | redirect to `/`            |

**A button links to a page by matching a `path` in this table.** If the path
isn't here, the click goes to the `**` fallback (Home).

---

## 3. Where each button is (the file to edit)

Every page's buttons are in that page's `.html` file:

| Page    | Buttons file                              |
|---------|-------------------------------------------|
| Home    | `src/app/pages/home/home.html`            |
| Orders  | `src/app/pages/orders/orders.html`        |
| Reports | `src/app/pages/reports/reports.html`      |
| Admin   | `src/app/pages/admin/admin.html`          |

Example — `home.html`:

```html
@for (l of links; track l.path) {
  <a class="btn" [routerLink]="l.path">{{ l.label }} &rarr;</a>
}
<button class="btn ghost" (click)="go('/orders')">Go to Orders (code)</button>
```

The destinations come from the `links` array in `home.ts`:

```ts
protected readonly links = [
  { path: '/orders',  label: 'Go to Orders' },
  { path: '/reports', label: 'Go to Reports' },
  { path: '/admin',   label: 'Go to Admin' },
];
```

### To link one button to another page
Change its `path` to a route from section 2:

```ts
{ path: '/admin', label: 'Go to Admin' }   // <-- edit this path
```

### The two link styles
```html
<!-- 1. Declarative (preferred: real link, keyboard/new-tab friendly) -->
<a class="btn" routerLink="/orders">Go to Orders</a>

<!-- 2. Programmatic (when you must run code first) -->
<button class="btn" (click)="go('/orders')">Go to Orders</button>
```
```ts
go(path: string) { this.router.navigate([path]); }
```

Both need `RouterLink` (and `Router` for `navigate`) imported in the page's
`.ts` — already done in this app:

```ts
imports: [RouterLink],
protected readonly router = inject(Router);
```

---

## 4. Adding a 5th page (3 steps)

```bash
npx ng generate component pages/invoices --skip-tests
```

1. **Register the route** in `src/app/app.routes.ts`:
   ```ts
   { path: 'invoices', component: Invoices, title: 'Invoices' },
   ```
2. **Add it to the top nav** in `src/app/app.ts`:
   ```ts
   { path: '/invoices', label: 'Invoices' },
   ```
3. **Link to it** from any page by adding to that page's `links` array:
   ```ts
   { path: '/invoices', label: 'Go to Invoices' },
   ```

---

## 5. How the shell works

- `src/index.html` loads `<app-root>`.
- `src/app/app.html` = top nav + `<router-outlet />`.
- `app.routes.ts` says which component fills the outlet for each URL.
- Clicking a `routerLink` changes the URL → the router swaps the component.
  **No page reload.**

---

## 6. If your 4 pages are plain `.html` files

The router pattern still applies, but for real file-to-file links the equivalent
is a normal anchor — no Angular needed:

```html
<!-- page2.html -->
<button onclick="location.href='page1.html'">Back to Page 1</button>
<a class="btn" href="page3.html">Go to Page 3</a>
```

Rules that keep it working: the 4 files sit in the **same folder**, use
**relative** names (`page3.html`, not `/page3.html`), and each button's target
must exactly match a real file name.

---

## File map

```
src/
  index.html                     # the only real HTML entry
  styles.css                     # shared styling (buttons, nav)
  app/
    app.ts / app.html / app.css  # shell: top nav + <router-outlet/>
    app.routes.ts                # URL -> page table  ← link targets
    pages/
      home/    home.ts|html|css  # "page 1"
      orders/  orders.ts|html|css
      reports/ reports.ts|html|css
      admin/   admin.ts|html|css
```
