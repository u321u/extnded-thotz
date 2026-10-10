/* Extnded Thotz — Matrix edition interaction layer
   Digital-rain canvas + scroll condense + reveal observer.       */
(function () {
  "use strict";

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

  function resize() {
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    colWidth = FONT_SIZE;
    colCount = Math.ceil(window.innerWidth / colWidth);
    columns = [];
    for (var i = 0; i < colCount; i++) {
      columns[i] = {
        y: Math.floor((Math.random() * -40) * 1),
        speed: 0.4 + Math.random() * 0.7,
        glyphIdx: Math.floor(Math.random() * GLYPHS.length)
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

    // trail fade
    ctx.fillStyle = "rgba(2, 6, 4, 0.22)";
    ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);
    ctx.font = FONT_SIZE + "px 'IBM Plex Mono', monospace";

    for (var i = 0; i < colCount; i++) {
      var col = columns[i];
      col.y += col.speed;
      if (col.speed >= 1) col.y += col.speed - 1;
      if (col.y * FONT_SIZE > window.innerHeight + 120) {
        col.y = Math.floor((Math.random() * -30) * 1);
        col.speed = 0.4 + Math.random() * 0.7;
        col.glyphIdx = Math.floor(Math.random() * GLYPHS.length);
      }
      var y = col.y * FONT_SIZE;
      if (y > 0) {
        // head glyph: brightest
        var ch = GLYPHS[col.glyphIdx];
        ctx.fillStyle = "rgba(138, 255, 180, 0.9)";
        ctx.shadowColor = "rgba(53, 224, 122, 0.8)";
        ctx.shadowBlur = 8;
        ctx.fillText(ch, i * colWidth, y);
        ctx.shadowBlur = 0;

        // occasional tail glyph: dimmer
        if (Math.random() < 0.5) {
          var tail = GLYPHS[(col.glyphIdx + 7) % GLYPHS.length];
          ctx.fillStyle = "rgba(53, 224, 122, 0.35)";
          ctx.fillText(tail, i * colWidth, y - FONT_SIZE);
        }
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
        var out = mk("gold", "> ");
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
              window.setTimeout(step, 24 + Math.random() * 30);
            } else {
              caret.remove();
              done();
            }
          };
          step();
        });
      }).then(function () {
        state.textContent = "_idle";
        return wait(2600);
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
