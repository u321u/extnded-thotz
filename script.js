/* Extnded Thotz — Matrix edition interaction layer
   Digital-rain canvas + scroll condense + reveal observer.       */
(function () {
  "use strict";

  document.documentElement.classList.remove("no-js");

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- reveal ---------- */
  var revealItems = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && !reduced) {
    var observer = new IntersectionObserver(
      function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) {
            entries[i].target.classList.add("is-visible");
            observer.unobserve(entries[i].target);
          }
        }
      },
      { threshold: 0.16, rootMargin: "0px 0px -80px 0px" }
    );
    revealItems.forEach(function (item) { observer.observe(item); });
    window.__revealReady = true;
  } else {
    revealItems.forEach(function (item) { item.classList.add("is-visible"); });
    window.__revealReady = true;
  }

  /* ---------- topbar scroll condense ---------- */
  var topbar = document.querySelector(".topbar");
  if (topbar && !reduced) {
    var onScroll = function () {
      topbar.classList.toggle("scrolled", window.scrollY > 8);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- digital rain ---------- */
  var canvas = document.getElementById("rain");
  if (!canvas || canvas.getContext === undefined || reduced) return;

  var ctx = canvas.getContext("2d");
  var GLYPHS = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン0123456789";
  var FONT_SIZE = 15;
  var columns = [];
  var colWidth = 0;
  var colCount = 0;
  var vw = 0;
  var vh = 0;
  var MAX_TRAIL = 9;

  // Tail colours are precomputed: building "rgba(...)" per glyph per frame
  // allocates a few thousand strings a second for no visual gain.
  var TRAIL_COLOR = [];
  for (var t = 1; t <= MAX_TRAIL; t++) {
    TRAIL_COLOR[t] = [];
    for (var k = 0; k < t; k++) {
      TRAIL_COLOR[t][k] = "rgba(53, 224, 122, " + ((1 - k / t) * 0.5).toFixed(3) + ")";
    }
  }

  function randGlyph() {
    return Math.floor(Math.random() * GLYPHS.length);
  }

  function resize() {
    // cap the pixel ratio: retina density buys nothing here and doubles the fill cost
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    vw = window.innerWidth;
    vh = window.innerHeight;
    canvas.width = Math.floor(vw * dpr);
    canvas.height = Math.floor(vh * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    colWidth = FONT_SIZE;
    colCount = Math.ceil(vw / colWidth);
    columns = [];
    for (var i = 0; i < colCount; i++) {
      columns[i] = {
        y: -Math.random() * 40,
        speed: 0.35 + Math.random() * 0.8,
        glyph: randGlyph(),
        trail: 3 + Math.floor(Math.random() * MAX_TRAIL)
      };
    }
  }

  var lastTick = 0;
  var FRAME_MS = 55; // ~18fps: authentic pace, easy on the GPU

  function tick(ts) {
    window.__rainRaf = requestAnimationFrame(tick);
    if (document.hidden) return;
    if (ts - lastTick < FRAME_MS) return;
    lastTick = ts;

    // trail fade — short enough to keep ghosts, long enough to read as rain
    ctx.fillStyle = "rgba(2, 6, 4, 0.2)";
    ctx.fillRect(0, 0, vw, vh);
    ctx.font = FONT_SIZE + "px 'IBM Plex Mono', monospace";
    ctx.textBaseline = "top";

    for (var i = 0; i < colCount; i++) {
      var col = columns[i];
      col.y += col.speed;
      if (col.speed >= 1) col.y += col.speed - 1;

      var headY = col.y * FONT_SIZE;
      if (headY > vh + 120) {
        col.y = -Math.random() * 30;
        col.speed = 0.35 + Math.random() * 0.8;
        col.glyph = randGlyph();
        col.trail = 3 + Math.floor(Math.random() * MAX_TRAIL);
        continue;
      }
      if (headY < -FONT_SIZE) continue;

      // tail: dimmer glyphs trailing above the head
      for (var k = 1; k < col.trail; k++) {
        var ty = headY - k * FONT_SIZE;
        if (ty < -FONT_SIZE || ty > vh) continue;
        ctx.fillStyle = TRAIL_COLOR[col.trail][k];
        ctx.fillText(GLYPHS[(col.glyph + k * 3) % GLYPHS.length], i * colWidth, ty);
      }

      // head: brightest, with bloom
      ctx.fillStyle = "rgba(160, 255, 195, 0.92)";
      ctx.shadowColor = "rgba(53, 224, 122, 0.85)";
      ctx.shadowBlur = 9;
      ctx.fillText(GLYPHS[col.glyph], i * colWidth, headY);
      ctx.shadowBlur = 0;

      // slow glyph mutation so columns never repeat
      if (Math.random() < 0.06) col.glyph = randGlyph();
    }

    // rare signal glitch: stray glyphs flare across the field
    if (Math.random() < 0.035) {
      for (var g = 0; g < 5; g++) {
        ctx.fillStyle = "rgba(138, 255, 180, 0.45)";
        ctx.fillText(
          GLYPHS[randGlyph()],
          Math.floor(Math.random() * colCount) * colWidth,
          Math.random() * vh
        );
      }
    }
  }

  resize();
  window.addEventListener("resize", resize);
  window.__rainRaf = requestAnimationFrame(tick);

  /* ---------- live dictation console ---------- */
  var body = document.getElementById("console-body");
  var state = document.getElementById("console-state");
  if (body && state && !reduced) {
    var SCENES = [
      {
        say: "um so basically could you uh send the invoice to maria before friday",
        typed: "Could you send the invoice to Maria before Friday?",
      },
      {
        say: "yeah i think the uh the overlay looks good ship it",
        typed: "Yeah — the overlay looks good. Ship it.",
      },
      {
        say: "quick note for standup um finished the rain effect today",
        typed: "Standup note: finished the rain effect today.",
      },
    ];

    var mk = function (cls, txt) {
      var p = document.createElement("p");
      if (cls) p.className = cls;
      if (txt) p.textContent = txt;
      body.appendChild(p);
      return p;
    };

    var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
    var busy = false;

    var runScene = function (scene) {
      body.textContent = "";
      mk("dim", "> hold ctrl + windows");
      state.textContent = "_listening";
      state.classList.add("hot");
      var listen = mk("listen");
      listen.textContent = "> listening";
      var wave = document.createElement("span");
      wave.className = "wave";
      wave.setAttribute("aria-hidden", "true");
      for (var w = 0; w < 6; w++) wave.appendChild(document.createElement("i"));
      listen.appendChild(wave);
      return wait(1900).then(function () {
        wave.remove();
        state.textContent = "_transcribing";
        state.classList.remove("hot");
        mk("dim", "> raw: " + scene.say);
        return wait(900);
      }).then(function () {
        state.textContent = "_injecting";
        var out = mk(null, "> ");
        var span = document.createElement("span");
        out.appendChild(span);
        var caret = document.createElement("span");
        caret.className = "caret";
        caret.setAttribute("aria-hidden", "true");
        out.appendChild(caret);
        var i = 0;
        return new Promise(function (done) {
          var step = function () {
            if (i < scene.typed.length) {
              span.textContent = scene.typed.slice(0, ++i);
              window.setTimeout(step, 22 + Math.random() * 24);
            } else {
              caret.remove();
              done();
            }
          };
          step();
        });
      }).then(function () {
        state.textContent = "_idle";
        return wait(2400);
      });
    };

    var loop = function () {
      if (busy) return;
      busy = true;
      var idx = Math.floor(Math.random() * SCENES.length);
      runScene(SCENES[idx]).then(function () {
        busy = false;
      });
    };

    // start when the console scrolls into view
    if ("IntersectionObserver" in window) {
      var seen = false;
      new IntersectionObserver(function (entries, obs) {
        if (!seen && entries[0].isIntersecting) {
          seen = true;
          loop();
          window.setInterval(loop, 200);
          obs.disconnect();
        }
      }, { threshold: 0.3 }).observe(document.getElementById("console"));
    } else {
      loop();
      window.setInterval(loop, 200);
    }
  }
})();
