// Parenty website analytics (Google Tag Manager GTM-TK4KS8P7 + Google Consent Mode v2)
// Runs synchronously in <head> before gtm.js so default consent is always registered first.
(function () {
    var CONSENT_KEY = "analytics_consent";
    var EEA_UK_CH = [
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
        "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL",
        "PT", "RO", "SK", "SI", "ES", "SE", "GB", "CH"
    ];

    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () {
        window.dataLayer.push(arguments);
    };

    var saved = null;
    try {
        saved = localStorage.getItem(CONSENT_KEY);
    } catch (e) {}

    function consentPayload(status) {
        return {
            analytics_storage: status,
            ad_storage: status,
            ad_user_data: status,
            ad_personalization: status
        };
    }

    // Privacy-protective by default in EEA/UK/CH; outside those regions granted unless declined.
    if (saved === "granted") {
        window.gtag("consent", "default", consentPayload("granted"));
    } else if (saved === "denied") {
        window.gtag("consent", "default", consentPayload("denied"));
    } else {
        var eeaDefault = consentPayload("denied");
        eeaDefault.region = EEA_UK_CH;
        eeaDefault.wait_for_update = 500;
        window.gtag("consent", "default", eeaDefault);
        window.gtag("consent", "default", consentPayload("granted"));
    }

    window.gtag("js", new Date());
    window.dataLayer.push({ "gtm.start": new Date().getTime(), event: "gtm.js" });

    function setConsent(value) {
        try {
            localStorage.setItem(CONSENT_KEY, value);
        } catch (e) {}
        var status = value === "granted" ? "granted" : "denied";
        window.gtag("consent", "update", consentPayload(status));
        window.dataLayer.push({
            event: "consent_updated",
            analytics_consent: status
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var banner = document.getElementById("cookieBanner");
        var acceptBtn = document.getElementById("cookieAccept");
        var declineBtn = document.getElementById("cookieDecline");

        if (banner) {
            if (saved !== "granted" && saved !== "denied") {
                banner.hidden = false;
            }
            if (acceptBtn) {
                acceptBtn.addEventListener("click", function () {
                    setConsent("granted");
                    banner.hidden = true;
                });
            }
            if (declineBtn) {
                declineBtn.addEventListener("click", function () {
                    setConsent("denied");
                    banner.hidden = true;
                });
            }
            document.querySelectorAll("[data-cookie-settings]").forEach(function (trigger) {
                trigger.addEventListener("click", function () {
                    banner.hidden = false;
                    if (declineBtn) declineBtn.focus();
                });
            });
        }

        // Push clean GTM Data Layer events for App Store / Google Play clicks and audience switches
        var pageLang = document.documentElement.lang || "en";
        document.addEventListener("click", function (event) {
            var link = event.target && event.target.closest ? event.target.closest("a[href]") : null;
            if (link) {
                var href = link.getAttribute("href") || "";
                var store = null;
                if (href.indexOf("apps.apple.com") !== -1) store = "app_store";
                else if (href.indexOf("play.google.com") !== -1) store = "google_play";
                if (store) {
                    var section = link.closest("section, nav, header, footer");
                    var placement = (section && (section.id || section.className.split(" ")[0])) || "page";
                    window.dataLayer.push({
                        event: "store_click",
                        store: store,
                        page_lang: pageLang,
                        placement: placement
                    });
                }
            }

            var audBtn = event.target && event.target.closest ? event.target.closest(".mode-switch [data-audience], .audience-switch [data-audience]") : null;
            if (audBtn && audBtn.getAttribute("aria-current") !== "page") {
                window.dataLayer.push({
                    event: "audience_switch",
                    audience: audBtn.dataset.audience || "",
                    page_lang: pageLang
                });
            }
        });
    });
})();
