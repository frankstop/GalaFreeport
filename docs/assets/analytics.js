(() => {
  "use strict";

  const measurementId = "G-RSVR6Y389R";
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {
    window.dataLayer.push(arguments);
  };

  const tag = document.createElement("script");
  tag.async = true;
  tag.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
  document.head.appendChild(tag);

  window.gtag("js", new Date());
  window.gtag("config", measurementId, {
    page_title: document.title,
    page_path: window.location.pathname,
    page_location: window.location.origin + window.location.pathname,
    traffic_context: window.self === window.top ? "direct" : "embedded",
  });
})();
