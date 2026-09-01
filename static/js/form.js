(function () {
  'use strict';

  if (!window.KILLFEED_DATA) return;

  var CDN = 'https://cdn.statically.io/gh/mr-velosofy/FastAPI_KillfeedGenerator@main/assets/';
  var AGENT_ICON_FIX = { 'KAYO': 'Kayo', 'Iso': 'ISO' };
  var weaponsList = window.KILLFEED_DATA.weapons || [];
  var abilitiesList = window.KILLFEED_DATA.abilities || [];
  var specialList = window.KILLFEED_DATA.special || [];
  var allTabs = { weapons: weaponsList, abilities: abilitiesList, special: specialList };
  var activeTab = "weapons";

  function weaponImgSrc(val) {
    return val ? CDN + encodeURI(String(val).replace(/\\/g, '/')) : '';
  }

  function agentIconSrc(val) {
    if (!val) return '';
    return CDN + 'agents-icon/' + encodeURI(AGENT_ICON_FIX[val] || val) + '.png';
  }

  function displayName(path) {
    var name = path.split(/[/\\]/).pop();
    return name.replace(/\.png$/i, "").replace(/_/g, " ");
  }

  function detectTab(path) {
    if (/(^|[/\\])weapons[/\\]/.test(path)) return "weapons";
    if (/(^|[/\\])abilities[/\\]/.test(path)) return "abilities";
    if (/(^|[/\\])special[/\\]/.test(path)) return "special";
    return "weapons";
  }

  // ── Custom Dropdown ──────────────────────────────────────────

  function buildCustomDropdown(selectEl) {
    var wrapper = selectEl.parentElement.querySelector('.cdrop');
    if (!wrapper) return;
    var isWeapon = selectEl.id === 'weapon-select';
    var getImgSrc, getText;

    if (isWeapon) {
      getImgSrc = weaponImgSrc;
      getText = function (val) { return val ? displayName(val) : ''; };
    } else {
      getImgSrc = agentIconSrc;
      getText = function (val) { return val || ''; };
    }

    function renderTrigger(selectedVal) {
      var imgSrc = getImgSrc(selectedVal);
      var text = getText(selectedVal);
      wrapper.innerHTML =
        '<div class="cdrop-trigger" tabindex="0">' +
          (imgSrc ? '<img class="cdrop-img" src="' + imgSrc + '" alt="">' : '<span class="cdrop-img cdrop-img-placeholder"></span>') +
          '<span class="cdrop-text">' + text + '</span>' +
          '<span class="cdrop-arrow"></span>' +
        '</div>';
      wrapper.querySelector('.cdrop-trigger').addEventListener('click', function (e) {
        e.stopPropagation();
        toggleMenu(selectEl);
      });
      wrapper.querySelector('.cdrop-trigger').addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          closeAllDropdowns();
          return;
        }
        if (e.key === 'Enter') {
          e.preventDefault();
          var menu = wrapper.querySelector('.cdrop-menu');
          if (menu) {
            var hl = menu.querySelector('.cdrop-opt-highlight');
            if (hl) { hl.click(); }
          } else {
            toggleMenu(selectEl);
          }
          return;
        }
        if (e.key.length === 1 && e.key >= 'a' && e.key <= 'z') {
          e.preventDefault();
          var menu = wrapper.querySelector('.cdrop-menu');
          if (!menu) toggleMenu(selectEl);
          menu = wrapper.querySelector('.cdrop-menu');
          if (!menu) return;
          var letter = e.key.toLowerCase();
          // clear previous highlight
          menu.querySelectorAll('.cdrop-opt-highlight').forEach(function (o) { o.classList.remove('cdrop-opt-highlight'); });
          var opts = menu.querySelectorAll('.cdrop-opt');
          // determine start index based on repeated letter
          var startIdx = 0;
          if (wrapper._lastLetter === letter && wrapper._lastMatchIdx >= 0) {
            startIdx = wrapper._lastMatchIdx + 1;
          }
          var matchIdx = -1;
          for (var i = startIdx; i < opts.length; i++) {
            var txt = opts[i].textContent.trim().toLowerCase();
            if (txt.charAt(0) === letter) {
              matchIdx = i;
              break;
            }
          }
          // wrap around if no match from startIdx
          if (matchIdx === -1) {
            for (var i = 0; i < startIdx; i++) {
              var txt = opts[i].textContent.trim().toLowerCase();
              if (txt.charAt(0) === letter) {
                matchIdx = i;
                break;
              }
            }
          }
          if (matchIdx !== -1) {
            opts[matchIdx].classList.add('cdrop-opt-highlight');
            opts[matchIdx].scrollIntoView({ block: 'nearest' });
            wrapper._lastLetter = letter;
            wrapper._lastMatchIdx = matchIdx;
          } else {
            wrapper._lastLetter = letter;
            wrapper._lastMatchIdx = -1;
          }
        }
      });
    }

    function renderMenu(selectedVal, filterTab) {
      var existing = wrapper.querySelector('.cdrop-menu');
      if (existing) existing.remove();

      var menu = document.createElement('div');
      menu.className = 'cdrop-menu';
      var items = [];

      if (isWeapon) {
        var list = allTabs[filterTab || activeTab] || [];
        list.forEach(function (item) {
          items.push({ value: item, img: getImgSrc(item), text: getText(item) });
        });
      } else {
        var options = selectEl.querySelectorAll('option');
        options.forEach(function (opt) {
          items.push({ value: opt.value, img: getImgSrc(opt.value), text: getText(opt.value) });
        });
      }

      if (items.length === 0) {
        var empty = document.createElement('div');
        empty.className = 'cdrop-empty';
        empty.textContent = 'No items';
        menu.appendChild(empty);
        wrapper.appendChild(menu);
        return;
      }

      items.forEach(function (item) {
        var opt = document.createElement('div');
        opt.className = 'cdrop-opt' + (item.value === selectedVal ? ' selected' : '');
        opt.setAttribute('data-value', item.value);
        opt.innerHTML =
          (item.img ? '<img class="cdrop-opt-img" src="' + item.img + '" alt="">' : '<span class="cdrop-opt-img cdrop-opt-img-placeholder"></span>') +
          '<span>' + item.text + '</span>';
        opt.addEventListener('click', function (e) {
          e.stopPropagation();
          selectVal(selectEl, item.value);
          closeAllDropdowns();
        });
        menu.appendChild(opt);
      });
      wrapper.appendChild(menu);
    }

    function selectVal(sel, val) {
      sel.value = val;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      renderTrigger(val);
      rebuildWeaponOptionsOnTab(); // refresh menu for next open
    }

    function toggleMenu(sel) {
      var menu = wrapper.querySelector('.cdrop-menu');
      if (menu) {
        menu.remove();
        return;
      }
      closeAllDropdowns();
      var val = sel.value;
      var tab = isWeapon ? activeTab : null;
      renderMenu(val, tab);
      menu = wrapper.querySelector('.cdrop-menu');
      if (menu) {
        menu.style.display = 'block';
      }
    }

    // build initial trigger
    renderTrigger(selectEl.value);

    // store rebuild function on wrapper for tab changes
    wrapper._rebuild = function () {
      renderTrigger(selectEl.value);
      var menu = wrapper.querySelector('.cdrop-menu');
      if (menu) {
        var tab = isWeapon ? activeTab : null;
        renderMenu(selectEl.value, tab);
      }
    };

    return wrapper;
  }

  function closeAllDropdowns() {
    document.querySelectorAll('.cdrop-menu').forEach(function (m) { m.remove(); });
  }

  document.addEventListener('click', function () {
    closeAllDropdowns();
  });

  // ── Init Custom Dropdowns ────────────────────────────────────

  function initAllDropdowns() {
    buildCustomDropdown(document.getElementById('killer_agent'));
    buildCustomDropdown(document.getElementById('victim_agent'));
    buildCustomDropdown(document.getElementById('weapon-select'));
  }

  function rebuildWeaponOptionsOnTab() {
    var dd = document.querySelector('.cdrop[data-for="weapon"]');
    if (dd && dd._rebuild) dd._rebuild();
  }

  // ── Tab switching ────────────────────────────────────────────

  var tabButtons = document.querySelectorAll(".seg-btn");
  tabButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      tabButtons.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      activeTab = btn.getAttribute("data-tab");
      populateSelect(activeTab);
      refreshFormMode();
      rebuildWeaponOptionsOnTab();
      setTimeout(triggerPreview, 50);
    });
  });

  function populateSelect(tab) {
    var select = document.getElementById("weapon-select");
    select.innerHTML = "";
    var items = allTabs[tab] || [];
    items.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item;
      opt.textContent = displayName(item);
      select.appendChild(opt);
    });
    // keep first item selected if no value
    if (submittedWeapon && tab === detectTab(submittedWeapon)) {
      select.value = submittedWeapon;
    }
  }

  var submittedWeapon = window.KILLFEED_DATA.weapon || null;
  if (submittedWeapon) {
    activeTab = detectTab(submittedWeapon);
  }
  populateSelect(activeTab);
  tabButtons.forEach(function (b) {
    b.classList.toggle("active", b.getAttribute("data-tab") === activeTab);
  });
  if (submittedWeapon) {
    document.getElementById("weapon-select").value = submittedWeapon;
  }

  // ── Stepper ──────────────────────────────────────────────────

  var stepperValue = 0;
  var stepperDisplay = document.getElementById("stepper-value");
  var numeralInput = document.getElementById("numeral-input");

  function initStepper() {
    var val = numeralInput.value;
    if (val === "3") stepperValue = 3;
    else if (val === "4") stepperValue = 4;
    else if (val === "5") stepperValue = 5;
    else if (val === "6") stepperValue = 6;
    else if (val === "7") stepperValue = 7;
    else stepperValue = 0;
    updateStepper();
  }

  function updateStepper() {
    stepperDisplay.textContent = stepperValue;
    if (stepperValue >= 3 && stepperValue <= 7) {
      numeralInput.value = String(stepperValue);
    } else {
      numeralInput.value = "";
    }
  }

  document.getElementById("stepper-minus").addEventListener("click", function () {
    var allowed = [0, 3, 4, 5, 6, 7];
    var idx = allowed.indexOf(stepperValue);
    if (idx > 0) {
      stepperValue = allowed[idx - 1];
      updateStepper();
      triggerPreview();
    }
  });

  document.getElementById("stepper-plus").addEventListener("click", function (e) {
    e.stopPropagation();
    var allowed = [0, 3, 4, 5, 6, 7];
    var idx = allowed.indexOf(stepperValue);
    if (idx >= 0 && idx < allowed.length - 1) {
      stepperValue = allowed[idx + 1];
      updateStepper();
      triggerPreview();
    }
  });

  initStepper();

  // ── Revive mode ──────────────────────────────────────────────

  var REVIVE_VALUE = "special/Revive.png";
  var meSideInput = document.getElementById("me-side-input");
  var meLeftCheck = document.getElementById("me_left_check");
  var meRightCheck = document.getElementById("me_right_check");
  var meP1Box = document.getElementById("me-p1-toggle");
  var meP2Box = document.getElementById("me-p2-toggle");
  var meHighlightBox = document.getElementById("me-highlight-toggle");
  var suicideBox = document.getElementById("suicide-toggle");
  var prevRevState = isReviveMode();
  var revStash = null;

  function applyReviveDefaults() {
    if (!revStash) { // keep the pre-revive players so we can restore them on exit
      revStash = {
        kn: killerNameInput.value, ka: killerAgentSelect.value,
        vn: victimNameInput.value, va: victimAgentSelect.value
      };
    }
    var others = [];
    killerAgentSelect.querySelectorAll("option").forEach(function (o) {
      if (o.value !== "Sage") others.push(o.value);
    });
    var rand = others[Math.floor(Math.random() * others.length)] || "Reyna";
    killerAgentSelect.value = "Sage"; // the reviver
    killerNameInput.value = "Sage";
    victimAgentSelect.value = rand;   // the revived
    victimNameInput.value = rand;
    rebuildDropdownFor("killer_agent");
    rebuildDropdownFor("victim_agent");
  }

  function exitReviveRestore() {
    if (!revStash) return;
    killerNameInput.value = revStash.kn;
    killerAgentSelect.value = revStash.ka;
    victimNameInput.value = revStash.vn;
    victimAgentSelect.value = revStash.va;
    revStash = null;
    rebuildDropdownFor("killer_agent");
    rebuildDropdownFor("victim_agent");
  }
  var lastNonReviveWeapon = (function () { // eager: toggleSelfKill() may fire before handleReviveInit
    var cur = document.getElementById("weapon-select").value;
    return (cur && cur !== REVIVE_VALUE) ? cur : weaponsList[0];
  })();

  function isReviveMode() {
    return document.getElementById("weapon-select").value === REVIVE_VALUE;
  }

  function setWeapon(val) {
    activeTab = detectTab(val);
    tabButtons.forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-tab") === activeTab);
    });
    populateSelect(activeTab);
    document.getElementById("weapon-select").value = val;
    rebuildWeaponOptionsOnTab();
  }

  function syncMeSideInput() {
    var side = "";
    if (isReviveMode() && !enemyKillCheck.checked) {
      if (meLeftCheck.checked) side = "left";
      else if (meRightCheck.checked) side = "right";
    }
    meSideInput.value = side;
  }

  function refreshFormMode() {
    var rev = isReviveMode();
    var isSelf = selfKillCheck.checked;
    meHighlightBox.style.display = rev ? "none" : "";
    meP1Box.style.display = rev ? "flex" : "none";
    meP2Box.style.display = rev ? "flex" : "none";
    suicideBox.classList.toggle("is-disabled", rev); // suicide locked out inside revive
    document.getElementById("hs-toggle").style.display = (rev || isSelf) ? "none" : "";
    document.getElementById("wb-toggle").style.display = (rev || isSelf) ? "none" : "";
    document.getElementById("numeral-group").style.display = (rev || isSelf) ? "none" : "";
    document.getElementById("victim-group").style.display = isSelf ? "none" : "";
    document.getElementById("victim-agent-group").style.display = isSelf ? "none" : "";
    document.getElementById("switch-group").style.display = isSelf ? "none" : "";
    document.getElementById("killer-name-label").textContent = rev ? "REVIVER" : (isSelf ? "NAME" : "NICK(P1)");
    document.getElementById("killer-agent-label").textContent = rev ? "AGENT" : (isSelf ? "AGENT" : "AGENT(P1)");
    document.getElementById("victim-name-label").textContent = rev ? "REVIVED" : "NICK(P2)";
    document.getElementById("victim-agent-label").textContent = "AGENT";
    if (prevRevState && !rev) exitReviveRestore(); // leaving revive -> put pre-revive players back
    prevRevState = rev;
    syncMeSideInput();
  }

  [meLeftCheck, meRightCheck].forEach(function (chk) {
    chk.addEventListener("change", function () {
      if (chk.checked) {
        (chk === meLeftCheck ? meRightCheck : meLeftCheck).checked = false;
      }
      syncMeSideInput();
    });
  });

  document.getElementById("is_enemy_kill").addEventListener("change", function () {
    if (!isReviveMode()) return;
    var off = enemyKillCheck.checked; // enemy revive: ME can never be you
    meP1Box.classList.toggle("is-disabled", off);
    meP2Box.classList.toggle("is-disabled", off);
    if (off) {
      meLeftCheck.checked = false;
      meRightCheck.checked = false;
    }
    syncMeSideInput();
  });

  document.getElementById("weapon-select").addEventListener("change", function () {
    if (this.value === REVIVE_VALUE) {
      if (selfKillCheck.checked) {
        selfKillCheck.checked = false;
        toggleSelfKill(); // revive and suicide are exclusive
      }
      applyReviveDefaults(); // Sage / random on entry
    } else {
      lastNonReviveWeapon = this.value;
    }
    refreshFormMode();
  });

  function handleReviveInit() {
    var cur = document.getElementById("weapon-select").value;
    lastNonReviveWeapon = (cur && cur !== REVIVE_VALUE) ? cur : weaponsList[0];
    var side = meSideInput.value; // restore submitted ME side
    if (side === "left") meLeftCheck.checked = true;
    else if (side === "right") meRightCheck.checked = true;
    if (isReviveMode() && enemyKillCheck.checked) {
      meP1Box.classList.add("is-disabled");
      meP2Box.classList.add("is-disabled");
    }
    refreshFormMode();
  }

  // ── Self-kill toggle ─────────────────────────────────────────

  var selfKillCheck = document.getElementById("is_self_kill");
  var killerNameInput = document.getElementById("killer_name");
  var victimNameInput = document.getElementById("victim_name");
  var killerAgentSelect = document.getElementById("killer_agent");
  var victimAgentSelect = document.getElementById("victim_agent");
  var enemyKillCheck = document.getElementById("is_enemy_kill");

  var savedP2 = null; // P2 details stashed while Suicide mode rewrites them

  function toggleSelfKill() {
    if (selfKillCheck.checked && isReviveMode()) {
      setWeapon(lastNonReviveWeapon); // SUICIDE wins -> leave revive mode
    }
    var isSelf = selfKillCheck.checked;
    if (isSelf) {
      if (!killerNameInput.value) killerNameInput.value = "PLAYER";
      if (!savedP2) {
        savedP2 = { name: victimNameInput.value, agent: victimAgentSelect.value };
      }
      victimNameInput.value = killerNameInput.value;
      victimAgentSelect.value = killerAgentSelect.value;
      rebuildDropdownFor("victim_agent");
    } else if (savedP2) {
      victimNameInput.value = savedP2.name;
      victimAgentSelect.value = savedP2.agent;
      savedP2 = null;
      rebuildDropdownFor("victim_agent");
      triggerPreview();
    }
    refreshFormMode();
  }

  selfKillCheck.addEventListener("change", toggleSelfKill);
  killerNameInput.addEventListener("input", function () {
    if (selfKillCheck.checked) victimNameInput.value = this.value;
  });
  killerAgentSelect.addEventListener("change", function () {
    if (selfKillCheck.checked) victimAgentSelect.value = this.value;
  });

  toggleSelfKill();

  // ── P1/P2 switch ─────────────────────────────────────────────

  function rebuildDropdownFor(id) {
    var dd = document.querySelector('.cdrop[data-for="' + id + '"]');
    if (dd && dd._rebuild) dd._rebuild();
  }

  var swapBtn = document.getElementById("btn-swap");
  swapBtn.addEventListener("animationend", function () {
    this.classList.remove("is-swapping");
  });
  swapBtn.addEventListener("click", function () {
    if (selfKillCheck.checked) return; // both sides are the same player
    var kn = killerNameInput.value;
    var ka = killerAgentSelect.value;
    killerNameInput.value = victimNameInput.value;
    killerAgentSelect.value = victimAgentSelect.value;
    victimNameInput.value = kn;
    victimAgentSelect.value = ka;
    if (isReviveMode() && !enemyKillCheck.checked) { // "you" stays you across the swap
      if (meLeftCheck.checked) { meLeftCheck.checked = false; meRightCheck.checked = true; }
      else if (meRightCheck.checked) { meRightCheck.checked = false; meLeftCheck.checked = true; }
      syncMeSideInput();
    }
    rebuildDropdownFor("killer_agent");
    rebuildDropdownFor("victim_agent");
    triggerPreview();
    this.classList.remove("is-swapping");
    void this.offsetWidth; // restart animation on rapid clicks
    this.classList.add("is-swapping");
  });

  // ── Live preview ─────────────────────────────────────────────

  var previewImg = document.getElementById("preview-img");
  var debounceTimer;
  var lastPreviewKey = null;
  var pendingKey = null;

  function collectFormData() {
    var form = document.querySelector("form");
    var params = new URLSearchParams();
    [].slice.call(form.querySelectorAll("input, select")).forEach(function (el) {
      if (el.type === "checkbox") {
        if (el.checked) params.append(el.name, "true");
      } else if (el.name) {
        params.append(el.name, el.value);
      }
    });
    return params;
  }

  function triggerPreview() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      var key = collectFormData().toString();
      if (key === lastPreviewKey) return; // nothing changed -> skip regeneration
      pendingKey = key;
      previewImg.src = "/api/preview?" + key;
    }, 800); // longer debounce: one render per pause in typing
  }

  previewImg.addEventListener("load", function () {
    if (pendingKey !== null) { lastPreviewKey = pendingKey; pendingKey = null; }
    previewImg.classList.add("is-loaded");
    dismissSkeleton();
  });
  previewImg.addEventListener("error", function () {
    pendingKey = null; // allow retry on failure
  });

  // ── Skeleton loading state ───────────────────────────────────
  // Covers the page until the first preview arrives (or ~2s max)
  var skeleton = document.getElementById("page-skeleton");
  function dismissSkeleton() {
    if (!skeleton || skeleton.classList.contains("is-done")) return;
    skeleton.classList.add("is-done");
    setTimeout(function () {
      if (skeleton.parentNode) skeleton.parentNode.removeChild(skeleton);
      skeleton = null;
    }, 450);
  }
  setTimeout(dismissSkeleton, 2200);
  // Cached render (e.g. post-submit): load event already fired
  if (previewImg.complete && previewImg.naturalWidth > 0) {
    previewImg.classList.add("is-loaded");
    dismissSkeleton();
  }

  document.querySelectorAll("input, select").forEach(function (el) {
    el.addEventListener("input", triggerPreview);
    el.addEventListener("change", triggerPreview);
  });

  // ── Download ─────────────────────────────────────────────────

  function downloadPreview() {
    var params = collectFormData();
    var url = "/api/preview?" + params.toString() + "&t=" + Date.now() + "&download=true";
    var a = document.createElement('a');
    a.href = url;
    a.download = 'killfeed.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  var exportBtn = document.querySelector(".btn-export");
  if (exportBtn) exportBtn.addEventListener("click", downloadPreview);

  document.querySelector("form").addEventListener("submit", function (e) {
    e.preventDefault();
  });

  // ── Init ─────────────────────────────────────────────────────

  // First-load prefill: default nicknames to the selected agents
  (function prefillNames() {
    var k = document.getElementById("killer_name");
    var v = document.getElementById("victim_name");
    if (!k.value && !v.value && !submittedWeapon) {
      k.value = document.getElementById("killer_agent").value;
      v.value = document.getElementById("victim_agent").value;
    }
    k.dataset.auto = "1";
    v.dataset.auto = "1";
  })();

  // Track agent→nick sync: update nick only if it was auto-set
  (function initAgentNickSync() {
    var lastKillerAgent = killerAgentSelect.value;
    var lastVictimAgent = victimAgentSelect.value;

    // any manual edit clears the auto flag
    killerNameInput.addEventListener("input", function () { delete killerNameInput.dataset.auto; });
    victimNameInput.addEventListener("input", function () { delete victimNameInput.dataset.auto; });

    killerAgentSelect.addEventListener("change", function () {
      if (killerNameInput.dataset.auto) {
        killerNameInput.value = this.value;
      }
      lastKillerAgent = this.value;
    });
    victimAgentSelect.addEventListener("change", function () {
      if (victimNameInput.dataset.auto) {
        victimNameInput.value = this.value;
      }
      lastVictimAgent = this.value;
    });
  })();

  initAllDropdowns();
  handleReviveInit();

  // ── Live stats: fade between online / feeds ───────────────────
  var lsInner = document.getElementById("ls-inner");
  if (lsInner) {
  var lsOnline = 0, lsToday = 0, lsShowOnline = true;

  function lsLabel() {
    return lsShowOnline
      ? lsOnline + " Online"
      : lsToday + " Feeds (24h)";
  }

  function lsCycle() {
    lsInner.style.opacity = "0";
    setTimeout(function () {
      lsShowOnline = !lsShowOnline;
      lsInner.textContent = lsLabel();
      lsInner.style.opacity = "1";
    }, 400);
  }

  setInterval(lsCycle, 4000);
  lsInner.textContent = lsLabel();

  function refreshLiveStats() {
    fetch("/api/stats/public", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) return;
        lsOnline = s.online || 0;
        lsToday = s.today || 0;
      })
      .catch(function () {});
    setTimeout(refreshLiveStats, 60000);
  }
  refreshLiveStats();
  }

  // Preload all selector artwork from the CDN so dropdowns open instantly
  (function preloadAssets() {
    var seen = {};
    function add(url) {
      if (!url || seen[url]) return;
      seen[url] = 1;
      var im = new Image();
      im.src = url;
    }
    document.querySelectorAll('#killer_agent option').forEach(function (o) {
      add(agentIconSrc(o.value));
    });
    weaponsList.concat(abilitiesList).concat(specialList).forEach(function (item) {
      add(weaponImgSrc(item));
    });
  })();

  setTimeout(triggerPreview, 100);
})();