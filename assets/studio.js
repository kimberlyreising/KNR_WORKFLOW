(() => {
  "use strict";
  const form = document.getElementById("studio-signup-form");
  const status = document.getElementById("studio-signup-status");
  const measurementId = (window.KNR_STUDIO || {}).measurementId || "";
  const supportLinks = (window.KNR_STUDIO || {}).supportLinks || {};
  const supportSection = document.getElementById("support");
  const stripeUrl = value => { try { const u = new URL(value); return u.protocol === "https:" && u.hostname === "buy.stripe.com" && /^\/[A-Za-z0-9]+$/.test(u.pathname); } catch { return false; } };
  const configured = /^G-[A-Z0-9]+$/.test(measurementId);
  const preferenceKey = "knr-analytics-consent-v1";
  const settings = document.getElementById("studio-analytics-settings");
  let initialized = false;
  const readPreference = () => { try { return localStorage.getItem(preferenceKey); } catch { return null; } };
  const savePreference = value => { try { localStorage.setItem(preferenceKey, value); } catch { /* This visit still respects the choice. */ } };
  const referrerOrigin = () => { try { return new URL(document.referrer).origin; } catch { return ""; } };
  let supportConfigured = false;
  document.querySelectorAll("[data-support-link]").forEach(anchor => {
    const key = anchor.dataset.supportLink;
    const url = supportLinks[key];
    if (!stripeUrl(url)) {
      anchor.removeAttribute("href");
      anchor.setAttribute("aria-disabled", "true");
      anchor.tabIndex = -1;
      return;
    }
    anchor.href = url;
    anchor.removeAttribute("aria-disabled");
    supportConfigured = true;
  });
  if (supportSection) supportSection.hidden = !supportConfigured;

  document.querySelectorAll('a[href="#studio-privacy"]').forEach(anchor => {
    anchor.addEventListener("click", () => { document.getElementById("studio-privacy").open = true; });
  });

  function track(name, properties = {}) {
    if (!configured || !initialized || window["ga-disable-" + measurementId] === true || typeof window.gtag !== "function") return;
    // Only callers' fixed section IDs and artwork titles are used. Never read form fields.
    window.gtag("event", name, {
      send_to: measurementId,
      page_location: location.origin + location.pathname,
      page_referrer: referrerOrigin(),
      ...properties
    });
  }

  // GA4 is enabled automatically unless this browser previously opted out.
  // Advertising-related consent remains denied. Persisted opt-outs stay off.
  function initializeAnalytics() {
    initialized = true;
    window["ga-disable-" + measurementId] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("consent", "default", {
      analytics_storage: "granted", ad_storage: "denied",
      ad_user_data: "denied", ad_personalization: "denied"
    });
    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      send_page_view: false,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      page_location: location.origin + location.pathname,
      page_referrer: referrerOrigin()
    });
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
    document.head.appendChild(script);
    track("page_view", { page_title: document.title });
  }

  function startAnalytics() {
    window["ga-disable-" + measurementId] = false;
    if (!initialized) return initializeAnalytics();
    window.gtag("consent", "update", { analytics_storage: "granted" });
  }

  function stopAnalytics() {
    window["ga-disable-" + measurementId] = true;
    if (initialized) window.gtag("consent", "update", { analytics_storage: "denied" });
    // Remove this property's first-party cookies when permission is withdrawn.
    document.cookie.split(";").forEach(cookie => {
      const name = cookie.trim().split("=")[0];
      if (name !== "_ga" && name !== "_ga_" + measurementId.slice(2)) return;
      const hostname = location.hostname;
      const domains = ["", hostname, "." + hostname, "." + hostname.replace(/^www\./, "")];
      domains.forEach(domain => {
        document.cookie = name + "=; Max-Age=0; Path=/; SameSite=Lax" + (domain ? "; Domain=" + domain : "");
      });
    });
  }

  if (configured) {
    // No interruptive consent banner. The footer offers a one-click opt-out.
    // Visitors who already declined remain opted out.
    if (readPreference() === "decline") {
      window["ga-disable-" + measurementId] = true;
    } else {
      startAnalytics();
    }
    if (settings) {
      settings.hidden = false;
      const updateSettingsLabel = () => {
        settings.textContent = readPreference() === "decline" ? "Turn on analytics" : "Turn off analytics";
      };
      updateSettingsLabel();
      settings.addEventListener("click", () => {
        if (readPreference() === "decline") {
          savePreference("allow");
          startAnalytics();
        } else {
          savePreference("decline");
          stopAnalytics();
        }
        updateSettingsLabel();
      });
    }
    document.addEventListener("click", event => {
      const anchor = event.target.closest("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (/^https:\/\/buy\.stripe\.com\//.test(href)) {
        const supportKey = anchor.dataset.supportLink;
        if (supportKey) {
          track("support_click", { support_tier: supportKey });
        } else {
          const card = anchor.closest(".piece");
          track("stripe_click", { artwork_title: card?.querySelector("h3")?.textContent.trim() || "Print" });
        }
      } else if (/^#(prints|support|commission|about|contact|studio-updates)$/.test(href)) {
        track("section_click", { section_id: href.slice(1) });
      }
    });
  }

  if (!form || !status || typeof window.fetch !== "function") return;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = form.querySelector("button[type=submit]");
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = "Sending…";
    status.textContent = "";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(form.action, {
        method: "POST", body: new FormData(form), headers: { Accept: "application/json" }, signal: controller.signal
      });
      if (!response.ok) {
        if (response.status === 429) throw new Error("Please wait a few minutes and try again.");
        throw new Error("Your signup could not be saved. Please try again, or use the contact form below.");
      }
      status.textContent = "Thank you—your signup request has been received.";
      track("generate_lead", { lead_type: "studio_signup" });
      form.reset();
    } catch (error) {
      status.textContent = error.name === "AbortError" || error instanceof TypeError
        ? "We couldn't confirm your signup. Please try again when your connection is available."
        : error.message;
    } finally {
      clearTimeout(timeout);
      button.disabled = false;
      button.textContent = "Join Studio Updates";
    }
  });
})();
