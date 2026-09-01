(function () {
  'use strict';

  if (!window.gsap || !document.getElementById('coffee-dollar')) return;

  gsap.registerPlugin(MorphSVGPlugin);
  gsap.to("#coffee-dollar", {
    duration: 1.5,
    morphSVG: { shape: "#coffee-cup" },
    ease: "power2.inOut",
    repeat: -1,
    yoyo: true,
    repeatDelay: 3
  });
})();