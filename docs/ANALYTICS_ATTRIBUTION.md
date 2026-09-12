# GA4 / GTM tracking + order attribution

Existing Google infrastructure (do NOT create new property/container):
- GTM container: `GTM-TFC47QZW` (`NEXT_PUBLIC_GTM_ID`)
- GA4 Measurement ID: `G-RCPXZRSWLZ` (configured inside GTM)
- Google Tag ID: `GT-T5N4DC36`

## Frontend (`frontend/src`)

- `lib/analytics.ts` — the ONLY tracking layer. Pushes `view_item`,
  `add_to_cart`, `remove_from_cart`, `view_cart`, `begin_checkout`,
  `purchase` + deduped `virtual_pageview` to `window.dataLayer`.
  GA4 tags live in GTM; nothing hardcodes gtag separately.
- `lib/attribution.ts` — first-party first-touch + latest/session
  attribution. Cookie `gadgeto_attr` (1y) + `localStorage` mirror
  (`gadgeto_attr_first` / `gadgeto_attr_last`). UTM/gclid take precedence;
  same-site SPA navigations without new params keep the session touch.
- `components/GtmProvider.tsx` — pushes `virtual_pageview` + captures
  attribution on every SPA navigation (GTM script itself loads once via
  `next/script` in the layout).
- `components/GtmNoscript.tsx` — GTM `<noscript>` iframe fallback.
- `app/[locale]/layout.tsx` — GTM snippet + `<noscript>` fallback,
  Consent-Mode defaults (`denied`), `GtmProvider`, `ConsentBanner`.
- `components/ConsentBanner.tsx` — the single consent mechanism
  (`gadgeto_consent` in localStorage; `consent_update` dataLayer event).
- `purchase` fires exactly once per order via `trackPurchaseOnce`
  (`gadgeto_purchase_<orderId>` localStorage guard) on the checkout
  success page, using the backend order number as `transaction_id`.

## Backend

- Migration `045_order_attribution` adds 14 nullable columns to `orders`
  (`first_*` / `last_*`: source, medium, campaign, term, content,
  landing_page, gclid). Missing attribution → NULL, never breaks checkout.
- `POST /api/v1/checkout` accepts + persists the snapshot atomically
  with the order (values trimmed to column limits).
- Admin `GET /orders` returns source/medium/campaign columns;
  `GET /orders/{id}` returns the full order row (incl. attribution).

## Admin (`admin/src`)

- `lib/attribution-label.ts` — `formatAttribution()` list label
  (e.g. `Google / CPC · summer_sale`, `Direct`, `example.com / Referral`).
- Orders list: new `Джерело` column. Order detail: `Джерело трафіку`
  section with all 14 attribution fields.

## GTM container inspection result (2026-09-12, public gtm.js)

- Fetched `https://www.googletagmanager.com/gtm.js?id=GTM-TFC47QZW`
  (HTTP 200, ~332KB). The published container `resource` contains
  **zero tags, zero predicates, zero rules** (`"tags":[]`,
  `"predicates":[]`, `"rules":[]`) — only the 5 built-in URL macros.
- The live container therefore fires NO GA4 / Google Tag requests today.
  There is nothing to reuse or deduplicate: no GA4 config tag, no
  pageview tag, no History-Change pageview risk from GTM itself.
- Either the container was never configured, or the configured workspace
  was never submitted/published. Both cases need the same fix: configure
  + publish (see import bundle below).

## GTM/GA4 manual steps (required in Google UI)

> The recommended path is the ready-to-import bundle
> `docs/gtm/GTM-TFC47QZW-container.json` (see next section) +
> `Preview` + `Submit/Publish`. The manual click-path below is the
> equivalent for reviewers who prefer the UI.

1. GTM container `GTM-TFC47QZW`: add a Google tag using the
   existing measurement ID `G-RCPXZRSWLZ`.
2. Add GA4 Event tags for `view_item`, `add_to_cart`, `remove_from_cart`,
   `view_cart`, `begin_checkout`, `purchase` (use the `ecommerce` object
   from the dataLayer; `purchase` dedupes on `transaction_id` in GA4).
3. Add a GA4 pageview tag triggered by Custom Event `virtual_pageview`
   (NOT "All Pages" on History Change — that would double-count SPA
   navigations). Set the page path from `page_path`.
4. Consent: `consent_default` (denied) fires on every load;
   `consent_update` fires on banner choice. In GTM add the Consent-Mode
   settings: **Admin → Container Settings → Consent Settings → Consent
   overview** → enable `analytics_storage` + `ad_storage`, and on the
   Google tag enable "Consent initialization" with default state
   **Denied**; wire banner updates by adding a Google tag "Consent
   initialization" triggered by `consent_update` with the granted state,
   or use the tag's consent defaults + the `CJS - consent granted`
   variable pattern below. The app's inline `consent_default` push
   carries `analytics_storage` / `ad_storage` keys already — map them
   directly in the Google tag's Consent Settings so tags queue until
   consent is granted.
5. Verify with GTM Preview + GA4 DebugView; test gclid/UTM/referral
   scenarios from Part 10 of the task.

## Ready-to-import container bundle (recommended)

File: `docs/gtm/GTM-TFC47QZW-container.json`
(GTM **Admin → Import Container**, choose the JSON, target workspace
"Default", import option **Merge**, then **Preview** → test →
**Submit → Publish**.)

Contents (no duplicates, no History-Change pageviews):

| Tag | Type | Trigger |
| --- | ---- | ------- |
| GA4 – Google tag (G-RCPXZRSWLZ) | Google Tag (`googtag`) | Initialization – All Pages (fires once per full load) |
| GA4 – SPA pageview | GA4 Event `page_view`, `page_path={{DLV – page_path}}` | Custom event `virtual_pageview` only |
| GA4 – view_item | GA4 Event (ecommerce passthrough) | Custom event `view_item` |
| GA4 – add_to_cart | GA4 Event (ecommerce passthrough) | Custom event `add_to_cart` |
| GA4 – remove_from_cart | GA4 Event (ecommerce passthrough) | Custom event `remove_from_cart` |
| GA4 – view_cart | GA4 Event (ecommerce passthrough) | Custom event `view_cart` |
| GA4 – begin_checkout | GA4 Event (ecommerce passthrough) | Custom event `begin_checkout` |
| GA4 – purchase | GA4 Event (ecommerce passthrough) | Custom event `purchase` |

Variables: `DLV – page_path` (Data Layer v1, `page_path`);
`DLV – ecommerce` (Data Layer v1, `ecommerce`); `CJS – ecommerce items`
(Custom JS returning `ecommerce.items || []`).
Built-in variables enabled: Page URL, Page Path, Referrer (used by the
pageview tag). Ecommerce parameters are sent explicitly
(`currency={{DLV – ecommerce.currency}}`,
`value={{DLV – ecommerce.value}}`,
`transaction_id={{DLV – ecommerce.transaction-id}}`,
`items={{CJS – ecommerce items}}`) so GA4 receives the exact payloads
the app pushes — including UAH currency, backend order number as
`transaction_id`, and item id/name/price/quantity.

Why this avoids duplicates: pageviews fire ONLY on `virtual_pageview`
(one per full load + one per SPA route change, deduped app-side via
`__gtmPagePath`); there is no All-Pages/History-Change pageview tag, so
an SPA transition cannot produce two pageviews. `purchase` fires only
from the success page behind the `gadgeto_purchase_<id>` localStorage
guard; GA4 additionally dedupes repeat `transaction_id`s.
