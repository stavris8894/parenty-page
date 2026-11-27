// Parenty website analytics (GA4 G-4KM30V8DE0 + Google Consent Mode v2)
// Runs synchronously in <head> before gtag/js so default consent is always set first.
(function () {
    var MEASUREMENT_ID = "G-4KM30V8DE0";
    var CONSENT_KEY = "analytics_consent";

    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () {
        window.dataLayer.push(arguments);
    };

    var saved = null;
    try {
        saved = localStorage.getItem(CONSENT_KEY);
    } catch (e) {}

    window.gtag("consent", "default", {
        analytics_storage: saved === "granted" ? "granted" : "denied",
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        wait_for_update: 500
    });

    window.gtag("js", new Date());
    window.gtag("config", MEASUREMENT_ID);

    function setConsent(value) {
        try {
            localStorage.setItem(CONSENT_KEY, value);
        } catch (e) {}
        window.gtag("consent", "update", {
            analytics_storage: value === "granted" ? "granted" : "denied",
            ad_storage: "denied",
            ad_user_data: "denied",
            ad_personalization: "denied"
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

        // Track App Store / Google Play clicks and audience switches
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
                    window.gtag("event", "store_click", {
                        store: store,
                        page_lang: pageLang,
                        placement: placement
                    });
                }
            }

            var audBtn = event.target && event.target.closest ? event.target.closest(".audience-switch button[data-audience]") : null;
            if (audBtn) {
                window.gtag("event", "audience_switch", {
                    audience: audBtn.dataset.audience || "",
                    page_lang: pageLang
                });
            }
        });
    });
})();
