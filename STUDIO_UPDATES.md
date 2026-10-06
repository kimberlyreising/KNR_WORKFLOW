# Studio updates and visitor analytics

## Email capture

The Studio Updates signup uses the site's existing Formspree form `xrenkveq`.
Signups have the subject **KNR Studio — email signup**, source
`studio_updates_signup`, an explicit consent field and a consent-version field.
Find the requests in the same Formspree dashboard/inbox as commission inquiries.
Both forms share that account's submission quota and any existing form rules.
Only a successful HTTP response shows a received message; failures preserve the
visitor's entry. The form also works without JavaScript via Formspree's hosted flow.

This collects signup requests. It does not send newsletters, double-opt-in
confirmations, manage automatic unsubscribe links or create paid memberships.
Before sending a mailing, use a mailing service with unsubscribe handling and
import only consenting signups. Honor removal requests submitted via Contact.

## Visitor analytics — awaiting account connection

`assets/studio-config.js` currently has an empty `measurementId`. No Google
Analytics script or visitor tracking runs until a real ID is provided. Create or
select the KNR Studio web stream for `https://kimberlyreising.com` in Kimberly's
Google Analytics account, then set its `G-...` Measurement ID in that file.
Use America/New_York as the property's reporting timezone.

In the web stream's Enhanced Measurement settings, disable **form interactions**
and **browser-history page views**. This code sends its own sanitized events.
The tracker removes query strings and fragments from page URLs and uses only the
referrer's origin. It never reads email addresses or other form entries. Advertising
storage, advertising personalization and Google Signals are disabled in the tag.

Google Analytics is loaded only after the visitor allows analytics. Declining
prevents tracking. Analytics Preferences in the footer lets them change their
choice. These reports are estimates of consenting browsers, not a census of all
people, and do not reconstruct visits from before activation.

| Event | Meaning |
| --- | --- |
| `page_view` | One page load after analytics permission |
| `section_click` | Click to Prints, Commissions, About, Contact or Studio Updates |
| `stripe_click` | Print checkout click, with artwork title; **not a confirmed sale** |
| `support_click` | Click to a KNR Studio support checkout, with support tier; **not a confirmed payment** |
| `generate_lead` | Formspree accepted a studio signup request |

View Users, Views and Traffic acquisition in Google Analytics. Register
`artwork_title`, `support_tier`, `section_id` and `lead_type` as event-scoped custom dimensions to
break down those events. Stripe remains the source for actual purchase totals.

## Verification and deployment

The site is hosted by Netlify. Publish through the existing GitHub deployment
connection. Check the live signup at `/#studio-updates` and ensure a real signup
arrives in Formspree before relying on it. After the ID is connected, allow
analytics and confirm a `page_view` in GA Realtime, then test a print click and a
successful signup. Test declining in a clean browser too.

No payment information or new paid service is needed by the added code. Existing
Formspree account limits still apply.
