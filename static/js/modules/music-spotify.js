// ===== Module: music-spotify =====
// "Spotify" theme renderer for the music player. music.js owns data, playback,
// routing and the theme switch; this file only builds the Spotify-style markup
// (sidebar library, home shelves, entity pages, search, queue) and handles its
// few extra click actions. Styles live in app.css under .wm[data-mzt="spotify"].

var mzSp = (function () {
  var SP = {};
  var libFilter = '', libSort = 'recent', tintCache = {};
  var slots = {};                                                // 'playlistId|songId' -> the position a removed song had, so re-adding puts it back there
  var edit = null;                                               // playlist edit mode: { pid, draft: [ids], base: n, saving }
  var ME = 'raj';

  function esc(s) { return escapeHtml(s); }
  function dateStr(sec) { return sec ? new Date(sec * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''; }
  function plural(n, w) { return n.toLocaleString() + ' ' + w + (n === 1 ? '' : 's'); }
  function fitSize(title) { var n = title.length; return n <= 11 ? 96 : n <= 18 ? 72 : n <= 28 ? 48 : 32; }

  var I = {
    home: '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12.5 3.247a1 1 0 0 0-1 0L4 7.577V20h4.5v-6a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v6H20V7.577l-7.5-4.33zm-2-1.732a3 3 0 0 1 3 0l7.5 4.33a2 2 0 0 1 1 1.732V21a1 1 0 0 1-1 1h-6.5a1 1 0 0 1-1-1v-6h-3v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.577a2 2 0 0 1 1-1.732l7.5-4.33z"/></svg>',
    search: '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M10.533 1.27893C5.35215 1.27893 1.12598 5.41887 1.12598 10.5579C1.12598 15.697 5.35215 19.8369 10.533 19.8369C12.767 19.8369 14.8235 19.0671 16.4402 17.7794L20.7929 22.132C21.1834 22.5226 21.8166 22.5226 22.2071 22.132C22.5976 21.7415 22.5976 21.1083 22.2071 20.7178L17.8634 16.3741C19.1616 14.7849 19.94 12.7634 19.94 10.5579C19.94 5.41887 15.7138 1.27893 10.533 1.27893ZM3.12598 10.5579C3.12598 6.55226 6.42768 3.27893 10.533 3.27893C14.6383 3.27893 17.94 6.55226 17.94 10.5579C17.94 14.5636 14.6383 17.8369 10.533 17.8369C6.42768 17.8369 3.12598 14.5636 3.12598 10.5579Z"/></svg>',
    lib: '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M3 22a1 1 0 0 1-1-1V3a1 1 0 0 1 2 0v18a1 1 0 0 1-1 1zM15.5 2.134A1 1 0 0 0 14 3v18a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V6.464a1 1 0 0 0-.5-.866l-6-3.464zM9 2a1 1 0 0 0-1 1v18a1 1 0 1 0 2 0V3a1 1 0 0 0-1-1z"/></svg>',
    play: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M3 1.713a.7.7 0 0 1 1.05-.607l10.89 6.288a.7.7 0 0 1 0 1.212L4.05 14.894A.7.7 0 0 1 3 14.288V1.713z"/></svg>',
    clock: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8z"/><path d="M8 3.25a.75.75 0 0 1 .75.75v3.25H11a.75.75 0 0 1 0 1.5H7.25V4A.75.75 0 0 1 8 3.25z"/></svg>',
    shuffle: '<svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>',
    heartOff: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M1.69 2A4.582 4.582 0 0 1 8 2.023 4.583 4.583 0 0 1 11.88.817h.002a4.618 4.618 0 0 1 3.782 3.65v.003a4.543 4.543 0 0 1-1.011 3.84L9.35 14.629a1.765 1.765 0 0 1-2.093.464 1.762 1.762 0 0 1-.605-.463L1.348 8.309A4.582 4.582 0 0 1 1.689 2zm3.158.252A3.082 3.082 0 0 0 2.49 7.337l.005.005L7.8 13.664a.264.264 0 0 0 .311.069.262.262 0 0 0 .09-.069l5.312-6.33a3.043 3.043 0 0 0 .68-2.573 3.118 3.118 0 0 0-2.551-2.463 3.079 3.079 0 0 0-2.612.816l-.007.007a1.501 1.501 0 0 1-2.045 0l-.009-.008a3.082 3.082 0 0 0-2.121-.861z"/></svg>',
    heartOn: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M15.724 4.22A4.313 4.313 0 0 0 12.192.814a4.269 4.269 0 0 0-3.622 1.13.837.837 0 0 1-1.14 0 4.272 4.272 0 0 0-6.21 5.855l5.916 7.05a1.128 1.128 0 0 0 1.727 0l5.916-7.05a4.228 4.228 0 0 0 .945-3.577z"/></svg>',
    note: '<svg viewBox="0 0 24 24" width="40%" height="40%" fill="currentColor"><path d="M6 3h15v15.167a3.5 3.5 0 1 1-3.5-3.5H19V5H8v13.167a3.5 3.5 0 1 1-3.5-3.5H6V3z"/></svg>',
  };
  SP.heart = function (on) { return on ? I.heartOn : I.heartOff; };

  // ─── cover helpers ─────────────────────────────────────
  function cov(id, hue, letter, size, cls, inner) {
    var ch = esc(String(letter == null ? '' : letter).replace(/^[^A-Za-z0-9À-￿]+/, '').charAt(0).toUpperCase() || '♪');
    return '<div class="wm-art sp-art ' + (cls || '') + '" style="--h:' + hue + '">' + (inner || ch) +
      (id ? '<img draggable="false" loading="lazy" decoding="async" alt="" src="' + esc(mzCoverUrl(id, size)) + '" onerror="this.remove()">' : '') + '</div>';
  }
  function trackCov(t, size, cls) { return cov(t.c, t.h, t.al || t.t, size, cls); }
  function albumCredits(al) {
    var cnt = {}, order = [];
    al.tracks.forEach(function (t) { mzCredits(t).forEach(function (c) { if (!cnt[c.id]) { cnt[c.id] = { c: c, n: 0 }; order.push(c.id); } cnt[c.id].n++; }); });
    var main = order.map(function (id) { return cnt[id]; }).filter(function (x) { return x.n * 2 >= al.tracks.length; }).sort(function (x, y) { return y.n - x.n; }).map(function (x) { return x.c; }).slice(0, 3);
    return main.length ? main : mzCredits(al.first);
  }
  function albumCov(al, size, cls) { return cov(al.first.c, al.h, al.name, size, cls); }
  // The artist's own picture (Navidrome keeps one per artist), falling back to the first track's cover when there is none
  // saved photos/banners: tag their URLs with the file's change time, so a stale cached picture is never shown after a reload
  function loadArtOverrides() {
    fetch('/api/music/art/overrides').then(function (r) { return r.ok ? r.json() : {}; }).then(function (o) {
      var had = Object.keys(mz.artV || {}).length;
      mz.artV = Object.assign({}, o.v || {}, mz.artV || {});
      mz.artB = mz.artB || {}; (o.b || []).forEach(function (id) { mz.artB[id] = true; });
      if (!had && Object.keys(o.v || {}).length && mz.loaded && typeof mzRender === 'function') mzRender();
    }).catch(function () {});
  }
  loadArtOverrides();
  function artistImg(a, size, banner) { return mz.source === 'navidrome' ? '/api/music/artwork/' + mzEnc('ar-' + a.id) + '?size=' + size + (banner ? '&banner=1' : '') + (mz.artV && mz.artV[a.id] ? '&v=' + mz.artV[a.id] : '') : ''; }
  var EB = '<span class="sp-eb" title="Explicit">E</span>';
  var LIKED_TICK = '<svg viewBox="0 0 24 24" width="18" height="18" aria-label="Liked"><circle cx="12" cy="12" r="11" fill="#1ed760"/><polyline points="7 12.5 10.5 16 17 8.5" fill="none" stroke="#000" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var IMG_FALLBACK = "var f=this.dataset.fb;if(f&&this.getAttribute('src')!==f){this.src=f}else{this.remove()}";
  function artistCov(a, size, cls) {
    var first = a.tracks[0], img = artistImg(a, size);
    if (!img) return cov(first.c, mzHue(a.name), a.name, size, 'round ' + (cls || ''));
    var ch = esc(String(a.name || '').replace(/^[^A-Za-z0-9À-￿]+/, '').charAt(0).toUpperCase() || '♪');
    return '<div class="wm-art sp-art round ' + (cls || '') + '" style="--h:' + mzHue(a.name) + '">' + ch +
      '<img draggable="false" loading="lazy" decoding="async" alt="" src="' + esc(img) + '"' + (first.c ? ' data-fb="' + esc(mzCoverUrl(first.c, size)) + '"' : '') + ' onerror="' + IMG_FALLBACK + '"></div>';
  }
  function likedCov(cls) { return '<div class="wm-art sp-art sp-liked ' + (cls || '') + '">' + I.heartOn.replace('width="16" height="16"', 'width="45%" height="45%"') + '</div>'; }
  function songsCov(cls) { return '<div class="wm-art sp-art sp-allsongs ' + (cls || '') + '">' + I.note + '</div>'; }
  function plCov(pl, size, cls) {
    var first = pl && mz.plCache[pl.id] && mz.byId.get(mz.plCache[pl.id][0]);
    var own = pl && mz.artV && mz.artV['pl_' + pl.id];                                  // a picture chosen for this playlist
    return cov(own ? 'pl-' + pl.id : (pl && pl.c) || (first && first.c) || '', mzHue(pl ? pl.name : 'pl'), pl ? pl.name : '♪', size, cls);
  }

  // ─── tint (page header colour from the cover) ──────────
  function colorOf(img) {
    try {
      var c = document.createElement('canvas'); c.width = c.height = 12;
      var x = c.getContext('2d'); x.drawImage(img, 0, 0, 12, 12);
      var d = x.getImageData(0, 0, 12, 12).data, r = 0, g = 0, b = 0, w = 0;
      for (var i = 0; i < d.length; i += 4) {
        var mx = Math.max(d[i], d[i + 1], d[i + 2]), mn = Math.min(d[i], d[i + 1], d[i + 2]);
        var wt = 0.05 + Math.pow((mx - mn) / (mx || 1), 2) * 3;
        r += d[i] * wt; g += d[i + 1] * wt; b += d[i + 2] * wt; w += wt;
      }
      r /= w; g /= w; b /= w;
      var max = Math.max(r, g, b) / 255, min = Math.min(r, g, b) / 255, l = (max + min) / 2, h = 0, s = 0;
      if (max !== min) {
        var dd = max - min; s = l > 0.5 ? dd / (2 - max - min) : dd / (max + min);
        if (max === r / 255) h = ((g - b) / 255 / dd + (g < b ? 6 : 0)); else if (max === g / 255) h = ((b - r) / 255 / dd + 2); else h = ((r - g) / 255 / dd + 4);
        h *= 60;
      }
      return 'hsl(' + Math.round(h) + ' ' + Math.round(Math.min(70, Math.max(0, s * 100))) + '% 32%)';       // a black-and-white cover gives a grey page, not a coloured one
    } catch (e) { return null; }
  }
  function tint(page, coverId, hue) {
    if (!page) return;
    page.style.setProperty('--tint', 'hsl(' + hue + ' 30% 30%)');
    if (!coverId) return;
    if (tintCache[coverId]) { page.style.setProperty('--tint', tintCache[coverId]); return; }
    var img = new Image();
    img.onload = function () { var c = colorOf(img); if (c) { tintCache[coverId] = c; if (page.isConnected) { page.style.setProperty('--tint', c); barsSoon(); } } };
    img.src = mzCoverUrl(coverId, 64);
  }

  // ─── data helpers ──────────────────────────────────────
  function sumDur(list) { return list.reduce(function (s, t) { return s + (t.d || 0); }, 0); }
  function albumsArr() { return Array.from(mz.albums.values()); }
  function albumLastPlayed(al) { return al.tracks.reduce(function (m, t) { return Math.max(m, t.lp || 0); }, 0); }
  function artistPlays(a) { return a.tracks.reduce(function (s, t) { return s + (t.pc || 0); }, 0); }
  function liked() { return musicPlaylist.filter(function (t) { return t.fav; }); }

  function mixes() {
    var all = musicPlaylist, out = [];
    var arts = Array.from(mz.artists.values()).filter(function (a) { return a.tracks.length >= 6 && !/unknown/i.test(a.name); })
      .sort(function (a, b) { return artistPlays(b) - artistPlays(a); }).slice(0, 18);
    var pool = mzShuffled(arts);
    for (var n = 0; n < 3 && pool.length >= 3 * (n + 1); n++) {
      var grp = pool.slice(n * 3, n * 3 + 3), list = [];
      grp.forEach(function (a) { list = list.concat(mzShuffled(a.tracks).slice(0, 14)); });
      list = list.concat(mzShuffled(all).slice(0, 8));
      out.push({ id: 'daily' + (n + 1), title: 'Daily Mix ' + (n + 1), sub: grp.map(function (a) { return a.name; }).join(', ') + ' and more', tracks: mzShuffled(list), hue: [200, 330, 140][n] });
    }
    var rep = all.filter(function (t) { return t.pc >= 2; }).sort(function (a, b) { return b.pc - a.pc; }).slice(0, 50);
    if (rep.length >= 10) out.push({ id: 'onrepeat', title: 'On Repeat', sub: 'Songs you love right now', tracks: rep, hue: 270 });
    var fresh = mzShuffled(all.filter(function (t) { return !t.pc; })).slice(0, 50);
    if (fresh.length >= 10) out.push({ id: 'discover', title: 'Discover Mix', sub: 'Songs you haven\'t played yet', tracks: fresh, hue: 25 });
    out.forEach(function (m) { mz.mixCache[m.id] = m; });
    return out;
  }
  function getMix(id) { if (!mz.mixCache[id]) mixes(); return mz.mixCache[id]; }
  function mixCov(m, size, cls) {
    var t = m.tracks[0];
    return '<div class="wm-art sp-art sp-mix ' + (cls || '') + '" style="--h:' + m.hue + '"><span class="tag">' + esc(m.title) + '</span>' +
      (t && t.c ? '<img loading="lazy" decoding="async" alt="" src="' + esc(mzCoverUrl(t.c, size)) + '" onerror="this.remove()">' : '') + '</div>';
  }

  // ─── building blocks ───────────────────────────────────
  function card(o) {
    return '<div class="sp-cardx" data-act="sp-open" data-k="' + o.k + '" data-v="' + esc(o.v) + '">' +
      '<div class="sp-cover">' + o.cover + '<button class="sp-cardplay" data-act="sp-playctx" data-k="' + (o.pk || o.k) + '" data-v="' + esc(o.v) + '" aria-label="Play">' + I.play + '</button></div>' +
      '<div class="sp-ct">' + esc(o.title) + '</div><div class="sp-cs">' + esc(o.sub) + '</div></div>';
  }
  function albumCard(al) { return card({ k: 'album', v: al.id, cover: albumCov(al, 300), title: al.name, sub: (al.year ? al.year + ' • ' : '') + al.artist }); }
  function trackCard(t) { return card({ k: 'song', pk: 'songs1', v: t.f, cover: trackCov(t, 300), title: t.t, sub: t.ar }); }
  function artistCard(a) { return card({ k: 'artist', v: a.id, cover: artistCov(a, 300), title: a.name, sub: 'Artist' }); }
  function plCard(p) { return card({ k: 'playlist', v: p.id, cover: plCov(p, 300), title: p.name, sub: 'By ' + ME }); }
  function mixCard(m) { return card({ k: 'mix', v: m.id, cover: mixCov(m, 300), title: m.title, sub: m.sub }); }
  function shelf(title, cards, showAll, tab, total) {
    if (!cards.length) return '';
    var head = tab ? '<h2><a class="sp-sh" data-act="sp-stab" data-v="' + tab + '">' + esc(title) + '</a></h2>' : '<h2>' + esc(title) + '</h2>';
    var all = tab ? (total > cards.length ? '<a data-act="sp-stab" data-v="' + tab + '">Show all ' + total + '</a>' : '')
      : (showAll ? '<a data-act="sp-showall" data-v="' + showAll + '">Show all</a>' : '');
    return '<section class="sp-shelf"><div class="sp-shelf-h">' + head + all + '</div><div class="sp-cards">' + cards.join('') + '</div></section>';
  }
  function gridSection(title, cards) {
    return '<div class="sp-page"><div class="sp-pbody">' + BACK + '<h1 class="sp-gridtitle">' + esc(title) + '</h1><div class="sp-grid">' + cards.join('') + '</div></div></div>';
  }

  function openTarget(k, v) {
    switch (k) {
      case 'album': mzGo('album', v); break;
      case 'artist': mzGo('artist', v); break;
      case 'playlist': mzGo('playlist', v); break;
      case 'mix': mzGo('mix', v); break;
      case 'liked': mzGo('favorites'); break;
      case 'songs': mzGo('songs'); break;
      case 'genre': mzGo('genre', v); break;
      case 'view': mzGo(v); break;
    }
  }
  function collectionTracks(k, v) {
    switch (k) {
      case 'album': var al = mz.albums.get(v); return al ? al.tracks : [];
      case 'artist': var a = mz.artists.get(v); return a ? a.tracks : [];
      case 'mix': var m = getMix(v); return m ? m.tracks : [];
      case 'liked': return liked();
      case 'songs': return musicPlaylist;
      case 'genre': return mz.genres.get(v) || [];
      case 'playlist': return (mz.plCache[v] || []).map(function (id) { return mz.byId.get(id); }).filter(Boolean);
    }
    return [];
  }
  async function collectionList(k, v) {
    if (k === 'playlist' && !mz.plCache[v]) {
      try { var r = await fetch('/api/music/playlist/' + encodeURIComponent(v)); mz.plCache[v] = (await r.json()).ids || []; } catch (_) { mz.plCache[v] = []; }
    }
    return collectionTracks(k, v);
  }
  async function playCollection(k, v, shuffle) {
    var list = await collectionList(k, v);
    if (list.length) { mz.nextCtx = { k: k, v: v }; mzPlayList(list, 0, shuffle); if (shuffle) SP.render(); }
  }

  // ─── sidebar ───────────────────────────────────────────
  function libCore() {
    var v = mz.view, items = [];
    function item(k, id, cover, title, sub, on) {
      return '<div class="sp-li' + (on ? ' on' : '') + '" data-act="sp-lib" data-k="' + k + '" data-v="' + esc(id) + '">' + cover + '<div class="sp-lit"><b>' + esc(title) + '</b><small>' + esc(sub) + '</small></div></div>';
    }
    var f = libFilter;
    if (!f || f === 'playlists') {
      var nl = liked().length;
      items.push(item('liked', '', likedCov(), 'Liked Songs', 'Playlist • ' + plural(nl, 'song'), v.type === 'favorites'));
      mz.playlists.slice().sort(libSort === 'alpha' ? function (a, b) { return a.name.localeCompare(b.name); } : function () { return 0; }).forEach(function (p) {
        items.push(item('playlist', p.id, plCov(p, 100), p.name, 'Playlist • ' + ME, v.type === 'playlist' && v.key === p.id));
      });
    }
    if (!f || f === 'albums') {
      var al = albumsArr();
      al.sort(libSort === 'alpha' ? function (a, b) { return a.name.localeCompare(b.name); } : function (a, b) { return (albumLastPlayed(b) - albumLastPlayed(a)) || (b.added - a.added); });
      al.slice(0, f ? 400 : 60).forEach(function (a) { items.push(item('album', a.id, albumCov(a, 100), a.name, 'Album • ' + a.artist, v.type === 'album' && v.key === a.id)); });
    }
    if (!f || f === 'artists') {
      var ar = Array.from(mz.artists.values());
      ar.sort(libSort === 'alpha' ? function (a, b) { return a.name.localeCompare(b.name); } : function (a, b) { return artistPlays(b) - artistPlays(a) || b.tracks.length - a.tracks.length; });
      ar.slice(0, f ? 400 : 40).forEach(function (a) { items.push(item('artist', a.id, artistCov(a, 100), a.name, 'Artist', v.type === 'artist' && v.key === a.id)); });
    }
    function chip(k, label) { return '<button class="sp-chip' + (libFilter === k ? ' on' : '') + '" data-act="sp-chip" data-v="' + k + '">' + label + '</button>'; }
    return {
      items: items,
      chips: '<div class="sp-chips">' + chip('playlists', 'Playlists') + chip('artists', 'Artists') + chip('albums', 'Albums') + '</div>',
      tools: '<div class="sp-lib-tools"><button class="sp-sortbtn" data-act="sp-sort">' + (libSort === 'alpha' ? 'Alphabetical' : 'Recents') +
        ' <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M15 14.5H5V13h10v1.5zm0-5.75H5v-1.5h10v1.5zM15 3H5V1.5h10V3zM3 3H1V1.5h2V3zm0 11.5H1V13h2v1.5zm0-5.75H1v-1.5h2v1.5z"/></svg></button></div>',
    };
  }
  function sideHtml() {
    var c = libCore();
    var vt = mz.view.type;
    var nav = '<div class="sp-panel sp-nav">' +
      '<button class="sp-navitem' + (vt === 'home' ? ' on' : '') + '" data-act="sp-home">' + I.home + '<span>Home</span></button>' +
      '<button class="sp-navitem' + (vt === 'search' ? ' on' : '') + '" data-act="sp-search">' + I.search + '<span>Search</span></button></div>';
    return nav + '<div class="sp-panel sp-lib"><div class="sp-lib-head"><div class="sp-libtitle">' + I.lib + '<span>Your Library</span></div></div>' +
      c.chips + c.tools + '<div class="sp-lib-list">' + c.items.join('') + '</div></div>' +
      '<div class="sp-cp" id="sp-cp"><div class="sp-cp-art" id="sp-cp-art"></div><button class="sp-cp-close" data-act="sp-cover-toggle" aria-label="Hide the album art" title="Hide the album art"><svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M14.5 4.5 8 11 1.5 4.5l1.06-1.06L8 8.88l5.44-5.44z"/></svg></button></div>';
  }
  var AVATAR = '<button class="sp-mavatar" onclick="mzThemeMenu(event)" aria-label="Account and theme">R</button>';
  var BACK = '<button class="sp-mback" onclick="history.back()" aria-label="Back"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 5 8 12 15 19"/></svg></button>';
  function libraryView() {
    var c = libCore();
    return { html: '<div class="sp-page sp-libpage"><div class="sp-pbody"><div class="sp-mtop">' + AVATAR + '<h1 class="sp-gridtitle">Your Library</h1></div>' +
      c.chips + c.tools + '<div class="sp-lib-list">' + c.items.join('') + '</div></div></div>', hue: 230 };
  }

  // ─── track table ───────────────────────────────────────
  function artistLinks(t) {
    return mzArtistLinks(t, 'lnk', 'artist');
  }
  // Moving several songs at once: they all shift by the same distance as the grabbed one, so gaps between them stay; the others fill the rest in order.
  function groupShown(shown, sel, dragged, to) {
    var n = shown.length, at = [];
    shown.forEach(function (id, i) { if (sel.has(id)) at.push(i); });
    var delta = Math.max(-at[0], Math.min(n - 1 - at[at.length - 1], to - shown.indexOf(dragged))), out = new Array(n), rest = [];
    at.forEach(function (i) { out[i + delta] = shown[i]; });
    shown.forEach(function (id) { if (!sel.has(id)) rest.push(id); });
    var k = 0; for (var i = 0; i < n; i++) if (out[i] === undefined) out[i] = rest[k++];
    return out;
  }
  // While dragging: the grabbed row follows the pointer; with a selection the other selected rows follow it and the rest slide out of the way.
  function dragLayout(d, y) {
    var n = d.rows.length, to = Math.max(0, Math.min(n - 1, Math.round((d.top0 + y) / d.h)));
    if (d.sel) {
      var res = groupShown(d.ids, d.sel, d.ids[d.from], to);
      d.rows.forEach(function (r, j) {
        var ty = d.sel.has(d.ids[j]) ? Math.max(-j * d.h, Math.min((n - 1 - j) * d.h, y)) : (res.indexOf(d.ids[j]) - j) * d.h;
        r.style.transform = ty ? 'translateY(' + ty + 'px)' : '';
      });
      d.to = to; return;
    }
    d.rows.forEach(function (r, j) {
      if (j === d.from) return;
      var sh = (d.from < j && j <= to) ? -d.h : (to <= j && j < d.from) ? d.h : 0;
      r.style.transform = sh ? 'translateY(' + sh + 'px)' : '';
    });
    d.to = to;
  }
  function selBar(ed) {
    var n = ed.sel.size, off = ed.saving ? ' disabled' : '';
    var all = ed.draft.filter(function (id) { return mz.byId.has(id); }).length;
    if (!n) return '<div class="sp-selbar"><span>Tap songs to select them</span><button data-act="sp-sel-all"' + off + '>Select all</button></div>';
    return '<div class="sp-selbar on"><span>' + n + ' selected</span><button data-act="sp-sel-top"' + off + '>Top</button><button data-act="sp-sel-bottom"' + off + '>Bottom</button><button class="rm" data-act="sp-sel-rm"' + off + '>Remove</button>' +
      (n < all ? '<button data-act="sp-sel-all"' + off + '>All</button>' : '') + '<button data-act="sp-sel-none"' + off + '>Clear</button></div>';
  }
  function rowHtml(t, i, o) {
    var cur = mzCur(), playing = cur && cur.f === t.f;
    var n = o.num === 'n' ? (t.n || i + 1) : i + 1;
    var title = '<div class="tt"><b>' + esc(t.t) + '</b><small>' + (t.ex ? EB : '') + (o.hideArtist ? '' : artistLinks(t)) + '</small></div>';
    var EDITEND = '<button class="sp-rmbtn" data-act="sp-edit-rm" data-c="' + i + '" aria-label="Remove from playlist"><svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10" fill="#e5484d"/><line x1="7" y1="12" x2="17" y2="12" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg></button>' +
      '<span class="sp-grip" aria-label="Drag to reorder" role="button"><svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><rect x="4" y="7" width="16" height="2" rx="1"/><rect x="4" y="11" width="16" height="2" rx="1"/><rect x="4" y="15" width="16" height="2" rx="1"/></svg></span>';
    return '<div class="sp-row trk' + (playing ? ' playing' : '') + (o.edit && edit && edit.sel && edit.sel.has(t.f) ? ' esel' : '') + (mz.sel === i ? ' sel' : '') + (o.cls ? ' ' + o.cls : '') + '" data-act="' + (o.edit ? 'sp-edit-row' : 'row') + '" data-c="' + i + '" data-t="' + esc(t.f) + '">' +
      '<span class="c0"><i class="n">' + n + '</i><i class="eq"></i><button class="pl" data-act="play-row" data-c="' + i + '" aria-label="Play">' + I.play + '</button></span>' +
      '<span class="c1">' + (o.edit ? '<span class="sp-echk' + (edit && edit.sel && edit.sel.has(t.f) ? ' on' : '') + '" aria-hidden="true"></span>' : '') + (o.cover ? trackCov(t, 100, 'sm') : '') + title + '</span>' +
      (o.album ? '<span class="c-alb"><a class="lnk" data-act="album" data-v="' + esc(t.li) + '">' + esc(t.al) + '</a></span>' : '') +
      (o.date ? '<span class="c-date">' + dateStr(t.a) + '</span>' : '') +
      (o.plays ? '<span class="c-plays">' + (t.pc ? t.pc.toLocaleString() : '') + '</span>' : '') +
      '<span class="c-end">' + (o.edit ? EDITEND : (t.fav ? '<span class="sp-lk">' + LIKED_TICK + '</span>' : '') + '<span class="star' + (t.fav ? ' on' : '') + '" data-act="star" data-t="' + esc(t.f) + '">' + SP.heart(t.fav) + '</span><time>' + mzFmt(t.d) + '</time>' +
      '<span class="more" data-act="sp-more" data-t="' + esc(t.f) + '" aria-label="More"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg></span>') + '</span></div>';
  }
  function tableHtml(tracks, o) {
    o = o || {};
    var list = o.noSort || o.edit ? tracks : mzSortList(tracks);
    mz.ctx = list;
    if (!list.length) return '<div class="sp-empty">' + (o.empty || 'Nothing here yet.') + '</div>';
    function th(col, label, cls) {
      var on = mz.sort.col === col;
      return '<span class="' + (cls || '') + (on ? ' on' : '') + '" data-act="sort" data-v="' + col + '">' + label + '</span>';
    }
    var head = '<div class="sp-th"><span class="c0">#</span>' + th('t', 'Title', 'c1') + (o.album ? th('al', 'Album', 'c-alb') : '') + (o.date ? th('a', 'Date added', 'c-date') : '') +
      (o.plays ? th('pc', 'Plays', 'c-plays') : '') + '<span class="c-end">' + th('d', I.clock, 'clk') + '</span></div>';
    var cls = 'sp-tbl' + (o.album ? ' alb' : '') + (o.date ? ' dt' : '') + (o.plays ? ' pl' : '');
    return '<div class="' + cls + '">' + head + list.map(function (t, i) { return rowHtml(t, i, o); }).join('') + '</div>';
  }

  // ─── entity page ───────────────────────────────────────
  function actions(artist, extra) {
    var ad = artist ? ' data-v="' + esc(artist) + '"' : '';
    return '<div class="sp-actions"><button class="sp-bigplay" data-act="' + (artist ? 'sp-playartist' : 'sp-playpage') + '"' + ad + ' aria-label="Play">' + I.play.replace('width="16" height="16"', 'width="24" height="24"') +
      '</button><button class="sp-shufbtn' + (mz.shuffle ? ' on' : '') + '" data-act="' + (artist ? 'sp-shuffleartist' : 'sp-shufflepage') + '"' + ad + ' title="Shuffle" aria-label="Shuffle">' + I.shuffle + '</button>' + (extra || '') + '</div>';
  }
  function page(o) {
    var t = o.title;
    var meta = o.meta || '';
    var head = '<div class="sp-phead">' + BACK + (o.more || '') + '<div class="sp-pcover">' + o.cover + '</div><div class="sp-ptext"><div class="sp-kind">' + esc(o.kind) + '</div>' +
      '<h1 style="font-size:' + fitSize(t) + 'px">' + esc(t) + '</h1><div class="sp-meta">' + meta + '</div></div></div>';
    return { html: '<div class="sp-page' + (o.cls ? ' ' + o.cls : '') + '" id="sp-page">' + head + '<div class="sp-pbody">' + (o.bar || '') + actions('', o.actionsExtra) + (o.body || '') + '</div></div>', tint: o.tint, hue: o.hue || 230 };
  }
  function metaLine(parts, tracks) {
    return parts.concat([plural(tracks.length, 'song') + (tracks.length ? ', ' + mzDur(sumDur(tracks)) : '')]).filter(Boolean).join(' <span class="dot">•</span> ');
  }

  // ─── views ─────────────────────────────────────────────
  function homeView() {
    var h = new Date().getHours(), greet = h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    var recentAlb = albumsArr().filter(albumLastPlayed).sort(function (a, b) { return albumLastPlayed(b) - albumLastPlayed(a); });
    var quick = [{ k: 'liked', v: '', cover: likedCov(), title: 'Liked Songs' }];
    recentAlb.slice(0, 7).forEach(function (al) { quick.push({ k: 'album', v: al.id, cover: albumCov(al, 160), title: al.name }); });
    if (quick.length < 8) mz.playlists.forEach(function (p) { if (quick.length < 8) quick.push({ k: 'playlist', v: p.id, cover: plCov(p, 160), title: p.name }); });
    if (quick.length < 8) albumsArr().sort(function (a, b) { return b.added - a.added; }).forEach(function (al) { if (quick.length < 8) quick.push({ k: 'album', v: al.id, cover: albumCov(al, 160), title: al.name }); });
    var q = '<div class="sp-quicks">' + quick.map(function (x) {
      return '<div class="sp-quick" data-act="sp-open" data-k="' + x.k + '" data-v="' + esc(x.v) + '">' + x.cover + '<b>' + esc(x.title) + '</b>' +
        '<button class="sp-cardplay" data-act="sp-playctx" data-k="' + x.k + '" data-v="' + esc(x.v) + '" aria-label="Play">' + I.play + '</button></div>';
    }).join('') + '</div>';
    var shelves = '';
    var mx = mixes();
    shelves += shelf('Made for ' + ME, mx.map(mixCard));
    shelves += shelf('Recently played', recentAlb.slice(0, 20).map(albumCard), 'albums');
    var topArt = Array.from(mz.artists.values()).filter(function (a) { return !/unknown/i.test(a.name) && a.tracks.length >= 3; })
      .sort(function (a, b) { return artistPlays(b) - artistPlays(a) || b.tracks.length - a.tracks.length; }).slice(0, 20);
    shelves += shelf('Your top artists', topArt.map(artistCard), 'artists');
    shelves += shelf('Recently added', musicPlaylist.slice().sort(function (a, b) { return b.a - a.a; }).slice(0, 20).map(trackCard), 'recent');
    shelves += shelf('Albums for you', mzShuffled(albumsArr().filter(function (a) { return a.tracks.length >= 4; })).slice(0, 20).map(albumCard), 'albums');
    shelves += shelf('Your playlists', mz.playlists.slice(0, 20).map(plCard));
    return { html: '<div class="sp-page sp-home" id="sp-page"><div class="sp-pbody"><div class="sp-mtop">' + AVATAR + '</div><h1 class="sp-greet">' + greet + '</h1>' + q + shelves + '</div></div>', hue: 150 + (h * 7) % 120 };
  }

  // Recents: what you opened from search, newest first (kept in prefs like Follow)
  var X_ICON = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M5 5l14 14M19 5L5 19"/></svg>';
  function recents() { return Array.isArray(mz.prefs.recents) ? mz.prefs.recents : []; }
  function addRecent(k, v) {
    var l = recents().filter(function (r) { return !(r[0] === k && r[1] === v); });
    l.unshift([k, v]); mz.prefs.recents = l.slice(0, 30); mzSavePrefs();
  }
  function recentItem(r) {
    var k = r[0], v = r[1], cur = mzCur();
    if (k === 'album') { var al = mz.albums.get(v); if (!al) return null;
      return { cov: albumCov(al, 112), title: al.name, sub: (al.tracks.some(function (t) { return t.ex; }) ? EB + ' ' : '') + 'Album • ' + esc(albumCredits(al).map(function (c) { return c.name; }).join(', ') || al.artist), on: !!cur && cur.li === v }; }
    if (k === 'artist') { var a = mz.artists.get(v); if (!a) return null; return { cov: artistCov(a, 112), title: a.name, sub: 'Artist', on: false }; }
    if (k === 'playlist') { var pl = mz.playlists.filter(function (x) { return String(x.id) === String(v); })[0]; if (!pl) return null; return { cov: plCov(pl, 112), title: pl.name, sub: 'Playlist', on: false }; }
    if (k === 'song') { var t = mz.byId.get(v); if (!t) return null; return { cov: trackCov(t, 112), title: t.t, sub: (t.ex ? EB + ' ' : '') + 'Song • ' + esc(t.ar), on: !!cur && cur.f === v }; }
    return null;
  }
  // Search history: the words you searched for (kept in prefs like the recents above), newest first
  function searches() { return Array.isArray(mz.prefs.searches) ? mz.prefs.searches : []; }
  var H_ICON = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>';
  function historyHtml() {
    var l = searches(); if (!l.length) return '';
    return '<h2>Recent searches</h2>' + l.map(function (q) {
      return '<div class="sp-rec" data-act="sp-hist" data-v="' + esc(q) + '"><span class="sp-rimg">' + H_ICON + '</span><span class="sp-rtx"><b>' + esc(q) + '</b></span>' +
        '<button class="sp-rx" data-act="sp-histx" data-v="' + esc(q) + '" aria-label="Remove from search history">' + X_ICON + '</button></div>';
    }).join('') + '<button class="sp-showmore" data-act="sp-histclear">Clear search history</button>';
  }
  function recentsView() {
    var rows = recents().map(function (r) {
      var it = recentItem(r); if (!it) return '';
      return '<div class="sp-rec' + (r[0] === 'artist' ? ' art' : '') + '" data-act="sp-open" data-k="' + esc(r[0]) + '" data-v="' + esc(r[1]) + '"><span class="sp-rimg">' + it.cov + '</span>' +
        '<span class="sp-rtx"><b' + (it.on ? ' class="on"' : '') + '>' + esc(it.title) + '</b><i>' + it.sub + '</i></span>' +
        '<button class="sp-rx" data-act="sp-recx" data-k="' + esc(r[0]) + '" data-v="' + esc(r[1]) + '" aria-label="Remove from recents">' + X_ICON + '</button></div>';
    }).join('');
    return { html: '<div class="sp-page"><div class="sp-pbody sp-recs">' + historyHtml() + (rows ? '<h2>Recents</h2>' + rows :
      '<div class="sp-empty"><h2>Play what you love</h2><p>Search for songs, artists, albums and playlists.</p></div>') + '</div></div>', hue: 220 };
  }
  SP.sf = false;                                      // phone: the search field is active (back arrow, Recents)
  SP.setSf = function (on) {
    on = !!on && mzUseSheet(); if (SP.sf === on) return; SP.sf = on;
    if (mz.view.type === 'search' && !mz.query.trim()) mzRender(); else SP.sfApply();
  };
  SP.sfApply = function () {
    var w = rootEl(), on = SP.sf && mz.view.type === 'search' && mzUseSheet();
    if (w) w.dataset.sf = on ? '1' : '';
    var si = mzEl('wm-search-input'); if (si) si.placeholder = on ? 'What do you want to listen to?' : (mz.theme === 'spotify' ? 'What do you want to play?' : 'Search');
  };
  SP.sfExit = function () {
    var si = mzEl('wm-search-input'); if (si) { si.value = ''; si.blur(); }
    clearTimeout(mz.searchTimer); mz.query = ''; SP.sf = false; mzRender();
  };

  var srTab = '';                                     // which kind of search result is open in full: '', songs, artists, albums, playlists
  function searchView() {
    var qs = mz.query.trim().toLowerCase();
    if (!qs) {
      srTab = '';
      if (SP.sf && mzUseSheet()) return recentsView();
      var tiles = [];
      var gs = Array.from(mz.genres.entries()).filter(function (g) { return g[1].length >= 6; }).sort(function (a, b) { return b[1].length - a[1].length; }).slice(0, 18);
      var base = [['Liked Songs', 'liked', ''], ['Recently Added', 'view', 'recent'], ['Most Played', 'view', 'played'], ['All Songs', 'songs', ''], ['Artists', 'view', 'artists'], ['Albums', 'view', 'albums']];
      base.forEach(function (b) { tiles.push({ title: b[0], k: b[1], v: b[2], t: null }); });
      gs.forEach(function (g) { tiles.push({ title: g[0], k: 'genre', v: g[0], t: g[1].filter(function (x) { return x.c; })[0] }); });
      return { html: '<div class="sp-page"><div class="sp-pbody">' + (searches().length ? '<div class="sp-recs sp-hist">' + historyHtml() + '</div>' : '') + '<h2 class="sp-browse">Browse all</h2><div class="sp-tiles">' + tiles.map(function (t) {
        return '<div class="sp-tile" style="--h:' + mzHue(t.title) + '" data-act="sp-open" data-k="' + t.k + '" data-v="' + esc(t.v) + '"><b>' + esc(t.title) + '</b>' +
          (t.t ? '<img loading="lazy" alt="" src="' + esc(mzCoverUrl(t.t.c, 160)) + '" onerror="this.remove()">' : '') + '</div>';
      }).join('') + '</div></div></div>', hue: 220 };
    }
    var terms = qs.split(/\s+/);
    function hit(s) { return terms.every(function (t) { return s.indexOf(t) >= 0; }); }
    var songs = musicPlaylist.filter(function (t) { return hit(t.k); });
    var arts = Array.from(mz.artists.values()).filter(function (a) { return hit(a.name.toLowerCase()); }).sort(function (a, b) { return b.tracks.length - a.tracks.length; });
    var albs = albumsArr().filter(function (a) { return hit((a.name + ' ' + a.artist).toLowerCase()); });
    var pls = mz.playlists.filter(function (p) { return hit((p.name || '').toLowerCase()); });
    var gens = Array.from(mz.genres.entries()).filter(function (g) { return hit(g[0].toLowerCase()); }).sort(function (a, b) { return b[1].length - a[1].length; });
    if (!songs.length && !arts.length && !albs.length && !pls.length && !gens.length) return { html: '<div class="sp-page"><div class="sp-pbody"><div class="sp-empty"><h2>No results found for “' + esc(mz.query) + '”</h2><p>Please make sure your words are spelled correctly, or use fewer or different keywords.</p></div></div></div>', hue: 220 };

    // one chip per kind of result (with how many), so each full list is one tap away
    var kinds = [['songs', 'Songs', songs.length], ['artists', 'Artists', arts.length], ['albums', 'Albums', albs.length], ['playlists', 'Playlists', pls.length], ['genres', 'Genres', gens.length]].filter(function (k) { return k[2]; });
    if (srTab && !kinds.some(function (k) { return k[0] === srTab; })) srTab = '';          // that kind has no matches for this search
    var chips = '<div class="sp-chips sp-schips"><button class="sp-chip' + (srTab ? '' : ' on') + '" data-act="sp-stab" data-v="">All</button>' + kinds.map(function (k) {
      return '<button class="sp-chip' + (srTab === k[0] ? ' on' : '') + '" data-act="sp-stab" data-v="' + k[0] + '">' + k[1] + ' <span class="n">' + k[2] + '</span></button>';
    }).join('') + '</div>';
    var CAP = 600;
    function capNote(n) { return n > CAP ? '<p class="sp-capnote">Showing the first ' + CAP + ' of ' + n + '. Search for something more specific to narrow it down.</p>' : ''; }

    if (srTab === 'songs') {
      return { html: '<div class="sp-page"><div class="sp-pbody">' + chips + '<h2 class="sp-h2">Songs</h2>' + tableHtml(songs.slice(0, 1000), { album: true, cover: true }) + capNote2(songs.length, 1000) + '</div></div>', hue: 220 };
    }
    if (srTab === 'artists') return { html: '<div class="sp-page"><div class="sp-pbody">' + chips + '<h2 class="sp-h2">Artists</h2><div class="sp-grid">' + arts.slice(0, CAP).map(artistCard).join('') + '</div>' + capNote(arts.length) + '</div></div>', hue: 220 };
    if (srTab === 'albums') return { html: '<div class="sp-page"><div class="sp-pbody">' + chips + '<h2 class="sp-h2">Albums</h2><div class="sp-grid">' + albs.slice(0, CAP).map(albumCard).join('') + '</div>' + capNote(albs.length) + '</div></div>', hue: 220 };
    if (srTab === 'genres') return { html: '<div class="sp-page"><div class="sp-pbody">' + chips + '<h2 class="sp-h2">Genres</h2>' + genreTiles(gens) + '</div></div>', hue: 220 };
    if (srTab === 'playlists') return { html: '<div class="sp-page"><div class="sp-pbody">' + chips + '<h2 class="sp-h2">Playlists</h2><div class="sp-grid">' + pls.map(plCard).join('') + '</div></div></div>', hue: 220 };

    // All: the best match, a taste of each kind, and the headers (or Show all) open the full list
    var top;
    var exactArt = arts.filter(function (a) { return a.name.toLowerCase().indexOf(qs) === 0; })[0];
    if (exactArt) top = { cover: artistCov(exactArt, 300), title: exactArt.name, type: 'Artist', k: 'artist', v: exactArt.id };
    else if (albs[0] && (!songs[0] || albs[0].name.toLowerCase().indexOf(qs) === 0)) top = { cover: albumCov(albs[0], 300), title: albs[0].name, type: albs[0].artist, k: 'album', v: albs[0].id, pill: 'Album' };
    else if (songs[0]) top = { cover: trackCov(songs[0], 300), title: songs[0].t, type: songs[0].ar, k: 'song', v: songs[0].f, pill: 'Song' };
    else if (arts[0]) top = { cover: artistCov(arts[0], 300), title: arts[0].name, type: 'Artist', k: 'artist', v: arts[0].id };
    else top = { cover: plCov(pls[0], 300), title: pls[0].name, type: 'Playlist', k: 'playlist', v: pls[0].id };
    mz.ctx = songs.slice(0, 300);
    var topHtml = '<div class="sp-topres" data-act="sp-open" data-k="' + top.k + '" data-v="' + esc(top.v) + '">' + top.cover + '<h3>' + esc(top.title) + '</h3><div><span class="pill">' + esc(top.pill || top.type) + '</span>' +
      (top.pill ? ' <span class="dim">' + esc(top.type) + '</span>' : '') + '</div><button class="sp-cardplay" data-act="sp-playctx" data-k="' + (top.k === 'song' ? 'songs1' : top.k) + '" data-v="' + esc(top.v) + '" aria-label="Play">' + I.play + '</button></div>';
    var songRows = mz.ctx.slice(0, 4).map(function (t, i) { return rowHtml(t, i, { cover: true, cls: 'compact' }); }).join('');
    var songsBlock = songs.length ? '<div><div class="sp-shelf-h"><h2><a class="sp-sh" data-act="sp-stab" data-v="songs">Songs</a></h2>' + (songs.length > 4 ? '<a data-act="sp-stab" data-v="songs">Show all ' + songs.length + '</a>' : '') + '</div><div class="sp-tbl compact">' + songRows + '</div></div>' : '';
    var out = '<div class="sp-page"><div class="sp-pbody">' + chips + '<div class="sp-sr"><div><h2>Top result</h2>' + topHtml + '</div>' + songsBlock + '</div>';
    out += shelf('Artists', arts.slice(0, 12).map(artistCard), null, 'artists', arts.length) + shelf('Albums', albs.slice(0, 12).map(albumCard), null, 'albums', albs.length) +
      shelf('Playlists', pls.slice(0, 12).map(plCard), null, 'playlists', pls.length);
    if (gens.length) out += '<section class="sp-shelf"><div class="sp-shelf-h"><h2><a class="sp-sh" data-act="sp-stab" data-v="genres">Genres</a></h2></div>' + genreTiles(gens.slice(0, 12)) + '</section>';
    return { html: out + '</div></div>', hue: 220 };
  }
  function capNote2(n, cap) { return n > cap ? '<p class="sp-capnote">Showing the first ' + cap + ' of ' + n + '. Search for something more specific to narrow it down.</p>' : ''; }

  function listPage(opts, tracks) {
    var empty = opts.empty;
    var body = tableHtml(tracks, { album: true, date: true, cover: true, empty: empty, edit: opts.edit });
    return page({ kind: opts.kind || 'Playlist', title: opts.title, cover: opts.cover, hue: opts.hue, tint: opts.tint,
      meta: metaLine(opts.metaParts || ['<b>' + ME + '</b>'], tracks), body: body, bar: opts.bar, actionsExtra: opts.actionsExtra, more: opts.more });
  }

  function build() {
    var v = mz.view, all = musicPlaylist;
    switch (v.type) {
      case 'home': return homeView();
      case 'search': return searchView();
      case 'albums': return { html: gridSection('Albums', albumsArr().sort(function (a, b) { return a.artist.localeCompare(b.artist) || a.name.localeCompare(b.name); }).map(albumCard)), hue: 230 };
      case 'artists': return { html: gridSection('Artists', Array.from(mz.artists.values()).sort(function (a, b) { return a.name.localeCompare(b.name); }).map(artistCard)), hue: 230 };
      case 'genres': return searchViewGenres();
      case 'songs': return listPage({ title: 'All Songs', cover: songsCov(), hue: 0 }, all);
      case 'favorites': return listPage({ title: 'Liked Songs', cover: likedCov(), hue: 260, empty: 'Songs you like will appear here. Click the heart next to a song.' }, liked());
      case 'recent': return listPage({ title: 'Recently Added', cover: songsCov(), hue: 150 }, all.slice().sort(function (a, b) { return b.a - a.a; }).slice(0, 200));
      case 'played': return listPage({ title: 'Most Played', cover: songsCov(), hue: 20, empty: 'Play some music and it will show up here.' }, all.filter(function (t) { return t.pc > 0; }).sort(function (a, b) { return b.pc - a.pc; }).slice(0, 200));
      case 'genre': {
        var gt = mz.genres.get(v.key); if (!gt) return missing();
        var f = gt.filter(function (t) { return t.c; })[0];
        return listPage({ kind: 'Genre', title: v.key, cover: f ? trackCov(f, 300) : songsCov(), tint: f && f.c, hue: mzHue(v.key), metaParts: [] }, gt);
      }
      case 'mix': {
        var m = getMix(v.key); if (!m) return missing();
        return listPage({ kind: 'Made for ' + ME, title: m.title, cover: mixCov(m, 300), hue: m.hue, tint: m.tracks[0] && m.tracks[0].c, metaParts: [esc(m.sub)] }, m.tracks);
      }
      case 'playlist': {
        var pl = mz.playlists.filter(function (x) { return x.id === v.key; })[0];
        if (!mz.plCache[v.key]) { mzLoadPlaylist(v.key); return page({ kind: 'Playlist', title: pl ? pl.name : 'Playlist', cover: plCov(pl, 300), hue: 200, meta: 'Loading…', body: '' }); }
        if (edit && edit.pid !== v.key) edit = null;                       // left the playlist: edits are discarded
        var ed = edit, pt = (ed ? ed.draft : mz.plCache[v.key]).map(function (id) { return mz.byId.get(id); }).filter(Boolean);
        var pen = '<button class="sp-editbtn" data-act="sp-edit" title="Edit playlist" aria-label="Edit playlist"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/></svg></button>';
        return listPage({ title: pl ? pl.name : 'Playlist', cover: plCov(pl, 300), tint: (pl && mz.artV && mz.artV['pl_' + pl.id] ? 'pl-' + pl.id : pl && pl.c) || (pt[0] && pt[0].c), hue: mzHue(pl ? pl.name : 'p'),
          edit: !!ed, actionsExtra: !ed && mzIsMobile() && pt.length ? pen : '',
          more: ed || !pl ? '' : '<button class="sp-mmore" data-act="sp-plmenu" data-v="' + esc(pl.id) + '" aria-label="More options"><svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg></button>',
          bar: ed ? '<div class="sp-editbar"><button class="cancel" data-act="sp-edit-cancel"' + (ed.saving ? ' disabled' : '') + '>Cancel</button><b>Editing playlist</b><button class="done" data-act="sp-edit-done"' + (ed.saving ? ' disabled' : '') + '>' + (ed.saving ? 'Saving…' : 'Done') + '</button></div>' + selBar(ed) : '' }, pt);
      }
      case 'album': {
        var al = mz.albums.get(v.key); if (!al) return missing();
        var phoneAlb = mzIsMobile();
        // on a phone every row shows its artists (with the E badge), as the Spotify app does; the desktop table hides them when they are all the same
        var body = tableHtml(al.tracks, { num: 'n', noSort: !mz.sort.col, hideArtist: !phoneAlb && al.tracks.every(function (t) { return t.ar === al.artist; }) });
        var cr = albumCredits(al);
        var avatars = '<span class="sp-avs">' + cr.slice(0, 3).map(function (c) { var ar = mz.artists.get(c.id); return ar ? artistCov(ar, 60, 'xs') : ''; }).join('') + '</span>';
        var names = cr.map(function (c) { return '<a class="lnk bold" data-act="artist" data-v="' + esc(c.id) + '">' + esc(c.name) + '</a>'; }).join('<span class="dot"> • </span>');
        var sub = '<div class="sp-asub">' + (al.tracks.some(function (t) { return t.ex; }) ? EB : '') + 'Album' + (al.year ? ' <span class="dot">•</span> ' + esc(al.year) : '') + '</div>';
        var meta = '<span class="sp-mby">' + avatars + names + '</span><span class="sp-mcount"> <span class="dot">•</span> ' + esc(plural(al.tracks.length, 'song')) + ', ' + esc(mzDur(sumDur(al.tracks))) + (al.year ? ' <span class="dot">•</span> ' + esc(al.year) : '') + '</span>' + sub;
        var more = '<button class="sp-mmore" data-act="sp-albummenu" data-v="' + esc(al.id) + '" aria-label="More options"><svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg></button>';
        return page({ kind: 'Album', title: al.name, cover: albumCov(al, 400), tint: al.first.c, hue: al.h, meta: meta, body: body, cls: 'sp-albumpage', more: more });
      }
      case 'artist': return artistView();
      case 'now': return queueView();
      case 'lyrics': return lyricsView();
      case 'library': return libraryView();
    }
    return missing();
  }
  function genreTiles(gs) {
    return '<div class="sp-tiles">' + gs.map(function (g) {
      var f = g[1].filter(function (x) { return x.c; })[0];
      return '<div class="sp-tile" style="--h:' + mzHue(g[0]) + '" data-act="sp-open" data-k="genre" data-v="' + esc(g[0]) + '"><b>' + esc(g[0]) + '</b>' + (f ? '<img loading="lazy" alt="" src="' + esc(mzCoverUrl(f.c, 160)) + '" onerror="this.remove()">' : '') + '</div>';
    }).join('') + '</div>';
  }
  function searchViewGenres() {
    var gs = Array.from(mz.genres.entries()).sort(function (a, b) { return b[1].length - a[1].length; });
    return { html: '<div class="sp-page"><div class="sp-pbody"><h1 class="sp-gridtitle">Genres</h1>' + genreTiles(gs) + '</div></div>', hue: 230 };
  }
  function missing() { return { html: '<div class="sp-page"><div class="sp-pbody"><div class="sp-empty"><h2>Couldn\'t find that page</h2><p>It may have been removed from your library.</p></div></div></div>', hue: 230 }; }

  // one block per album: a clickable header, then its tracks as ordinary playable rows
  function discoBlock(al, a, ctx) {
    var tr = al.tracks.slice().sort(function (x, y) { return (x.n || 999) - (y.n || 999); });
    var single = tr.length === 1;
    if (single) ctx.push(tr[0]);                               // a lone track would just repeat the header
    var rows = single ? '' : tr.map(function (t) { ctx.push(t); return rowHtml(t, ctx.length - 1, { num: 'n', hideArtist: t.ar === a.name, cls: 'artist' }); }).join('');
    return '<div class="sp-disc-blk"><div class="sp-disc-head" data-act="album" data-v="' + esc(al.id) + '">' + albumCov(al, 100) +
      '<div class="tt"><b>' + esc(al.name) + '</b><small>' + (al.year ? esc(al.year) + ' • ' : '') + (tr.length === 1 ? 'Single' : 'Album') + ' • ' + plural(tr.length, 'song') + '</small></div>' +
      '<button class="pl" data-act="sp-playctx" data-k="album" data-v="' + esc(al.id) + '" aria-label="Play ' + esc(al.name) + '">' + I.play + '</button></div>' +
      (single ? '' : '<div class="sp-tbl pl compact art">' + rows + '</div>') + '</div>';
  }

  var aboutCache = {};
  function loadAbout(id) {
    function paint(d) {
      var el = document.getElementById('sp-about');
      if (!el || el.dataset.aid !== id) return;                                    // the page changed while this was loading
      var sim = (d.similar || []).map(function (x) { return mz.artists.get(x.id); }).filter(Boolean);
      var bio = d.bio || '';
      if (!bio && !sim.length) { el.innerHTML = ''; return; }
      var long = bio.length > 420, shown = mz.spAboutMore === id || !long ? bio : bio.slice(0, 420).replace(/\s+\S*$/, '') + '…';
      el.innerHTML = (bio ? '<h2 class="sp-h2">About</h2><div class="sp-about"><p>' + esc(shown) + '</p>' +
          (long ? '<button class="sp-showmore" data-act="sp-aboutmore" data-v="' + esc(id) + '">' + (mz.spAboutMore === id ? 'Show less' : 'Read more') + '</button>' : '') + '</div>' : '') +
        shelf('Fans also like', sim.map(artistCard));
    }
    if (aboutCache[id]) { paint(aboutCache[id]); return; }
    fetch('/api/music/artist/' + encodeURIComponent(id)).then(function (r) { return r.json(); }).then(function (d) { if (d && !d.error) { aboutCache[id] = d; paint(d); } }).catch(function () {});
  }
  SP.aboutRepaint = function (id) { if (aboutCache[id]) loadAbout(id); };

  function artistView() {
    var a = mz.artists.get(mz.view.key); if (!a) return missing();
    var popular = a.tracks.slice().sort(function (x, y) { return (y.pc || 0) - (x.pc || 0) || x.al.localeCompare(y.al) || (x.n || 999) - (y.n || 999); });
    var albums = Array.from(a.albums).sort(function (x, y) { return (y.year || '').localeCompare(x.year || ''); });
    var nPop = mz.spPopMore === a.id ? 10 : 5;
    var ctx = popular.slice(0, nPop);
    var rows = popular.slice(0, nPop).map(function (t, i) { return rowHtml(t, i, { cover: true, plays: true, cls: 'artist' }); }).join('');
    var cover = a.tracks.filter(function (t) { return t.c; })[0];
    var banner = !!(mz.artB && mz.artB[a.id]);       // a real wide banner (Spotify/SoundCloud); otherwise a blurred backdrop with the round photo on it
    var head = '<div class="sp-ahead' + (banner ? '' : ' nobanner') + '">' + BACK + (mz.source === 'navidrome' ? '<button class="sp-mmore" data-act="sp-artistmenu" data-v="' + esc(a.id) + '" aria-label="More options"><svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg></button>' : '') + '<div class="sp-abg">' + (artistImg(a, 1000) ? '<img' + (banner ? ' class="sp-aimg"' : '') + ' alt="" src="' + esc(banner ? artistImg(a, 1000, true) : artistImg(a, 500)) + '"' + (cover ? ' data-fb="' + esc(mzCoverUrl(cover.c, 600)) + '"' : '') + ' onerror="' + IMG_FALLBACK + '">'
        : cover ? '<img alt="" src="' + esc(mzCoverUrl(cover.c, 600)) + '" onerror="this.remove()">' : '') + '</div>' +
      '<div class="sp-ptext">' + (artistImg(a, 400) ? '<img class="sp-apfp" alt="" src="' + esc(artistImg(a, 400)) + '" onerror="this.remove()">' : '') + '<div class="sp-pinfo"><div class="sp-kind"><svg viewBox="0 0 24 24" width="24" height="24" fill="#4cb3ff"><path d="M10.814.5a1.658 1.658 0 0 1 2.372 0l2.512 2.572 3.595-.043a1.658 1.658 0 0 1 1.678 1.678l-.043 3.595 2.572 2.512c.667.65.667 1.722 0 2.372l-2.572 2.512.043 3.595a1.658 1.658 0 0 1-1.678 1.678l-3.595-.043-2.512 2.572a1.658 1.658 0 0 1-2.372 0l-2.512-2.572-3.595.043a1.658 1.658 0 0 1-1.678-1.678l.043-3.595L.5 13.186a1.658 1.658 0 0 1 0-2.372l2.572-2.512-.043-3.595a1.658 1.658 0 0 1 1.678-1.678l3.595.043L10.814.5zm6.584 9.12a1 1 0 0 0-1.414-1.413l-6.011 6.01-1.894-1.893a1 1 0 0 0-1.414 1.414l3.308 3.308 7.425-7.425z" fill="#4cb3ff"/><path d="M10.5 15.9l-2.4-2.4 1.1-1.1 1.3 1.3 4.3-4.3 1.1 1.1z" fill="#fff"/></svg> Your library artist</div>' +
      '<h1 style="font-size:' + (a.name.length <= 11 ? 96 : a.name.length <= 20 ? 72 : 48) + 'px">' + esc(a.name) + '</h1><div class="sp-meta">' + plural(a.tracks.length, 'song') + ' • ' + mzDur(sumDur(a.tracks)) + '</div></div></div></div>';
    var more = popular.length > 5 ? '<button class="sp-showmore" data-act="sp-popmore" data-v="' + esc(a.id) + '">' + (nPop > 5 ? 'Show less' : 'Show more') + '</button>' : '';
    var body = actions('artist:' + a.id) + '<h2 class="sp-h2">Popular</h2><div class="sp-tbl pl compact art">' + rows + '</div>' + more +
      (albums.length ? '<h2 class="sp-h2">Discography</h2><div class="sp-disc">' + albums.map(function (al) { return discoBlock(al, a, ctx); }).join('') + '</div>' : '') +
      (mz.source === 'navidrome' ? '<div id="sp-about" data-aid="' + esc(a.id) + '"></div>' : '');
    mz.ctx = ctx;
    if (mz.source === 'navidrome') loadAbout(a.id);
    return { html: '<div class="sp-page sp-artistpage" id="sp-page">' + head + '<div class="sp-pbody">' + body + '</div></div>', tint: cover && cover.c, hue: mzHue(a.name) };
  }

  function queueView() {
    var cur = mzCur();
    if (!cur) return { html: '<div class="sp-page"><div class="sp-pbody"><h1 class="sp-gridtitle">Queue</h1><div class="sp-empty"><h2>Nothing in the queue</h2><p>Start playing something and it will show up here.</p></div></div></div>', hue: 230 };
    function qrow(t, i) {
      return '<div class="sp-row qrow compact' + (i === mz.qi ? ' playing' : '') + '" data-act="q-jump" data-c="' + i + '" data-t="' + esc(t.f) + '">' +
        '<span class="c0"><i class="n">' + (i === mz.qi ? '' : i + 1) + '</i><i class="eq"></i><button class="pl" data-act="q-jump" data-c="' + i + '">' + I.play + '</button></span>' +
        '<span class="c1">' + trackCov(t, 100, 'sm') + '<div class="tt"><b>' + esc(t.t) + '</b><small>' + artistLinks(t) + '</small></div></span>' +
        '<span class="c-end"><time>' + mzFmt(t.d) + '</time></span></div>';
    }
    var next = mz.queue.slice(mz.qi + 1, mz.qi + 201);
    var out = '<div class="sp-page"><div class="sp-pbody">' + BACK + '<h1 class="sp-gridtitle">Queue</h1><h2 class="sp-h2">Now playing</h2><div class="sp-tbl compact">' + qrow(cur, mz.qi) + '</div>';
    if (next.length) {
      out += '<div class="sp-qhead"><h2 class="sp-h2">Next in queue</h2><button class="sp-textbtn" data-act="sp-clearq">Clear queue</button></div><div class="sp-tbl compact">' +
        next.map(function (t, n) { return qrow(t, mz.qi + 1 + n); }).join('') + '</div>';
    }
    return { html: out + '</div></div>', hue: 230 };
  }

  // ─── public API ────────────────────────────────────────
  var lastSig = '';
  SP.render = function () {
    var content = mzEl('wm-content'); if (!content) return;
    mzEl('wm-side').innerHTML = sideHtml();
    cpTrack = null; SP.coverSync();
    var hb = document.querySelector('#music-screen .sp-homebtn'); if (hb) hb.classList.toggle('on', mz.view.type === 'home');
    var tabOn = mz.view.type === 'home' ? 'home' : mz.view.type === 'search' ? 'search' : mz.view.type === 'library' ? 'library' : '';
    var tb = mzEl('sp-tabbar'); if (tb) tb.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', b.dataset.v === tabOn); });
    if (mz.view.type !== 'search') SP.sf = false;
    var vw = document.querySelector('#music-screen .wm'); if (vw) vw.dataset.view = mz.view.type; SP.sfApply();
    var vw = build(), keep = content.scrollTop, same = mz.view;
    var sig = mz.view.type + ':' + mz.view.key;
    if (lastSig && sig !== lastSig) {                               // a different page: slide it in the way the navigation went
      content.classList.remove('sp-v-fwd', 'sp-v-back'); void content.offsetWidth;
      content.classList.add(nav.dir === 'back' ? 'sp-v-back' : 'sp-v-fwd');
      content.addEventListener('animationend', function done(ev) {                // the slide is over: stop holding the page as a separate graphics layer
        if (ev.target !== content) return;
        content.classList.remove('sp-v-fwd', 'sp-v-back'); content.removeEventListener('animationend', done);
      });
    }
    lastSig = sig;
    content.innerHTML = (mz.error ? '<div class="sp-notice">' + esc(mz.error) + '</div>' : '') + vw.html;
    if (mz.view === same) content.scrollTop = keep;
    tint(mzEl('sp-page'), vw.tint, vw.hue || 230);
    mzMarkPlaying();
    SP.markCtx(); SP.dselSync(); SP.qpSync();
    coversAhead(content);
    barsSoon();
  };
  // Covers load about two screens ahead of the scroll, not when a row is nearly on screen, so they are already there when you get to them.
  // (The browser's own lazy loading waits much closer to the screen; flipping an image to eager makes it load at once.)
  var coverIO = null;
  function coversAhead(root) {
    if (coverIO) coverIO.disconnect();
    if (!('IntersectionObserver' in window)) return;
    coverIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var img = en.target; coverIO.unobserve(img);
        if (img.complete) return;
        img.loading = 'eager';
        img.addEventListener('load', function () { if (img.decode) img.decode().catch(function () {}); }, { once: true });      // decoded now, not when it scrolls in
      });
    }, { root: root, rootMargin: '1600px 0px' });
    Array.prototype.forEach.call(root.querySelectorAll('img[loading="lazy"]'), function (img) { coverIO.observe(img); });
  }
  SP.miniTint = function (t) {
    var w = document.querySelector('#music-screen .wm'); if (!w) return;
    w.style.setProperty('--sp-mini', 'hsl(' + t.h + ' 22% 22%)');
    if (!t.c) return;
    if (tintCache['m' + t.c]) { w.style.setProperty('--sp-mini', tintCache['m' + t.c]); return; }
    var img = new Image();
    img.onload = function () { var c = colorOf(img); if (c) { tintCache['m' + t.c] = c; w.style.setProperty('--sp-mini', c); } };
    img.src = mzCoverUrl(t.c, 64);
  };
  // the big album cover (old Spotify desktop): the little cover in the player bar expands into the sidebar
  var cpTrack = null;
  SP.coverApply = function () {
    var w = rootEl(); if (!w) return;
    var on = mz.theme === 'spotify' && mz.prefs.coverOpen === true;
    w.classList.toggle('cover-open', on);
    var b = mzEl('sp-expand'); if (b) { b.setAttribute('aria-expanded', on ? 'true' : 'false'); }
    cpTrack = null; SP.coverSync();
  };
  SP.coverToggle = function () {
    mz.prefs.coverOpen = !mz.prefs.coverOpen; mzSavePrefs(); SP.coverApply(); mzHaptic('tick');
  };
  SP.coverSync = function () {
    var t = mzCur(), art = mzEl('sp-cp-art'); if (!t || !art || cpTrack === t.f) return;
    cpTrack = t.f;
    art.innerHTML = '<div class="sp-cp-link" data-act="np-album" data-v="' + esc(t.li || '') + '">' + cov(t.c, t.h, t.al || t.t, 640, '') + '</div>';
  };
  SP.markPlaying = function () {
    SP.coverSync();
    var cur = mzCur();
    document.querySelectorAll('#wm-side .sp-li').forEach(function (el) { el.classList.remove('playing'); });
    if (cur) {
      var key = cur.li;
      document.querySelectorAll('#wm-side .sp-li[data-k="album"]').forEach(function (el) { el.classList.toggle('playing', el.dataset.v === key); });
    }
  };
  SP.click = function (a, el, e) {
    var k = el.dataset.k, v = el.dataset.v;
    switch (a) {
      case 'sp-home': mzGo('home'); break;
      case 'sp-edit': {
        var ids0 = mz.plCache[mz.view.key]; if (!ids0 || mz.view.type !== 'playlist') break;
        edit = { pid: mz.view.key, draft: ids0.slice(), base: ids0.length, saving: false, sel: new Set() }; mzHaptic('tick'); mzRender(); break;
      }
      case 'sp-edit-cancel': {
        if (!edit || edit.saving) break;
        var cur0 = mz.plCache[edit.pid] || [], dirty = edit.draft.join('\n') !== cur0.join('\n');
        if (dirty && !window.confirm('Discard your changes to this playlist?')) break;
        edit = null; mzRender(); break;
      }
      case 'sp-edit-done': SP.editDone(); break;
      case 'sp-edit-rm': {
        if (!edit || edit.saving) break;
        var at = []; edit.draft.forEach(function (id, i) { if (mz.byId.has(id)) at.push(i); });
        var di = at[parseInt(el.dataset.c, 10)]; if (di === undefined) break;
        edit.sel.delete(edit.draft[di]); edit.draft.splice(di, 1); mzHaptic('tick'); mzRender(); break;
      }
      case 'sp-edit-row': {                                          // tap a song while editing: select it, to move or remove several at once
        if (!edit || edit.saving || !el.dataset.t) break;
        if (edit.sel.has(el.dataset.t)) edit.sel.delete(el.dataset.t); else edit.sel.add(el.dataset.t);
        mzHaptic('tick'); mzRender(); break;
      }
      case 'sp-sel-all': case 'sp-sel-none': case 'sp-sel-top': case 'sp-sel-bottom': case 'sp-sel-rm': {
        if (!edit || edit.saving) break;
        var known = edit.draft.filter(function (id) { return mz.byId.has(id); });
        if (a === 'sp-sel-all') edit.sel = new Set(known);
        else if (a === 'sp-sel-none') edit.sel = new Set();
        else {
          var chosen = edit.draft.filter(function (id) { return edit.sel.has(id); }), others = edit.draft.filter(function (id) { return !edit.sel.has(id); });
          if (a === 'sp-sel-top') edit.draft = chosen.concat(others);
          else if (a === 'sp-sel-bottom') edit.draft = others.concat(chosen);
          else { edit.draft = others; edit.sel = new Set(); }
        }
        mzHaptic('tick'); mzRender(); break;
      }
      case 'sp-search': mzGo('search'); if (!mzUseSheet()) mzEl('wm-search-input').focus(); break;
      case 'sp-chip': libFilter = libFilter === v ? '' : v; if (mz.view.type === 'library') SP.render(); else mzEl('wm-side').innerHTML = sideHtml(); break;
      case 'sp-sort': libSort = libSort === 'recent' ? 'alpha' : 'recent'; if (mz.view.type === 'library') SP.render(); else mzEl('wm-side').innerHTML = sideHtml(); break;
      case 'sp-cover-toggle': SP.coverToggle(); break;
      case 'sp-tab': {
        var again = v === 'search' && mz.view.type === 'search';
        if (!again) mzGo(v);
        // phone: the first tap shows Browse all; tapping Search again (like Spotify) puts the cursor in the field and brings up the keyboard
        if (v === 'search' && (!mzUseSheet() || again)) mzEl('wm-search-input').focus();
        break;
      }
      case 'sp-more': { e.stopPropagation(); var rr = el.getBoundingClientRect(); mzOpenMenu(rr.left, rr.bottom, el.dataset.t, false, null); break; }
      case 'sp-recx': { e.stopPropagation(); mz.prefs.recents = recents().filter(function (r) { return !(r[0] === k && r[1] === v); }); mzSavePrefs(); mzHaptic('tick'); mzRender(); break; }
      case 'sp-hist': { var si = mzEl('wm-search-input'); if (si) si.value = v; mz.query = v; mzSearchRemember(v); mzRender(); var sc2 = mzEl('wm-content'); if (sc2) sc2.scrollTop = 0; break; }
      case 'sp-histx': e.stopPropagation(); mz.prefs.searches = searches().filter(function (q) { return q !== v; }); mzSavePrefs(); mzHaptic('tick'); mzRender(); break;
      case 'sp-histclear': mz.prefs.searches = []; mzSavePrefs(); mzRender(); break;
      case 'sp-lib': case 'sp-open':
        if (mz.view.type === 'search') mzSearchRemember(mz.query);
        if (mz.view.type === 'search' && (k === 'album' || k === 'artist' || k === 'playlist' || k === 'song')) addRecent(k, v);
        if (k === 'song') { var t = mz.byId.get(v); if (t) mzPlayList([t], 0); } else openTarget(k, v);
        break;
      case 'sp-playctx': {
        e.stopPropagation();
        if (k === 'songs1') { var one = mz.byId.get(v); if (one) mzPlayList([one], 0); } else playCollection(k, v);
        break;
      }
      case 'sp-playartist': case 'sp-shuffleartist': {
        var ar = mz.artists.get(String(v).replace(/^artist:/, '')); if (!ar) break;
        var all = ar.tracks.slice().sort(function (x, y) { return (y.pc || 0) - (x.pc || 0); });
        mz.nextCtx = { k: 'artist', v: ar.id }; mzPlayList(all, 0, a === 'sp-shuffleartist'); if (a === 'sp-shuffleartist') SP.render(); break;
      }
      case 'sp-aboutmore': mz.spAboutMore = mz.spAboutMore === v ? '' : v; SP.aboutRepaint(v); break;
      case 'sp-popmore': mz.spPopMore = mz.spPopMore === v ? '' : v; SP.render(); break;
      case 'sp-stab': { srTab = v || ''; SP.render(); var sc = mzEl('wm-content'); if (sc) sc.scrollTop = 0; break; }
      case 'sp-lyr-seek': { var ms = parseInt(el.dataset.ms, 10); if (isFinite(ms)) { mzHaptic('tick'); mzMediaSeekTo(ms / 1000); if (lyr) lyr.user = 0; lyrSync(true); } break; }
      case 'sp-creditsall': { mz.spCreditsAll = !mz.spCreditsAll; var ct = mzCur(); if (ct) npCards(ct); break; }
      case 'sp-artistmenu': { var arm = mz.artists.get(v); if (arm) SP.artistMenu(arm); break; }
      case 'sp-qual': { var qt = mzCur(); if (qt) SP.qualMenu(qt); break; }
      case 'sp-qp-close': SP.qpToggle(); break;
      case 'sp-qp-more': SP.qpMore(); break;
      case 'sp-plmenu': { var plm = mz.playlists.filter(function (x) { return x.id === v; })[0]; if (plm) SP.playlistMenu(plm); break; }
      case 'sp-albummenu': { var alm = mz.albums.get(v); if (alm) SP.albumMenu(alm); break; }
      case 'sp-playpage': mzPlayList(mz.ctx, 0); break;
      case 'sp-shufflepage': mzPlayList(mz.ctx, 0, true); SP.render(); break;
      case 'play-row': e.stopPropagation(); mzPlayCtx(parseInt(el.dataset.c, 10)); break;
      case 'sp-showall': mzGo(v); break;
      case 'sp-clearq':
        if (mz.remote) { mzCmd('qclear'); break; }
        mz.queue = mz.queue.slice(mz.qi, mz.qi + 1); mz.qi = mz.queue.length ? 0 : -1; mz.origQueue = null; mzSaveState(true); mzRender(); break;
    }
  };
  // ─── phone full-screen player: a sheet that follows your finger ──────
  // Swipe up on the mini player to pull it open, swipe down on the player to dismiss it. It tracks the
  // finger 1:1, then snaps (distance or flick speed decides) with an iOS-style ease.
  var npEl = null, npTimer = 0, npHideT = 0, npTrack = null, npLast = {}, lastDragAt = 0, npIsOpen = false;
  var NP = {
    like: '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="7.5" x2="12" y2="16.5"/><line x1="7.5" y1="12" x2="16.5" y2="12"/></svg>',
    liked: '<svg viewBox="0 0 24 24" width="30" height="30"><circle cx="12" cy="12" r="11" fill="#1ed760"/><polyline points="7 12.5 10.5 16 17 8.5" fill="none" stroke="#000" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    play: '<svg viewBox="0 0 24 24" width="30" height="30" fill="currentColor"><polygon points="7 4 20 12 7 20"/></svg>',
    pause: '<svg viewBox="0 0 24 24" width="30" height="30" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
  };
  // The system status bar (and nav bar) is painted by Android from the page's theme colour, so the closest a web app gets to "transparent" is
  // matching it to the screen: while the player is open it takes the player's top tint, then goes back to what it was.
  var BARS_FOLLOW_PAGE = true;                                     // a transparent theme-color is read as black by Chrome, so matching the page is the closest thing
  function setBars(color) {
    var m = document.querySelector('meta[name="theme-color"]'); if (!m || !BARS_FOLLOW_PAGE) return;
    if (color) { if (!m.dataset.base) m.dataset.base = m.getAttribute('content'); m.setAttribute('content', color); }
    else if (m.dataset.base) { m.setAttribute('content', m.dataset.base); delete m.dataset.base; }
  }
  var rgbCtx = null;
  function rgbOf(c) {                                              // any CSS colour -> [r, g, b]
    try {
      rgbCtx = rgbCtx || document.createElement('canvas').getContext('2d');
      rgbCtx.fillStyle = '#121212'; rgbCtx.fillStyle = c;
      var h = rgbCtx.fillStyle;
      if (h.charAt(0) === '#') return [parseInt(h.substr(1, 2), 16), parseInt(h.substr(3, 2), 16), parseInt(h.substr(5, 2), 16)];
      var m = h.match(/[\d.]+/g); return m ? [+m[0], +m[1], +m[2]] : [18, 18, 18];
    } catch (_) { return [18, 18, 18]; }
  }
  // On the music pages the bar keeps the page's tint however far you scroll, never the dark app colour
  var barRaf = 0;
  SP.barsSync = function () {
    if (npIsOpen) return;                                           // the player sets it itself
    var scr = document.getElementById('music-screen');
    var page = scr && scr.classList.contains('active') && mz.theme === 'spotify' ? mzEl('sp-page') : null;
    if (!page) { setBars(null); return; }
    var c = rgbOf(getComputedStyle(page).getPropertyValue('--tint').trim() || '#333');
    setBars('rgb(' + c.join(',') + ')');
  };
  function barsSoon() { if (!barRaf) barRaf = requestAnimationFrame(function () { barRaf = 0; SP.barsSync(); }); }
  function sheet() { return npEl || (npEl = mzEl('sp-np')); }
  function rootEl() { return document.querySelector('#music-screen .wm'); }
  function sheetH() { var n = sheet(); return (n && n.offsetHeight) || window.innerHeight || 800; }
  // While the sheet moves nothing else may take the main thread (the 250 ms sync, the cards, the bar colour): that is what made it stutter
  var npBusy = 0, npY = 0, npCardsT = 0;
  var EASE_OUT = 'cubic-bezier(.32,.72,0,1)', EASE_FLING = 'cubic-bezier(.2,.75,.3,1)';
  function dur(remaining, v, lo, hi) { return Math.round(Math.max(lo, Math.min(hi, remaining / Math.max(Math.abs(v || 0), .9)))); }   // a fast fling finishes fast, a slow release takes its time
  // While a finger drags the sheet its position is written once per frame (touch events can come faster than frames, and each write costs a style update)
  var npRaf = 0, npWant = 0;
  function dragY(px) { npWant = px; if (!npRaf) npRaf = requestAnimationFrame(function () { npRaf = 0; setY(npWant, false); }); }
  function dragFlush() { if (npRaf) { cancelAnimationFrame(npRaf); npRaf = 0; setY(npWant, false); } }
  // Putting a finger on the sheet while it is still sliding catches it where it is (not where it was heading), so it feels like a physical thing
  function sheetFlying() { var n = sheet(); return !!(n && Date.now() < npBusy && n.style.transition && n.style.transition !== 'none'); }
  function catchSheet() {
    var n = sheet(); if (!n) return npY;
    var y = npY; try { y = new DOMMatrixReadOnly(getComputedStyle(n).transform).m42; } catch (_) {}
    clearTimeout(npHideT); npRaf && cancelAnimationFrame(npRaf); npRaf = 0;
    n.style.transition = 'none'; npY = Math.round(y); n.style.transform = 'translate3d(0,' + npY + 'px,0)'; npBusy = Date.now() + 300;
    return npY;
  }
  function setY(px, anim, ms, ease) {
    var n = sheet(); if (!n) return;
    if (anim && npRaf) { cancelAnimationFrame(npRaf); npRaf = 0; }
    npBusy = Date.now() + (anim ? (ms || 420) + 120 : 300);
    n.style.transition = anim ? 'transform ' + (ms || 420) + 'ms ' + (ease || EASE_OUT) : 'none';
    npY = Math.round(px);
    n.style.transform = 'translate3d(0,' + npY + 'px,0)';
  }

  SP.npSet = function (open, animate, vel) {
    var n = sheet(), w = rootEl(); if (!n || !w) return;
    clearTimeout(npHideT);
    if (open) {
      if (!mzCur()) return;
      if (!npIsOpen) mzHaptic('open');
      npIsOpen = true;
      n.style.visibility = 'visible'; n.setAttribute('aria-hidden', 'false'); w.classList.add('np-open');
      if (animate) npBusy = Date.now() + 560;                      // the cards and tint wait until the slide has finished
      npSync();                                                    // (already done when the drag began; a full redo here was a hitch at the start of the slide)
      if (animate && !n.classList.contains('shown')) { setY(sheetH(), false); void n.offsetHeight; }   // start from just below the screen
      if (!n.classList.contains('shown')) { var sc0 = mzEl('sp-np-scroll'); if (sc0) sc0.scrollTop = 0; }       // always opens at the player, not where you left the cards
      n.classList.add('shown');
      if (vel) setY(0, animate, dur(npY, vel, 200, 420), EASE_FLING); else setY(0, animate, animate && npY && npY < sheetH() * .6 ? dur(npY, 0, 240, 380) : 0);
      clearInterval(npTimer); npTimer = setInterval(function () { if (Date.now() >= npBusy) npSync(); }, 250);
    } else {
      if (!npIsOpen && sheetFlying()) return;                      // already on its way down (a swipe closed it, then the history step calls this too): restarting the slide here made it stop and ease again mid-way
      if (npIsOpen) mzHaptic('close');
      npIsOpen = false; SP.qSet(false, false); setTimeout(SP.barsSync, 80);
      w.classList.remove('np-open'); n.setAttribute('aria-hidden', 'true'); clearInterval(npTimer);
      var ms = vel ? dur(sheetH() - npY, vel, 180, 400) : 420;
      setY(sheetH(), animate, ms, vel ? EASE_FLING : EASE_OUT);
      npHideT = setTimeout(function () { n.style.visibility = 'hidden'; n.classList.remove('shown'); }, animate ? ms + 30 : 0);
    }
  };
  SP.justDragged = function () { return Date.now() - lastDragAt < 400; };
  // ─── queue sheet ───────────────────────────────────────
  // Lives over the player: swipe up on the player (or press the queue button) to pull it up, swipe down on its header to put it away.
  // Rows swipe right to remove.
  var qEl = null, qIsOpen = false, qSig = '', swipeAt = 0;
  function qSheet() { return qEl || (qEl = mzEl('sp-q')); }
  var qVel = 0;                                                  // how fast the finger was moving when it let go of the queue (px/ms), so a flick closes it fast
  function qSetY(px, anim, ms, ease) {
    var q = qSheet(); if (!q) return;
    q.style.transition = anim ? 'transform ' + (ms || 420) + 'ms ' + (ease || EASE_OUT) : 'none';
    q.style.transform = 'translate3d(0,' + Math.round(px) + 'px,0)';
  }
  function qRows() {
    var cur = mzCur();
    function row(t, i, playing) {
      return '<div class="sp-qi" data-c="' + i + '">' + (playing ? '' : '<div class="sp-qi-del">Remove</div>') +
        '<div class="sp-qi-row' + (playing ? ' playing' : '') + '" data-act="q-jump" data-c="' + i + '" data-t="' + esc(t.f) + '">' + trackCov(t, 100, 'sm') +
        '<div class="tt"><b>' + esc(t.t) + '</b><small>' + esc(t.ar) + '</small></div><time>' + mzFmt(t.d) + '</time></div></div>';
    }
    if (!cur) return '<div class="sp-q-empty">Nothing in the queue</div>';
    var next = mz.queue.slice(mz.qi + 1, mz.qi + 201);
    return '<h3>Now playing</h3>' + row(cur, mz.qi, true) +
      (next.length ? '<h3>Next in queue</h3>' + next.map(function (t, n) { return row(t, mz.qi + 1 + n, false); }).join('') : '<div class="sp-q-empty">Nothing up next</div>');
  }
  function qSignature() { return mz.qi + ':' + mz.queue.length + ':' + (mz.queue[mz.qi] ? mz.queue[mz.qi].f : '') + ':' + (mz.queue[mz.qi + 1] ? mz.queue[mz.qi + 1].f : ''); }
  function qRender() {
    var list = mzEl('sp-q-list'); if (!list) return;
    qSig = qSignature(); list.innerHTML = qRows();
  }
  SP.qSet = function (open, animate) {
    var q = qSheet(); if (!q) return;
    if (open) {
      if (!qIsOpen) mzHaptic('open');
      qRender();
      q.style.visibility = 'visible'; q.setAttribute('aria-hidden', 'false');
      if (animate && !qIsOpen) { qSetY(window.innerHeight, false); void q.offsetHeight; }
      qIsOpen = true; qSetY(0, animate);
    } else {
      if (qIsOpen) mzHaptic('close');
      var cms = qVel ? dur(window.innerHeight * .6, qVel, 180, 400) : 420, cease = qVel ? EASE_FLING : EASE_OUT; qVel = 0;
      qIsOpen = false; q.setAttribute('aria-hidden', 'true'); qSetY(window.innerHeight, animate, cms, cease);
      setTimeout(function () { if (!qIsOpen) q.style.visibility = 'hidden'; }, animate ? cms + 30 : 0);
    }
  };
  SP.npQueue = function () { navSet('music/queue'); SP.qSet(true, true); };
  // ─── desktop queue panel: a column beside the page that the queue button shows and hides (it stays open while you browse) ───
  var qpSig = '', qpCur = '', qpMax = 60;                            // the panel lists 60 up-next songs, "Show more" adds 60 (a queue can hold thousands)
  function qpOpen() { return mz.theme === 'spotify' && !!mz.prefs.qp && !(typeof mzIsMobile === 'function' && mzIsMobile()); }
  function qpRow(t, i) {
    var on = i === mz.qi;
    return '<div class="sp-qp-row' + (on ? ' playing' : '') + '" data-act="q-jump" data-c="' + i + '" data-t="' + esc(t.f) + '">' + trackCov(t, 100, 'sm') +
      '<div class="tt"><b>' + esc(t.t) + '</b><small>' + esc(t.ar) + '</small></div><time>' + mzFmt(t.d) + '</time></div>';
  }
  SP.qpSync = function () {
    var w = document.querySelector('#music-screen .wm'); if (!w) return;
    var on = qpOpen(); w.classList.toggle('qp-open', on);
    var b = mzEl('wm-npbtn'); if (b) { b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); }
    var list = mzEl('sp-qp-list'); if (!on || !list) return;
    var next = mz.queue.slice(mz.qi + 1, mz.qi + 1 + qpMax);
    var sig = mz.qi + ':' + mz.queue.length + ':' + qpMax + ':' + (mz.queue[mz.qi] ? mz.queue[mz.qi].f : '') + ':' + next.map(function (t) { return t.f; }).join(',');   // a reorder further down the list counts too
    if (sig === qpSig) return;
    qpSig = sig;
    var cur = mzCur();
    if (!cur) { list.innerHTML = '<div class="sp-qp-empty">Nothing in the queue</div>'; return; }
    var left = mz.queue.length - (mz.qi + 1) - next.length, keep = qpCur === cur.f ? list.scrollTop : 0;   // a new song starts the list from the top again
    qpCur = cur.f;
    list.innerHTML = '<h3>Now playing</h3>' + qpRow(cur, mz.qi) +
      (next.length ? '<h3>Next in queue</h3>' + next.map(function (t, n) { return qpRow(t, mz.qi + 1 + n); }).join('') : '<div class="sp-qp-empty">Nothing up next</div>') +
      (left > 0 ? '<button class="sp-qp-more" data-act="sp-qp-more">Show ' + Math.min(left, 60) + ' more (' + left + ' left)</button>' : '');
    list.scrollTop = keep;
  };
  window.addEventListener('resize', function () { if (typeof SP !== 'undefined' && SP.qpSync) SP.qpSync(); });   // the panel appears/disappears at the 760px breakpoint
  SP.qpToggle = function () { mz.prefs.qp = !mz.prefs.qp; qpMax = 60; mzSavePrefs(); qpSig = ''; SP.qpSync(); };
  SP.qpMore = function () { qpMax += 60; SP.qpSync(); };
  SP.npBtn = function () {                                         // the queue button: the panel on a desktop, the page elsewhere
    if (mz.theme === 'spotify' && !(typeof mzIsMobile === 'function' && mzIsMobile())) SP.qpToggle(); else mzGo('now');
  };
  SP.qClose = function () {
    if (nav.cur === 'music/queue' && navCanBack()) { history.back(); return; }      // the back gesture does the same, so history stays in step
    SP.qSet(false, true); navReplace('music/player');
  };
  SP.qOpen = function () { return qIsOpen; };
  function qRemove(c) {
    var t = mz.queue[c]; if (!t || c === mz.qi) return;
    mzHaptic('tick');
    if (mz.remote) mzCmd('qremove', t.f);
    else { mz.queue.splice(c, 1); if (c < mz.qi) mz.qi--; mzSaveState(true); }
    qRender();
  }
  function qBind() {
    var list = mzEl('sp-q-list'), head = mzEl('sp-q-head'), q = qSheet(); if (!list || !q) return;
    list.addEventListener('click', function (e) { if (Date.now() - swipeAt < 350) { e.stopPropagation(); e.preventDefault(); } }, true);   // a swipe is not a tap
    // swipe a row right to remove it (the same direction as the other row swipes)
    var s = null;
    list.addEventListener('pointerdown', function (e) {
      var row = e.target.closest('.sp-qi-row'); if (!row || row.classList.contains('playing') || (e.pointerType === 'mouse' && e.button !== 0)) return;
      s = { row: row, id: e.pointerId, x0: e.clientX, y0: e.clientY, dx: 0, lock: '', last: { x: e.clientX, t: performance.now() }, v: 0 };
    });
    list.addEventListener('pointermove', function (e) {
      if (!s || e.pointerId !== s.id) return;
      var dx = e.clientX - s.x0, dy = e.clientY - s.y0;
      if (!s.lock) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        if (Math.abs(dx) > Math.abs(dy) * 1.2 && dx > 0) { s.lock = 'x'; try { s.row.setPointerCapture(s.id); } catch (_) {} }
        else { s = null; return; }                                  // vertical (scrolling) or leftwards: leave it to the browser
      }
      var now = performance.now();
      s.v = 0.6 * s.v + 0.4 * ((e.clientX - s.last.x) / Math.max(1, now - s.last.t)); s.last = { x: e.clientX, t: now };
      s.dx = Math.max(0, dx); s.row.style.transition = 'none'; s.row.style.transform = 'translate3d(' + s.dx + 'px,0,0)';
    });
    function done(e, cancelled) {
      if (!s || e.pointerId !== s.id) return;
      var d = s; s = null;
      if (d.lock !== 'x') return;
      swipeAt = Date.now();
      try { d.row.releasePointerCapture(d.id); } catch (_) {}
      var w = d.row.offsetWidth || 300;
      if (!cancelled && (d.dx > w * 0.35 || d.v > 0.6)) {
        d.row.style.transition = 'transform .2s ease-out'; d.row.style.transform = 'translate3d(' + w + 'px,0,0)';
        var c = parseInt(d.row.dataset.c, 10);
        setTimeout(function () { qRemove(c); }, 190);
      } else { d.row.style.transition = 'transform .25s cubic-bezier(.32,.72,0,1)'; d.row.style.transform = ''; }
    }
    list.addEventListener('pointerup', function (e) { done(e, false); });
    list.addEventListener('pointercancel', function (e) { done(e, true); });
    // pull the list down while it is scrolled to the top: the whole sheet follows your finger and goes away
    var tp = null;
    list.addEventListener('touchstart', function (e) {
      tp = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY, drag: false, v: 0, t0: performance.now(), last: { y: e.touches[0].clientY, t: performance.now() } } : null;
    }, { passive: true });
    list.addEventListener('touchmove', function (e) {
      if (!tp) return;
      var t = e.touches[0], dy = t.clientY - tp.y, dx = t.clientX - tp.x;
      if (!tp.drag) {
        if (list.scrollTop > 0 || dy < 10 || Math.abs(dy) < Math.abs(dx) * 1.2) { if (dy < -4 || list.scrollTop > 0) tp = null; return; }
        tp.v = dy / Math.max(16, performance.now() - tp.t0); tp.drag = true; tp.y = t.clientY - 10;      // measure from where the drag actually began, keeping the speed so far
        dy = 10;
      }
      e.preventDefault();
      var now = performance.now(); tp.v = 0.6 * tp.v + 0.4 * ((t.clientY - tp.last.y) / Math.max(1, now - tp.last.t)); tp.last = { y: t.clientY, t: now };
      qSetY(Math.max(0, dy), false);
    }, { passive: false });
    function tend(e) {
      if (!tp || !tp.drag) { tp = null; return; }
      var d = tp, t = e.changedTouches[0]; tp = null; swipeAt = Date.now();
      var dy = t.clientY - d.y, h = q.offsetHeight || window.innerHeight;
      if (e.type !== 'touchcancel' && (dy > h * 0.18 || d.v > 0.5)) { qVel = d.v; SP.qClose(); } else qSetY(0, true, dur(dy, 0, 200, 340), EASE_OUT);
    }
    list.addEventListener('touchend', tend); list.addEventListener('touchcancel', tend);
    // swipe the header down to put the queue away
    var g = null;
    head.addEventListener('pointerdown', function (e) {
      if (e.target.closest('button') || (e.pointerType === 'mouse' && e.button !== 0)) return;
      g = { id: e.pointerId, y0: e.clientY, last: { y: e.clientY, t: performance.now() }, v: 0, moved: false };
      try { head.setPointerCapture(e.pointerId); } catch (_) {}
    });
    head.addEventListener('pointermove', function (e) {
      if (!g || e.pointerId !== g.id) return;
      var dy = e.clientY - g.y0; if (!g.moved && Math.abs(dy) < 6) return; g.moved = true;
      var now = performance.now(); g.v = 0.6 * g.v + 0.4 * ((e.clientY - g.last.y) / Math.max(1, now - g.last.t)); g.last = { y: e.clientY, t: now };
      qSetY(Math.max(0, dy), false);
    });
    function hend(e, cancelled) {
      if (!g || e.pointerId !== g.id) return;
      var d = g; g = null; if (!d.moved) return;
      var dy = e.clientY - d.y0, h = q.offsetHeight || window.innerHeight;
      if (!cancelled && (dy > h * 0.18 || d.v > 0.5)) { qVel = d.v; SP.qClose(); } else qSetY(0, true, dur(dy, 0, 200, 340), EASE_OUT);
    }
    head.addEventListener('pointerup', function (e) { hend(e, false); });
    head.addEventListener('pointercancel', function (e) { hend(e, true); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', qBind); else qBind();

  // keep the sheet's contents in step with playback (local, or mirrored from another device)
  // what the file is: format, bitrate, and for lossless the sample rate / bit depth (a small line under the controls)
  var LOSSLESS = { flac: 1, wav: 1, alac: 1, aiff: 1, aif: 1, ape: 1, wv: 1 };
  // the album / playlist / artist / Liked Songs that is playing right now gets a green title and the little equaliser, wherever it is listed
  // desktop playlist: ctrl/cmd-click and shift-click pick several songs; a small bar moves or removes them, and dragging one drags them all
  var dsel = { pid: null, ids: new Set(), last: null };
  SP.dselSync = function () {
    var bar = document.getElementById('sp-dsel');
    if (dsel.pid && (mz.theme !== 'spotify' || mz.view.type !== 'playlist' || mz.view.key !== dsel.pid)) { dsel.pid = null; dsel.ids = new Set(); dsel.last = null; }
    if (edit) return;
    var rows = document.querySelectorAll('#wm-content .sp-row.trk[data-t]');
    Array.prototype.forEach.call(rows, function (r) { r.classList.toggle('esel', dsel.ids.has(r.dataset.t)); });
    if (!dsel.ids.size) { if (bar) bar.remove(); return; }
    if (!bar) { bar = document.createElement('div'); bar.id = 'sp-dsel'; bar.className = 'sp-dsel'; (document.getElementById('music-screen') || document.body).appendChild(bar); }
    bar.innerHTML = '<span>' + dsel.ids.size + ' selected</span><button data-act="sp-dsel-top">Move to top</button><button data-act="sp-dsel-bottom">Move to bottom</button><button class="rm" data-act="sp-dsel-rm">Remove</button><button data-act="sp-dsel-none">Clear</button>';
  };
  function dselApply(kind) {
    var pid = dsel.pid, ids = mz.plCache[pid]; if (!pid || !ids) return;
    var chosen = ids.filter(function (id) { return dsel.ids.has(id); }), others = ids.filter(function (id) { return !dsel.ids.has(id); });
    var next = kind === 'top' ? chosen.concat(others) : kind === 'bottom' ? others.concat(chosen) : others;
    if (kind === 'rm') { dsel.ids = new Set(); dsel.last = null; }
    mz.plCache[pid] = next; mzRender();
    jpost('/api/music/playlist/' + encodeURIComponent(pid) + '/order', { ids: next, base: ids.length }).catch(function (err) {
      if (/changed elsewhere/.test(err.message || '')) { delete mz.plCache[pid]; mzToast('This playlist changed elsewhere. Reloaded it'); }
      else { mz.plCache[pid] = ids; mzToast('Could not save the new order'); }
      mzRender();
    });
  }
  window.addEventListener('click', function (e) {
    if (mz.theme !== 'spotify' || mz.view.type !== 'playlist' || edit || !e.target.closest) return;
    var bt = e.target.closest('#sp-dsel button');
    if (bt) { e.stopPropagation(); e.preventDefault(); var k = bt.dataset.act.slice(8); if (k === 'none') { dsel.ids = new Set(); dsel.last = null; SP.dselSync(); } else dselApply(k); return; }
    if (typeof mzIsMobile === 'function' && mzIsMobile()) return;
    var row = e.target.closest('#wm-content .sp-row.trk[data-t]');
    if (!row || e.target.closest('button, input, .star, .sp-lk') || !(e.ctrlKey || e.metaKey || e.shiftKey)) return;
    e.stopPropagation(); e.preventDefault();
    var id = row.dataset.t;
    if (dsel.pid !== mz.view.key) dsel = { pid: mz.view.key, ids: new Set(), last: null };
    if (e.shiftKey && dsel.last) {
      var all = Array.prototype.map.call(document.querySelectorAll('#wm-content .sp-row.trk[data-t]'), function (r) { return r.dataset.t; });
      var a0 = all.indexOf(dsel.last), b0 = all.indexOf(id);
      if (a0 >= 0 && b0 >= 0) all.slice(Math.min(a0, b0), Math.max(a0, b0) + 1).forEach(function (x) { dsel.ids.add(x); });
    } else { if (dsel.ids.has(id)) dsel.ids.delete(id); else dsel.ids.add(id); dsel.last = id; }
    SP.dselSync();
  }, true);
  SP.npRefresh = function () { if (npIsOpen && mzCur() && sheet()) npSync(); };
  SP.npPlayIcon = function (playing) { var b = sheet() && mzEl('sp-np-play'); if (b && npLast.playing !== playing) { npLast.playing = playing; b.innerHTML = playing ? NP.pause : NP.play; } };
  SP.markCtx = function () {
    var root = mzEl('music-screen'); if (!root) return;
    Array.prototype.forEach.call(root.querySelectorAll('.playing-ctx'), function (e) { e.classList.remove('playing-ctx'); });
    var c = mz.playCtx; if (!c || !mzCur()) return;
    Array.prototype.forEach.call(root.querySelectorAll('[data-k][data-v]'), function (e) {
      if (e.dataset.k === c.k && e.dataset.v === c.v && e.tagName !== 'BUTTON' && !e.closest('button, .sp-rx')) e.classList.add('playing-ctx');
    });
  };
  SP.npQualRefresh = function () { var t = mzCur(); npQual(t); };
  // what is playing, as a little badge: the converted MP3 when the server is streaming a lower rate, otherwise the file itself
  function qualHtml(t) {
    var fmt = String(t && t.sx || '').toLowerCase();
    if (!fmt) return '';
    var rate = typeof mzQualityRate === 'function' ? mzQualityRate() : 0, parts = [];
    var sv = mz.served && mz.served.f === t.f ? mz.served.h : '', m = /^mp3-(\d+)$/.exec(sv);   // the server's own word on what it sent
    if (sv === 'original') rate = 0; else if (m) rate = +m[1];
    if (rate) return '<span class="sp-q-fmt">MP3</span><span class="sp-q-txt">' + rate + ' kbps \u2022 from ' + esc(fmt.toUpperCase()) + '</span>';
    if (LOSSLESS[fmt]) parts.push('Lossless');
    if (t.br) parts.push(t.br + ' kbps');
    return '<span class="sp-q-fmt">' + esc(fmt.toUpperCase()) + '</span>' + (parts.length ? '<span class="sp-q-txt">' + esc(parts.join(' \u2022 ')) + '</span>' : '');
  }
  function npQual(t) {                                             // the phone's full-screen player and the desktop player bar
    ['sp-np-qual', 'wm-qual'].forEach(function (id) {
      var el = mzEl(id); if (!el) return;
      var h = t ? qualHtml(t) : '';
      el.hidden = !h;
      if (h && el.dataset.h !== h) { el.dataset.h = h; el.innerHTML = h; }
    });
  }

  // "Playing from …" follows what the queue was started from (playlist, artist, Liked Songs), falling back to the song's album
  function npFrom(t) {
    var c = mz.playCtx, k = 'album', v = t.li, name = t.al || t.t, what = 'album', act = 'np-album';
    if (c && c.k === 'playlist') { var pl = mz.playlists.filter(function (x) { return x.id === c.v; })[0]; if (pl) { what = 'playlist'; name = pl.name; act = 'playlist'; v = pl.id; } }
    else if (c && c.k === 'artist') { var ar = mz.artists.get(c.v); if (ar) { what = 'artist'; name = ar.name; act = 'np-artist'; v = ar.id; } }
    else if (c && c.k === 'liked') { what = 'playlist'; name = 'Liked Songs'; act = 'nav'; v = 'favorites'; }
    var key = what + '|' + name + '|' + v;
    if (npLast.from === key) return; npLast.from = key;
    var box = mzEl('sp-np-from'); box.parentNode.querySelector('small').textContent = 'Playing from ' + what;
    box.innerHTML = v ? '<a class="npl" data-act="' + act + '" data-v="' + esc(v) + '">' + esc(name) + '</a>' : esc(name);
  }

  function npSync(force) {
    var t = mzCur(), n = sheet(); if (!t || !n) return;
    npFrom(t);
    if (force === true || npTrack !== t.f) {
      npTrack = t.f; npLast = {};
      mzEl('sp-np-title').innerHTML = t.li ? '<a class="npl" data-act="np-album" data-v="' + esc(t.li) + '">' + esc(t.t) + '</a>' : esc(t.t);
      mzEl('sp-np-artist').innerHTML = mzArtistLinks(t, 'npl', 'np-artist');
      var artBox = mzEl('sp-np-art');
      artBox.innerHTML = cov(t.c, t.h, t.al || t.t, 640, '');
      var big = artBox.querySelector('img');
      if (big && !big.complete) {                                  // not in the cache yet: the small picture (already fetched for the mini player) stands in, and the sharp one fades over it
        var wm = artBox.firstChild; if (wm && t.c) wm.style.background = 'center / cover url("' + mzCoverUrl(t.c, 160) + '")';
        big.style.opacity = '0';
        big.addEventListener('load', function () { big.style.transition = 'opacity .16s ease-out'; big.style.opacity = '1'; }, { once: true });
      }
      lyrLoad(t); npQual(t);
      clearTimeout(npCardsT);
      if (Date.now() < npBusy) npCardsT = setTimeout(function () { var c = mzCur(); if (c && npTrack === c.f) npCards(c); }, Math.max(0, npBusy - Date.now()) + 40);
      else npCards(t);
    }
    if (qIsOpen && qSig !== qSignature()) qRender();
    var bar = getComputedStyle(rootEl()).getPropertyValue('--sp-mini').trim();        // the cover's tint arrives a moment after the song changes
    if (bar && npLast.bar !== bar) { npLast.bar = bar; setBars(bar); }
    var playing = mz.remote ? !!(mz.rs && mz.rs.st.playing) : !!(musicAudio && !musicAudio.paused);
    if (npLast.playing !== playing) { npLast.playing = playing; mzEl('sp-np-play').innerHTML = playing ? NP.pause : NP.play; }
    var fav = !!(t.fav || t.inpl || (mz.inPl && mz.inPl.has(t.f)));                                 // a tick when the song is liked or in any playlist
    if (npLast.fav !== fav) { npLast.fav = fav; var h = mzEl('sp-np-heart'); h.innerHTML = fav ? NP.liked : NP.like; h.classList.toggle('on', fav); }
    mzEl('sp-np-shuffle').classList.toggle('on', !!mz.shuffle);
    var rep = mz.repeat;
    if (npLast.rep !== rep) { npLast.rep = rep; var r = mzEl('sp-np-repeat'); r.innerHTML = rep === 'one' ? MZ_ICON.repeatOne : MZ_ICON.repeat; r.classList.toggle('on', rep !== 'off'); }
    var rem = mz.remote ? 'Listening on ' + mzDevLabel(mz.activeId) : '';
    if (npLast.rem !== rem) { npLast.rem = rem; mzEl('sp-np-remote').textContent = rem; mzEl('sp-np-dev').classList.toggle('on', !!rem); }
    if (!mz.seeking) {
      var pos = mz.remote ? mzRemotePos() : (musicAudio ? musicAudio.currentTime : 0);
      var dur = mz.remote ? t.d : ((musicAudio && isFinite(musicAudio.duration) && musicAudio.duration) || t.d);
      var sk = mzEl('sp-np-seek');
      if (dur) { var pct = Math.min(100, pos / dur * 100); sk.value = Math.round(pct * 10); sk.style.setProperty('--p', pct + '%'); }
      mzEl('sp-np-cur').textContent = mzFmt(pos); mzEl('sp-np-dur').textContent = mzFmt(dur);
    }
    lyrSync();
  }

  // ─── "Add to playlist" sheet (the + on the phone player, and a long press on a track in a playlist) ───
  // Every row is a toggle that stays open: a green tick means the song is in it, tapping flips it (and writes to Navidrome).
  function jpost(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { if (!r.ok) throw new Error(d.error || ''); return d; }); });
  }
  var TICK = '<span class="sp-addchk"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12.5 10 17.5 19 7.5"/></svg></span>';


  // ─── the cards under the player: About the artist, Credits ───────────────────────────────────
  function fetchAbout(id, cb) {
    if (aboutCache[id]) { cb(aboutCache[id]); return; }
    fetch('/api/music/artist/' + encodeURIComponent(id)).then(function (r) { return r.json(); }).then(function (d) { if (d && !d.error) { aboutCache[id] = d; cb(d); } }).catch(function () {});
  }
  function roleLabel(r) { return String(r || '').replace(/[_-]+/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); }); }
  // ─── lyrics: a card under the controls; synced lines light up as the song plays, and tapping a line jumps there ───
  var lyr = null, lyrCache = {};
  function lyrLoad(t) {
    var box = mzEl('sp-npl'); if (!box) return;
    function off() { box.firstChild.textContent = ''; box.dataset.i = ''; lyr = null; }
    if (mz.prefs.lyr === false) { off(); return; }                 // switched off in the player's ⋮ menu
    function show(d) {
      var c = mzCur(); if (!c || c.f !== t.f) return;
      if (!d || !d.synced || !d.lines || !d.lines.length) { off(); return; }            // one live line needs timestamps
      box.firstChild.textContent = '';
      lyr = { f: t.f, synced: true, lines: d.lines, idx: -2, user: 0, body: 'sp-npl' };
      lyrSync(true);
    }
    off();
    if (t.f in lyrCache) { show(lyrCache[t.f]); return; }
    fetch('/api/music/lyrics/' + encodeURIComponent(t.f)).then(function (r) { return r.json(); }).then(function (d) { lyrCache[t.f] = d; show(d); }).catch(function () {});
  }
  function lyrSync(force) {
    if (!lyr || !lyr.synced) return;
    var t = mzCur(); if (!t || t.f !== lyr.f) return;
    var ms = (mz.remote ? mzRemotePos() : (musicAudio ? musicAudio.currentTime : 0)) * 1000 + 250, L = lyr.lines, lo = 0, hi = L.length - 1, idx = -1;
    while (lo <= hi) { var mid = (lo + hi) >> 1; if (L[mid][0] <= ms) { idx = mid; lo = mid + 1; } else hi = mid - 1; }
    if (idx === lyr.idx && !force) return;
    if (lyr.body === 'sp-npl') {                                  // the player: only the line being sung, between the cover and the title
      var one = mzEl('sp-npl'); if (!one) return;
      lyr.idx = idx;
      var txt = idx >= 0 ? L[idx][1] : '';
      if (one.dataset.i === String(idx) && !force) return;
      one.dataset.i = idx; one.firstChild.textContent = txt;
      one.classList.remove('in'); void one.offsetWidth; one.classList.add('in');
      return;
    }
    var body = mzEl(lyr.body); if (!body) return;
    var old = body.querySelector('p.on'); if (old) old.classList.remove('on');
    var cur = idx >= 0 ? body.children[idx] : null;
    if (cur) cur.classList.add('on');
    lyr.idx = idx;
    if (cur && Date.now() - lyr.user > 3500) body.scrollTo({ top: Math.max(0, cur.offsetTop - body.clientHeight / 2 + cur.offsetHeight / 2), behavior: force ? 'auto' : 'smooth' });
  }

  // desktop: a full lyrics page (the lines button in the player bar)
  var lyrTick = 0, lyrPageF = '';
  function lyricsView() {
    var t = mzCur();
    if (!t) return { html: '<div class="sp-page"><div class="sp-pbody"><div class="sp-empty"><h2>Nothing playing</h2><p>Play a song to see its lyrics.</p></div></div></div>', hue: 230 };
    lyrPageF = t.f;
    setTimeout(function () { lyrPage(t); lyrWatch(); }, 0);
    return { html: '<div class="sp-page sp-lyricspage" id="sp-page"><div class="sp-pbody"><div class="sp-lv-top">' + cov(t.c, t.h, t.al || t.t, 240, '') +
      '<div><h1>' + esc(t.t) + '</h1><p>' + esc(t.ar || '') + '</p></div></div><div class="sp-lv-body" id="sp-lv-body"><p class="sp-lv-msg">Loading lyrics…</p></div></div></div>', tint: t.c, hue: mzHue(t.ar || t.t) };
  }
  function lyrPage(t) {
    function show(d) {
      var body = mzEl('sp-lv-body'); if (!body || mz.view.type !== 'lyrics') return;
      var c = mzCur(); if (!c || c.f !== t.f) return;
      if (!d || !d.lines || !d.lines.length) { lyr = null; body.innerHTML = '<p class="sp-lv-msg">No lyrics for this song.</p>'; return; }
      body.classList.toggle('plain', !d.synced);
      body.innerHTML = d.lines.map(function (l, i) { return '<p' + (d.synced ? ' data-act="sp-lyr-seek" data-ms="' + l[0] + '"' : '') + ' data-i="' + i + '">' + (esc(l[1]) || '&nbsp;') + '</p>'; }).join('');
      lyr = { f: t.f, synced: !!d.synced, lines: d.lines, idx: -2, user: 0, body: 'sp-lv-body' };
      ['wheel', 'touchstart'].forEach(function (ev) { body.addEventListener(ev, function () { if (lyr) lyr.user = Date.now(); }, { passive: true }); });
      lyrSync(true);
    }
    if (t.f in lyrCache) { show(lyrCache[t.f]); return; }
    fetch('/api/music/lyrics/' + encodeURIComponent(t.f)).then(function (r) { return r.json(); }).then(function (d) { lyrCache[t.f] = d; show(d); }).catch(function () { show(null); });
  }
  function lyrWatch() {
    if (lyrTick) return;
    lyrTick = setInterval(function () {
      if (mz.view.type !== 'lyrics') { clearInterval(lyrTick); lyrTick = 0; return; }
      var c = mzCur();
      if (c && c.f !== lyrPageF) mzRender(); else lyrSync();                   // a new song: rebuild the page; otherwise just move the highlight
    }, 300);
  }
  SP.lyricsToggle = function () { if (mz.view.type === 'lyrics') history.back(); else mzGo('lyrics'); };

  function npCards(t) {
    var box = mzEl('sp-np-cards'); if (!box) return;
    var cr = mzCredits(t), main = mz.artists.get(cr[0].id), html = '';
    if (main) {
      var photo = artistImg(main, 900), fb = t.c ? mzCoverUrl(t.c, 700) : '';
      var img = photo ? '<img alt="" src="' + esc(photo) + '"' + (fb ? ' data-fb="' + esc(fb) + '"' : '') + ' onerror="' + IMG_FALLBACK + '">' : fb ? '<img alt="" src="' + esc(fb) + '" onerror="this.remove()">' : '';
      html += '<section class="sp-npc"><div class="sp-aimgwrap" data-act="np-artist" data-v="' + esc(main.id) + '">' + img + '<span class="sp-aboutlabel">About the artist</span></div>' +
        '<div class="sp-abody"><div class="sp-arow"><div class="sp-aname"><b>' + esc(main.name) + '</b><small>' + esc(plural(main.tracks.length, 'song')) + ' in your library</small></div>' + '</div>' +
        '<p class="sp-abio" id="sp-np-bio" data-aid="' + esc(main.id) + '"></p></div></section>';
    }
    // credits: the credited artists first, then composers, lyricists and the like (an artist who is both gets one row)
    var rows = [], byId = {};
    cr.forEach(function (c) { var r = { id: c.id, name: c.name, roles: ['Main Artist'], main: true }; rows.push(r); byId[c.id] = r; });
    (t.co || []).forEach(function (c) {
      var r = byId[c[0]];
      if (!r) { r = { id: c[0], name: c[1], roles: [] }; rows.push(r); byId[c[0]] = r; }
      var lab = roleLabel(c[2]); if (lab && r.roles.indexOf(lab) < 0) r.roles.push(lab);
    });
    if (rows.length) {
      var shown = mz.spCreditsAll ? rows : rows.slice(0, 4);
      html += '<section class="sp-npc sp-credits"><div class="sp-credits-h"><b>Credits</b>' + (rows.length > 4 ? '<a data-act="sp-creditsall">' + (mz.spCreditsAll ? 'Show less' : 'Show all') + '</a>' : '') + '</div>' +
        shown.map(function (r) {
          var known = mz.artists.get(r.id);
          return '<div class="sp-crow"><div class="sp-ct"><b' + (known ? ' class="link" data-act="np-artist" data-v="' + esc(r.id) + '"' : '') + '>' + esc(r.name) + '</b><small>' + esc(r.roles.join(' • ')) + '</small></div>' + '</div>';
        }).join('') + '</section>';
    }
    box.innerHTML = html;
    if (main) fetchAbout(main.id, function (d) {
      var el = mzEl('sp-np-bio'); if (!el || el.dataset.aid !== main.id) return;                    // the song changed while this was loading
      var bio = d.bio || ''; el.textContent = bio.length > 260 ? bio.slice(0, 260).replace(/\s+\S*$/, '') + '…' : bio;
    });
  }

  // ─── menu sheets: the ⋯ menu, the device picker and the settings menu on a phone ─────────────────
  // Same look and behaviour as the Add to playlist sheet: it slides up over a dimmed page, follows your finger when you swipe down,
  // closes on a tap outside, on Escape and on the Back gesture. Actions run after it has closed, so ones that navigate leave nothing behind.
  function mi(d, fill) { return '<svg viewBox="0 0 24 24" width="24" height="24" fill="' + (fill || 'none') + '" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>'; }
  var MI = {
    heart: I.heartOff.replace('width="16" height="16"', 'width="24" height="24"'), heartOn: I.heartOn.replace('width="16" height="16"', 'width="24" height="24"'),
    plus: mi('<circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>'),
    queue: mi('<line x1="4" y1="6" x2="15" y2="6"/><line x1="4" y1="12" x2="15" y2="12"/><line x1="4" y1="18" x2="10" y2="18"/><line x1="18" y1="14" x2="18" y2="20"/><line x1="15" y1="17" x2="21" y2="17"/>'),
    next: mi('<polygon points="5 4 15 12 5 20"/><line x1="19" y1="5" x2="19" y2="19"/>'),
    album: mi('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.6"/>'),
    person: mi('<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.2 3.6-6.5 8-6.5s8 2.3 8 6.5"/>'),
    remove: mi('<circle cx="12" cy="12" r="9"/><line x1="8" y1="12" x2="16" y2="12"/>'),
    tick: mi('<polyline points="5 12.5 10 17.5 19 7"/>')
  };
  SP.menuSheet = function (o) {
    var at = SP.menuAt; SP.menuAt = null;                                         // set by a right-click: on a wide screen the menu opens where the pointer is
    if (at && !o.at && Date.now() - at.t < 300) o.at = at;
    var old = mzEl('sp-msheet');
    if (old) { if (old._close) old._close(); setTimeout(function () { SP.menuSheet(o); }, 330); return; }   // one at a time: let the first one finish leaving
    mzHaptic('open');
    var items = o.items || [];
    var rows = items.map(function (it, i) {
      if (it.sep) return '<div class="sp-addsep"></div>';
      if (it.info) return '<div class="sp-mrow info"><span class="sp-mt"><small>' + esc(it.label) + '</small></span></div>';
      return '<div class="sp-mrow' + (it.on ? ' on' : '') + '" role="button" tabindex="0" data-i="' + i + '">' + (it.icon || '') +
        '<span class="sp-mt"><b>' + esc(it.label) + '</b>' + (it.sub ? '<small>' + esc(it.sub) + '</small>' : '') + '</span>' + (o.checks && it.on ? '<span class="sp-mtick">' + MI.tick + '</span>' : '') + '</div>';
    }).join('');
    var el = document.createElement('div'); el.id = 'sp-msheet'; el.className = 'sp-addsheet sp-msheet';
    el.innerHTML = '<div class="sp-addback"></div><div class="sp-addpanel" role="dialog" aria-modal="true" aria-label="' + esc(o.title || 'Options') + '"><div class="sp-addtop"><div class="sp-addgrab"></div>' +
      (o.head || (o.title ? '<div class="sp-addhead">' + esc(o.title) + '</div>' : '')) + '</div><div class="sp-addscroll">' + rows + (o.body || '') + '</div></div>';
    var pop = !!o.at && !mzIsMobile();
    if (pop) el.classList.add('sp-pop');
    (rootEl() || document.body).appendChild(el);
    if (o.mount) o.mount(el);
    var panel = el.querySelector('.sp-addpanel'), scroller = el.querySelector('.sp-addscroll');
    if (pop) {                                                                    // beside the pointer, kept inside the window
      panel.style.left = Math.max(8, Math.min(o.at.x, innerWidth - panel.offsetWidth - 8)) + 'px';
      panel.style.top = Math.max(8, Math.min(o.at.y, innerHeight - panel.offsetHeight - 8)) + 'px';
    }
    var closing = false, openedAt = Date.now(), swipedAt = 0, lastScroll = 0;
    var entry = mzSheetOpenEntry(function () { hide(); });                       // Back closes just this sheet
    requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add('open'); }); });
    function hide() { if (closing) return; closing = true; el.classList.remove('open'); panel.style.transform = ''; setTimeout(function () { el.remove(); }, 280); }
    function close(then) { if (closing) return; hide(); mzSheetCloseEntry(entry, then); }
    el._close = function (opts) { if (closing) return; hide(); if (opts && opts.route) mzSheetDrop(entry); else mzSheetCloseEntry(entry); };

    function pick(r) {
      var it = items[parseInt(r.dataset.i, 10)]; if (!it || !it.run) return;
      mzHaptic('tick');
      close(it.run);                                                               // leave first (animation, history), then act
    }
    scroller.addEventListener('scroll', function () { lastScroll = Date.now(); }, { passive: true });
    var down = null;
    scroller.addEventListener('pointerdown', function (e) { down = { x: e.clientX, y: e.clientY, flung: Date.now() - lastScroll < 260 }; });
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      if (e.target.classList.contains('sp-addback')) { if (Date.now() - openedAt > 300) { mzHaptic('close'); close(); } return; }
      var r = e.target.closest('.sp-mrow[data-i]'); if (!r) return;
      if (Date.now() - openedAt < 300 || Date.now() - swipedAt < 400) return;      // the tap that opened it, or the end of a swipe
      if (down && (down.flung || Math.abs(e.clientX - down.x) > 10 || Math.abs(e.clientY - down.y) > 10)) { down = null; return; }   // a scroll, not a tap
      down = null;
      pick(r);
    });
    if (pop) {
      el.addEventListener('contextmenu', function (e) { e.preventDefault(); close(); });           // a second right-click elsewhere just closes it
      var first = el.querySelector('.sp-mrow[data-i]'); if (first) setTimeout(function () { first.focus({ preventScroll: true }); }, 30);
    }
    el.addEventListener('keydown', function (e) {
      if (pop && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        e.preventDefault();
        var rs = Array.prototype.slice.call(el.querySelectorAll('.sp-mrow[data-i]')), i = rs.indexOf(document.activeElement);
        var nx = rs[(i + (e.key === 'ArrowDown' ? 1 : -1) + rs.length) % rs.length]; if (nx) nx.focus({ preventScroll: true });
      }
      if (e.key === 'Escape') close();
      else if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('sp-mrow')) { e.preventDefault(); pick(e.target); }
    });

    // swipe down anywhere on the sheet (from the top of its list) to dismiss; it follows the finger
    var tp = null;
    function setY(y, anim) { if (!anim) panel.style.transition = 'none'; else if (panel.style.transition === 'none') panel.style.transition = ''; panel.style.transform = y ? 'translateY(' + y + 'px)' : ''; el.querySelector('.sp-addback').style.opacity = y ? Math.max(0, 1 - y / (panel.offsetHeight || 400)) : ''; }
    panel.addEventListener('touchstart', function (e) {
      tp = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY, drag: false, v: 0, t0: performance.now(), last: { y: e.touches[0].clientY, t: performance.now() } } : null;
    }, { passive: true });
    panel.addEventListener('touchmove', function (e) {
      if (!tp) return;
      var f = e.touches[0], dy = f.clientY - tp.y, dx = f.clientX - tp.x;
      if (!tp.drag) {
        if (scroller.contains(e.target) && scroller.scrollTop > 0) { tp = null; return; }                  // the list is scrolled: that is a scroll
        if (dy < 10 || Math.abs(dy) < Math.abs(dx) * 1.2) { if (dy < -4) tp = null; return; }
        tp.v = dy / Math.max(16, performance.now() - tp.t0); tp.drag = true; tp.y = f.clientY - 10; dy = 10;
      }
      e.preventDefault();
      var now = performance.now(); tp.v = 0.6 * tp.v + 0.4 * ((f.clientY - tp.last.y) / Math.max(1, now - tp.last.t)); tp.last = { y: f.clientY, t: now };
      setY(Math.max(0, dy), false);
    }, { passive: false });
    function endSwipe(e) {
      if (!tp || !tp.drag) { tp = null; return; }
      var d = tp, f = e.changedTouches[0]; tp = null; swipedAt = Date.now();
      var dy = f.clientY - d.y, h = panel.offsetHeight || window.innerHeight;
      if (e.type !== 'touchcancel' && (dy > h * 0.2 || d.v > 0.5)) { mzHaptic('close'); el.querySelector('.sp-addback').style.opacity = ''; panel.style.transition = 'transform ' + dur(h - dy, d.v, 160, 320) + 'ms ' + EASE_FLING; close(); } else { panel.style.transition = 'transform ' + dur(dy, 0, 180, 300) + 'ms ' + EASE_OUT; setY(0, true); }
    }
    panel.addEventListener('touchend', endSwipe); panel.addEventListener('touchcancel', endSwipe);
  };

  // Photo / banner from a SoundCloud profile (for artists Navidrome has no picture of)
  function scPost(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || 'Failed'); return d; }); });
  }
  function scApply(a, profile) {
    mzToast('Importing from SoundCloud…');
    scPost('/api/music/sc/apply', { aid: a.id, profile: profile }).then(function (d) {
      mz.artV = mz.artV || {}; mz.artV[a.id] = Date.now(); mz.artB = mz.artB || {}; if (d.got.indexOf('banner') >= 0) mz.artB[a.id] = true;
      mzToast('Saved ' + d.got.join(' + ') + ' from ' + d.name); mzRender();
    }).catch(function (e) { mzToast(e.message); });
  }
  function artApply(a, source, ref) {
    mzToast('Importing…');
    scPost('/api/music/art/apply', { aid: a.id, source: source, ref: ref }).then(function (d) {
      mz.artV = mz.artV || {}; mz.artV[a.id] = Date.now(); mz.artB = mz.artB || {}; if (d.got.indexOf('banner') >= 0) mz.artB[a.id] = true; mzToast('Saved ' + d.got.join(' + ') + ' from ' + d.name); mzRender();
    }).catch(function (e) { mzToast(e.message); });
  }
  SP.spPick = function (a) {
    mzToast('Searching the web for ' + a.name + '…');
    fetch('/api/music/art/spotify/search?q=' + encodeURIComponent(a.name)).then(function (r) { return r.json(); }).then(function (list) {
      if (list.error) throw new Error(list.error);
      if (!list.length) { mzToast('No Spotify artist found'); return; }
      SP.menuSheet({ title: 'Pick the right artist', items: list.map(function (u) {
        return { icon: MI.person, label: u.name, sub: (u.info || '').replace(/^Artist · /, '') + (u.banner ? ' · has banner' : ''), run: function () { artApply(a, 'spotify', u.id); } };
      }) });
    }).catch(function (e) { mzToast(e.message || 'Search failed'); });
  };
  SP.dzPick = function (a) {
    mzToast('Searching Deezer…');
    fetch('/api/music/art/deezer/search?q=' + encodeURIComponent(a.name)).then(function (r) { return r.json(); }).then(function (list) {
      if (list.error) throw new Error(list.error);
      if (!list.length) { mzToast('No Deezer artists found'); return; }
      SP.menuSheet({ title: 'Pick the right artist', items: list.map(function (u) {
        return { icon: MI.person, label: u.name, sub: u.fans + ' fans', run: function () { artApply(a, 'deezer', u.id); } };
      }) });
    }).catch(function (e) { mzToast(e.message || 'Search failed'); });
  };
  SP.artistMenu = function (a) {
    var head = '<div class="sp-mhead">' + artistCov(a, 100, "sm") + '<span class="sp-mt"><b>' + esc(a.name) + '</b><small>Artist</small></span></div>';
    var own = mz.view.type === 'artist' && mz.view.key === a.id, top = [];
    if (!own) {                                                  // opened from a card / row: the usual actions come first
      var all = a.tracks.slice().sort(function (x, y) { return (y.pc || 0) - (x.pc || 0); });
      top = [{ icon: MI.next, label: 'Play', run: function () { mzPlayList(all, 0); } },
        { icon: MI.queue, label: 'Shuffle', run: function () { mzPlayList(all, 0, true); } },
        { icon: MI.person, label: 'Go to artist', run: function () { mzGo('artist', a.id); } }, { sep: true }];
    }
    SP.menuSheet({ title: a.name, head: head, items: top.concat([
      { icon: MI.person, label: 'Find on SoundCloud', sub: 'Search for "' + a.name + '"', run: function () { SP.scPick(a); } },
      { icon: MI.person, label: 'Find on Spotify', sub: 'Photo and banner, via a web search', run: function () { SP.spPick(a); } },
      { icon: MI.person, label: 'Find on Deezer', sub: 'Photo only, many small artists', run: function () { SP.dzPick(a); } },
      { icon: MI.person, label: 'Paste a Spotify artist link', sub: 'Photo only', run: function () {
        var u = window.prompt('Spotify artist link (open.spotify.com/artist/…)'); if (u && u.trim()) artApply(a, 'spotify', u.trim()); } },
      { icon: MI.person, label: 'Paste a SoundCloud link', run: function () {
        var u = window.prompt('SoundCloud profile link (soundcloud.com/…)'); if (u && u.trim()) scApply(a, u.trim()); } },
      { sep: true },
      { icon: MI.person, label: 'Remove custom photo and banner', run: function () {
        scPost('/api/music/sc/clear', { aid: a.id }).then(function () { mz.artV = mz.artV || {}; mz.artV[a.id] = Date.now(); if (mz.artB) delete mz.artB[a.id]; mzToast('Removed'); mzRender(); }); } },
    ]) });
  };
  SP.scPick = function (a) {
    mzToast('Searching SoundCloud…');
    fetch('/api/music/sc/search?q=' + encodeURIComponent(a.name)).then(function (r) { return r.json(); }).then(function (list) {
      if (list.error) throw new Error(list.error);
      if (!list.length) { mzToast('No SoundCloud profiles found'); return; }
      SP.menuSheet({ title: 'Pick the right profile', items: list.map(function (u) {
        return { icon: MI.person, label: u.name, sub: u.followers + ' followers · ' + u.tracks + ' tracks · soundcloud.com/' + u.permalink, run: function () { scApply(a, u.permalink); } };
      }) });
    }).catch(function (e) { mzToast(e.message || 'Search failed'); });
  };

  // delete a playlist: from its page (the ⋮ at the top), or by long-pressing / right-clicking it anywhere
  var TRASH = mi('<polyline points="4 7 20 7"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>');
  SP.playlistMenu = function (pl) {
    var head = '<div class="sp-mhead">' + plCov(pl, 100, 'sm') + '<span class="sp-mt"><b>' + esc(pl.name) + '</b><small>Playlist • ' + plural(pl.n || 0, 'song') + '</small></span></div>';
    SP.menuSheet({ title: pl.name, head: head, items: [
      { icon: MI.next, label: 'Play', run: function () { playCollection('playlist', pl.id); } },
      { icon: I.shuffle.replace('width="16" height="16"', 'width="24" height="24"'), label: 'Shuffle play', run: function () { playCollection('playlist', pl.id, true); } },
      { icon: MI.next, label: 'Play next', run: function () { collectionList('playlist', pl.id).then(function (l) { if (!mzCur()) playCollection('playlist', pl.id); else l.slice().reverse().forEach(function (t) { mzQueueNext(t); }); }); } },
      { icon: MI.queue, label: 'Add to queue', run: function () { collectionList('playlist', pl.id).then(function (l) { l.forEach(function (t) { mzQueueAdd(t); }); }); } },
      { sep: true },
      { icon: MI.queue, label: 'Rename', run: function () { setTimeout(function () { SP.renamePlaylist(pl); }, 330); } },
      { icon: MI.album, label: 'Change cover', run: function () { setTimeout(function () { SP.playlistCover(pl); }, 330); } },
      { icon: TRASH, label: 'Delete playlist', run: function () {
        if (!window.confirm('Delete the playlist "' + pl.name + '"? The songs stay in your library.')) return;
        var had = mz.plCache[pl.id] ? Promise.resolve(mz.plCache[pl.id].slice())
          : fetch('/api/music/playlist/' + encodeURIComponent(pl.id)).then(function (r) { return r.json(); }).then(function (d) { return d.ids || []; }).catch(function () { return []; });
        had.then(function (ids) {
          return jpost('/api/music/playlist/' + encodeURIComponent(pl.id) + '/delete', {}).then(function () { return ids; });
        }).then(function (ids) {
          mz.playlists = mz.playlists.filter(function (x) { return x.id !== pl.id; }); delete mz.plCache[pl.id];
          mz.prefs.recents = (mz.prefs.recents || []).filter(function (r) { return !(r[0] === 'playlist' && r[1] === pl.id); }); mzSavePrefs();
          mzHaptic('like');
          mzToast('Deleted "' + pl.name + '"', { label: 'Undo', fn: function () {          // makes it again with the same name and songs, in order (it gets a new id)
            jpost('/api/music/playlists', { name: pl.name, ids: ids }).then(function () { mzToast('Restored "' + pl.name + '"'); return loadMusic(); })
              .catch(function () { mzHaptic('warn'); mzToast('Could not restore it'); });
          } });
          if (mz.view.type === 'playlist' && mz.view.key === pl.id) mzGo('library'); else mzRender();
        }).catch(function (e) { mzHaptic('warn'); mzToast(e.message || 'Could not delete the playlist'); });
      } }
    ] });
  };
  // A picture of your own for a playlist: a photo from this device, or the picture of a Spotify playlist link
  function setPlCover(pl, send) {
    mzToast('Saving the cover…');
    return send.then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || 'Could not save the cover'); return d; }); }).then(function (d) {
      mz.artV = mz.artV || {}; mz.artV['pl_' + pl.id] = d.v;
      Object.keys(tintCache).forEach(function (k) { if (k.indexOf('pl-' + pl.id) === 0) delete tintCache[k]; });
      mzHaptic('like'); mzToast('Cover saved'); mzRender();
    }).catch(function (e) { mzHaptic('warn'); mzToast(e.message || 'Could not save the cover'); });
  }
  SP.playlistCover = function (pl) {
    var own = mz.artV && mz.artV['pl_' + pl.id], url = '/api/music/playlist/' + encodeURIComponent(pl.id) + '/cover';
    var items = [
      { icon: MI.album, label: 'Upload a photo', sub: 'From this device', run: function () {
        var inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*';
        inp.addEventListener('change', function () { if (inp.files[0]) { var f = new FormData(); f.append('file', inp.files[0]); setPlCover(pl, fetch(url, { method: 'POST', body: f })); } });
        inp.click();
      } },
      { icon: MI.plus, label: 'Use a Spotify playlist link', sub: 'Takes the picture Spotify shows for it', run: function () { setTimeout(function () { SP.playlistCoverLink(pl); }, 330); } }
    ];
    if (own) items.push({ sep: true }, { icon: TRASH, label: 'Remove this cover', run: function () {
      fetch(url + '/clear', { method: 'POST' }).then(function () { delete mz.artV['pl_' + pl.id]; mzToast('Cover removed'); mzRender(); });
    } });
    SP.menuSheet({ title: 'Cover for ' + pl.name, items: items });
  };
  SP.playlistCoverLink = function (pl) {
    SP.menuSheet({ title: 'Spotify playlist link', items: [], body: '<div class="sp-qs"><div class="sp-rn"><input id="sp-pc-in" type="text" autocomplete="off" placeholder="open.spotify.com/playlist/…" aria-label="Spotify playlist link"><button type="button" class="sp-rn-ok">Use</button></div>' +
      '<p class="sp-qs-fine">In Spotify: ⋯ → Share → Copy link to playlist. The playlist has to be public. The picture is cut to a square from the middle.</p></div>',
      mount: function (el) {
        var inp = el.querySelector('#sp-pc-in'), ok = el.querySelector('.sp-rn-ok');
        function go() {
          var link = inp.value.trim(); if (!link) return;
          ok.disabled = true; el._close && el._close();
          setPlCover(pl, fetch('/api/music/playlist/' + encodeURIComponent(pl.id) + '/cover', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ link: link }) }));
        }
        ok.addEventListener('click', go);
        inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); go(); } });
        setTimeout(function () { inp.focus(); }, 380);
      } });
  };
  SP.renamePlaylist = function (pl) {
    SP.menuSheet({ title: 'Rename playlist', items: [], body: '<div class="sp-rn"><input id="sp-rn-in" type="text" maxlength="120" autocomplete="off" value="' + esc(pl.name) + '" aria-label="Playlist name"><button type="button" class="sp-rn-ok">Save</button></div>',
      mount: function (el) {
        var inp = el.querySelector('#sp-rn-in'), ok = el.querySelector('.sp-rn-ok');
        function save() {
          var name = inp.value.trim();
          if (!name || name === pl.name) { el._close && el._close(); return; }
          ok.disabled = true;
          jpost('/api/music/playlist/' + encodeURIComponent(pl.id) + '/rename', { name: name }).then(function () {
            pl.name = name; el._close && el._close(); mzToast('Renamed to "' + name + '"'); mzRender();
          }).catch(function (e) { ok.disabled = false; mzHaptic('warn'); mzToast(e.message || 'Could not rename'); });
        }
        ok.addEventListener('click', save);
        inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); save(); } });
        setTimeout(function () { inp.focus(); inp.select(); }, 380);
      } });
  };
  (function () {
    var timer = 0, sx = 0, sy = 0, swallow = 0;
    function target(e) {                                           // a playlist, album or artist card / row: [open its menu]
      if (mz.theme !== 'spotify' || !e.target.closest) return null;
      var el = e.target.closest('[data-k][data-v]'), k, v;
      if (e.target.closest('button, .sp-playctx, [data-act="sp-playctx"]')) return null;
      if (el && el.closest('#music-screen')) { k = el.dataset.k; v = el.dataset.v; }
      else if (e.target.closest('#music-screen .sp-phead') && mz.view.type === 'playlist') { k = 'playlist'; v = mz.view.key; }      // the name and cover on the playlist's own page
      else return null;
      if (k === 'playlist') { var pl = mz.playlists.filter(function (x) { return x.id === v; })[0]; return pl ? function () { SP.playlistMenu(pl); } : null; }
      if (k === 'album') { var al = mz.albums.get(v); return al ? function () { SP.albumMenu(al); } : null; }
      if (k === 'artist') { var ar = mz.artists.get(v); return ar ? function () { SP.artistMenu(ar); } : null; }
      return null;
    }
    function cancel() { clearTimeout(timer); timer = 0; }
    document.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse') return;
      var open = target(e); if (!open) return;
      sx = e.clientX; sy = e.clientY; cancel();
      timer = setTimeout(function () { timer = 0; swallow = Date.now(); mzHaptic('tick'); open(); }, 480);
    }, true);
    document.addEventListener('pointermove', function (e) { if (timer && Math.hypot(e.clientX - sx, e.clientY - sy) > 8) cancel(); }, true);
    ['pointerup', 'pointercancel', 'scroll'].forEach(function (ev) { document.addEventListener(ev, cancel, true); });
    document.addEventListener('contextmenu', function (e) { var open = target(e); if (open) { e.preventDefault(); e.stopPropagation(); swallow = Date.now(); SP.menuAt = { x: e.clientX, y: e.clientY, t: Date.now() }; open(); } }, true);
    document.addEventListener('click', function (e) { if (Date.now() - swallow < 600) { e.stopPropagation(); e.preventDefault(); } }, true);
  })();

  SP.albumMenu = function (al) {
    var tracks = al.tracks.slice();
    var head = '<div class="sp-mhead">' + albumCov(al, 100, 'sm') + '<span class="sp-mt"><b>' + esc(al.name) + '</b><small>' + esc(al.artist || '') + '</small></span></div>';
    var cr = albumCredits(al), items = [];
    items.push({ icon: MI.queue, label: 'Add to queue', run: function () { tracks.forEach(function (t) { mzQueueAdd(t); }); mzToast('Added ' + plural(tracks.length, 'song') + ' to the queue'); } });
    items.push({ icon: MI.next, label: 'Play next', run: function () { tracks.slice().reverse().forEach(function (t) { mzQueueNext(t); }); } });
    items.push({ sep: true });
    cr.forEach(function (c) { items.push({ icon: MI.person, label: cr.length > 1 ? 'Go to ' + c.name : 'Go to artist', sub: cr.length > 1 ? '' : c.name, run: function () { mzGo('artist', c.id); } }); });
    SP.menuSheet({ title: al.name, head: head, items: items });
  };

  // The ⋯ menu for a song, in the order the Spotify app has it
  // tap the format line: everything the app knows about the file
  SP.qualMenu = function (t) {
    var fmt = String(t.sx || '').toLowerCase(), rows = [];
    function add(label, val) { if (val) rows.push({ label: label, sub: String(val), run: function () {} }); }
    var rate = typeof mzQualityRate === 'function' ? mzQualityRate() : 0;
    add('Playing as', rate ? 'MP3 at ' + rate + ' kbps (converted for streaming)' : 'The original file');
    add('File format', fmt.toUpperCase() + (LOSSLESS[fmt] ? ' (lossless)' : ' (lossy)'));
    add('File bitrate', t.br && t.br + ' kbps');
    add('Sample rate', t.sr && (t.sr / 1000).toString().replace(/\.0+$/, '') + ' kHz');
    add('Bit depth', t.bd && t.bd + '-bit');
    add('Channels', t.ch && (t.ch === 1 ? 'Mono' : t.ch === 2 ? 'Stereo' : t.ch + ' channels'));
    add('File size', t.sz && (t.sz / 1048576).toFixed(1) + ' MB');
    add('Length', t.d && mzFmt(t.d));
    var head = '<div class="sp-mhead">' + trackCov(t, 100, 'sm') + '<span class="sp-mt"><b>' + esc(t.t) + '</b><small>File details</small></span></div>';
    SP.menuSheet({ title: 'File details', head: head, items: rows });
  };

  SP.trackMenu = function (t, o) {
    o = o || {};
    var cr = mzCredits(t), items = [];
    items.push({ icon: t.fav ? MI.heartOn : MI.heart, label: t.fav ? 'Remove from Liked Songs' : 'Add to Liked Songs', on: t.fav, run: function () { mzToggleFav(t); } });
    items.push({ icon: MI.plus, label: 'Add to playlist', run: function () { SP.addMenu(null, t, {}); } });
    items.push({ icon: MI.queue, label: 'Add to queue', run: function () { mzQueueAdd(t); } });
    items.push({ icon: MI.next, label: 'Play next', run: function () { mzQueueNext(t); } });
    items.push({ sep: true });
    if (t.li) items.push({ icon: MI.album, label: 'Go to album', sub: t.al || '', run: function () { mzGo('album', t.li); } });
    cr.forEach(function (c) { items.push({ icon: MI.person, label: cr.length > 1 ? 'Go to ' + c.name : 'Go to artist', sub: cr.length > 1 ? '' : c.name, run: function () { mzGo('artist', c.id); } }); });
    if (npIsOpen && mzCur() && mzCur().f === t.f) {                // from the full-screen player: show or hide the live lyric line
      var lyrOn = mz.prefs.lyr !== false;
      items.push({ sep: true });
      items.push({ icon: MI.queue, label: lyrOn ? 'Hide lyrics' : 'Show lyrics', run: function () { mz.prefs.lyr = !lyrOn; mzSavePrefs(); lyrLoad(t); mzToast(lyrOn ? 'Lyrics hidden' : 'Lyrics on'); } });
    }
    if (o.fromQueue && o.qIdx != null && !isNaN(o.qIdx) && o.qIdx !== mz.qi) { items.push({ sep: true }); items.push({ icon: MI.remove, label: 'Remove from queue', run: function () { mzQueueRemoveAt(o.qIdx); } }); }
    var head = '<div class="sp-mhead">' + trackCov(t, 100, 'sm') + '<span class="sp-mt"><b>' + esc(t.t) + '</b><small>' + esc(t.ar) + '</small></span></div>';
    SP.menuSheet({ title: t.t, head: head, items: items });
  };

  SP.addMenu = function (ev, track, opts) {
    if (ev) ev.stopPropagation();
    var t = track || mzCur(); if (!t) return;
    opts = opts || {};
    mzHaptic('tick');
    var old = mzEl('sp-addsheet'); if (old) old.remove();
    var el = document.createElement('div'); el.id = 'sp-addsheet'; el.className = 'sp-addsheet';
    var inSet = null, openedAt = Date.now(), lastScroll = 0, closing = false, swipedAt = 0;
    function row(cls, cover, title, sub, attrs) {
      return '<div class="sp-addrow ' + cls + '" role="button" tabindex="0"' + (attrs || '') + '>' + cover + '<span class="sp-addt"><b>' + esc(title) + '</b>' + (sub ? '<small>' + esc(sub) + '</small>' : '') + '</span>' + TICK + '</div>';
    }
    function plRow(p) { return row('pl', plCov(p, 100, 'sm'), p.name, 'Playlist • ' + plural(p.n || 0, 'song'), ' data-id="' + esc(p.id) + '"'); }
    var plus = '<span class="sp-addplus"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></span>';
    var curPl = opts.pid ? mz.playlists.filter(function (x) { return x.id === opts.pid; })[0] : null;
    el.innerHTML = '<div class="sp-addback"></div><div class="sp-addpanel"><div class="sp-addtop"><div class="sp-addgrab"></div><div class="sp-addhead">' + (opts.pid ? esc(t.t) : 'Add to playlist') + '</div></div>' +
      '<div class="sp-addscroll">' +
      (curPl ? '<div class="sp-addrow rm" role="button" tabindex="0"><span class="sp-addplus rmicon"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg></span><span class="sp-addt"><b>Remove from this playlist</b><small>' + esc(curPl.name) + '</small></span></div>' : '') +
      row('liked', likedCov('sm'), 'Liked Songs', '') +
      '<div class="sp-addsep"></div>' +
      '<div class="sp-addnew"><div class="sp-addrow new" role="button" tabindex="0">' + plus + '<span class="sp-addt"><b>New playlist</b></span></div>' +
      '<form class="sp-addform"><input type="text" maxlength="120" placeholder="Playlist name" aria-label="Playlist name"><button type="submit">Create</button></form></div>' +
      '<div class="sp-addlist">' + mz.playlists.map(plRow).join('') + '</div></div></div>';
    (rootEl() || document.body).appendChild(el);
    var panel = el.querySelector('.sp-addpanel'), scroller = el.querySelector('.sp-addscroll');
    requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add('open'); }); });

    var entry = mzSheetOpenEntry(function () { hide(); });                       // Back closes just this sheet
    function hide() {
      if (closing) return; closing = true;
      el.classList.remove('open'); panel.style.transform = '';
      setTimeout(function () { el.remove(); }, 280);
    }
    function close() { if (closing) return; hide(); mzSheetCloseEntry(entry); }
    el._close = function (o) { if (closing) return; hide(); if (o && o.route) mzSheetDrop(entry); else mzSheetCloseEntry(entry); };
    function mark(r, on) { r.classList.toggle('in', !!on); r.setAttribute('aria-pressed', on ? 'true' : 'false'); }
    function paint() {
      mark(el.querySelector('.sp-addrow.liked'), t.fav);
      el.querySelectorAll('.sp-addrow.pl').forEach(function (r) { mark(r, inSet && inSet.has(r.dataset.id)); });
      el.classList.toggle('loading', !inSet);
      if (inSet && mz.inPl) { if (inSet.size) mz.inPl.add(t.f); else mz.inPl.delete(t.f); }
      if (t === mzCur()) { t.inpl = !!(inSet && inSet.size); npSync(true); }
    }
    paint();
    fetch('/api/music/membership?id=' + encodeURIComponent(t.f)).then(function (r) { return r.json(); })
      .then(function (d) { inSet = new Set(d.playlists || []); paint(); })
      .catch(function () { inSet = new Set(); paint(); mzToast('Could not load your playlists'); });

    function viewIs(pid) { return mz.view.type === 'playlist' && mz.view.key === pid; }
    function syncLocal(p, inNow, at) {
      var ids = mz.plCache[p.id];
      if (inNow) { if (ids && ids.indexOf(t.f) < 0) { if (at !== undefined && at < ids.length) ids.splice(at, 0, t.f); else ids.push(t.f); } p.n = (p.n || 0) + 1; }
      else {
        var gone = 1;
        if (ids) { mz.plCache[p.id] = ids.filter(function (x) { return x !== t.f; }); gone = ids.length - mz.plCache[p.id].length || 1; }
        p.n = Math.max(0, (p.n || 0) - gone);
      }
      var sub = el.querySelector('.sp-addrow.pl[data-id="' + CSS.escape(p.id) + '"] small'); if (sub) sub.textContent = 'Playlist • ' + plural(p.n, 'song');
      if (viewIs(p.id)) mzRender();                         // the open playlist page changes live
      else if (mz.view.type !== 'now') { var sd = mzEl('wm-side'); if (sd && sd.innerHTML) sd.innerHTML = sideHtml(); }
    }
    function toggle(r) {
      if (r.classList.contains('busy')) return;
      if (r.classList.contains('liked')) { mzToggleFav(t); paint(); return; }
      if (!inSet) return;
      var p = mz.playlists.filter(function (x) { return x.id === r.dataset.id; })[0]; if (!p) return;
      var was = inSet.has(p.id);
      r.classList.add('busy'); mzHaptic('tick');
      var key = p.id + '|' + t.f;
      (was ? jpost('/api/music/playlist/' + encodeURIComponent(p.id) + '/remove', { id: t.f })
           : jpost('/api/music/playlist/' + encodeURIComponent(p.id) + '/add', slots[key] === undefined ? { id: t.f } : { id: t.f, index: slots[key] }))
        .then(function (d) {
          if (was) { inSet.delete(p.id); if (d.indices && d.indices.length) slots[key] = d.indices[0]; }
          else { inSet.add(p.id); delete slots[key]; }
          mark(r, !was); r.classList.remove('busy');
          if (!was && d.dup) { mzToast('Already in ' + p.name); return; }
          syncLocal(p, !was, d.index);
          mzToast(was ? 'Removed from ' + p.name : 'Added to ' + p.name);
        })
        .catch(function () { r.classList.remove('busy'); mzHaptic('warn'); mzToast('Could not update ' + p.name); });
    }

    // taps that are really scrolling (including a tap to stop a fling) must not toggle anything
    var down = null;
    scroller.addEventListener('scroll', function () { lastScroll = Date.now(); }, { passive: true });
    scroller.addEventListener('pointerdown', function (e) { down = { x: e.clientX, y: e.clientY, at: Date.now(), flung: Date.now() - lastScroll < 260 }; });
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      if (e.target.classList.contains('sp-addback')) { close(); return; }
      var r = e.target.closest('.sp-addrow'); if (!r) return;
      if (Date.now() - openedAt < 350 || Date.now() - swipedAt < 400) return;
      if (down && (down.flung || Math.abs(e.clientX - down.x) > 10 || Math.abs(e.clientY - down.y) > 10)) { down = null; return; }
      down = null;
      if (r.classList.contains('rm')) {
        var pl = curPl; r.classList.add('busy');
        jpost('/api/music/playlist/' + encodeURIComponent(pl.id) + '/remove', { id: t.f }).then(function (d) {
          if (d.indices && d.indices.length) slots[pl.id + '|' + t.f] = d.indices[0];
          if (inSet) inSet.delete(pl.id); inSet = inSet || new Set(); syncLocal(pl, false); mzToast('Removed from ' + pl.name); close();
        }).catch(function () { r.classList.remove('busy'); mzHaptic('warn'); mzToast('Could not remove'); });
        return;
      }
      if (r.classList.contains('new')) {
        var box = el.querySelector('.sp-addnew'); box.classList.add('open');
        var inp = box.querySelector('input'); inp.value = t.al || t.t || ''; setTimeout(function () { inp.focus(); inp.select(); box.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, 120);
        return;
      }
      toggle(r);
    });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
      else if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('sp-addrow')) { e.preventDefault(); e.target.click(); }
    });
    el.querySelector('.sp-addform').addEventListener('submit', function (e) {
      e.preventDefault();
      var inp = e.target.querySelector('input'), name = inp.value.trim(); if (!name) return;
      if (mz.playlists.some(function (p) { return p.name.toLowerCase() === name.toLowerCase(); })) { mzHaptic('warn'); mzToast('You already have a playlist called "' + name + '"'); return; }
      var btn = e.target.querySelector('button'); btn.disabled = true;
      jpost('/api/music/playlists', { name: name, id: t.f }).then(function (d) {
        var p = { id: d.id, name: name, n: 1, c: '', d: 0 };
        mz.playlists.unshift(p); mz.plCache[d.id] = [t.f];
        if (inSet) inSet.add(d.id);
        var tmp = document.createElement('div'); tmp.innerHTML = plRow(p);
        var nr = tmp.firstChild; nr.classList.add('fresh'); el.querySelector('.sp-addlist').prepend(nr); mark(nr, true);
        el.querySelector('.sp-addnew').classList.remove('open'); inp.value = ''; btn.disabled = false;
        mzToast('Added to ' + name); mzHaptic('like');
        var sd = mzEl('wm-side'); if (sd && sd.innerHTML) sd.innerHTML = sideHtml();
      }).catch(function (err) { btn.disabled = false; mzHaptic('warn'); mzToast(err.message || 'Could not create playlist'); });
    });

    // swipe down anywhere on the sheet (from the top of its list, like the queue) to dismiss; it follows the finger
    var tp = null;
    function setY(y, anim) { if (!anim) panel.style.transition = 'none'; else if (panel.style.transition === 'none') panel.style.transition = ''; panel.style.transform = y ? 'translateY(' + y + 'px)' : ''; }
    panel.addEventListener('touchstart', function (e) {
      tp = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY, drag: false, v: 0, t0: performance.now(), last: { y: e.touches[0].clientY, t: performance.now() } } : null;
    }, { passive: true });
    panel.addEventListener('touchmove', function (e) {
      if (!tp) return;
      var f = e.touches[0], dy = f.clientY - tp.y, dx = f.clientX - tp.x;
      if (!tp.drag) {
        if (scroller.contains(e.target) && scroller.scrollTop > 0) { tp = null; return; }          // the list is scrolled: that is a scroll
        if (dy < 10 || Math.abs(dy) < Math.abs(dx) * 1.2) { if (dy < -4) tp = null; return; }
        tp.v = dy / Math.max(16, performance.now() - tp.t0); tp.drag = true; tp.y = f.clientY - 10; dy = 10;                                              // measure from where the drag really began
      }
      e.preventDefault();
      var now = performance.now(); tp.v = 0.6 * tp.v + 0.4 * ((f.clientY - tp.last.y) / Math.max(1, now - tp.last.t)); tp.last = { y: f.clientY, t: now };
      setY(Math.max(0, dy), false);
    }, { passive: false });
    function endSwipe(e) {
      if (!tp || !tp.drag) { tp = null; return; }
      var d = tp, f = e.changedTouches[0]; tp = null; swipedAt = Date.now();
      var dy = f.clientY - d.y, h = panel.offsetHeight || window.innerHeight;
      if (e.type !== 'touchcancel' && (dy > h * 0.18 || d.v > 0.5)) { panel.style.transition = 'transform ' + dur(h - dy, d.v, 160, 320) + 'ms ' + EASE_FLING; close(); }
      else { panel.style.transition = 'transform ' + dur(dy, 0, 180, 300) + 'ms ' + EASE_OUT; setY(0, true); }
    }
    panel.addEventListener('touchend', endSwipe); panel.addEventListener('touchcancel', endSwipe);
  };

  // Done: write the staged order / removals to Navidrome in one go (nothing is saved while you are still editing)
  SP.editDone = function () {
    var ed = edit; if (!ed || ed.saving) return;
    var cur = mz.plCache[ed.pid] || [];
    if (ed.draft.join('\n') === cur.join('\n')) { edit = null; mzRender(); return; }
    ed.saving = true; mzRender();
    jpost('/api/music/playlist/' + encodeURIComponent(ed.pid) + '/order', { ids: ed.draft, base: ed.base })
      .then(function () {
        mz.plCache[ed.pid] = ed.draft;
        var p = mz.playlists.filter(function (x) { return x.id === ed.pid; })[0]; if (p) p.n = ed.draft.length;
        edit = null; mzInPlRefresh(); mzToast('Playlist updated'); mzHaptic('like'); mzRender();
      })
      .catch(function (err) {
        ed.saving = false; mzHaptic('warn');
        if (/changed elsewhere/.test(err.message || '')) { edit = null; delete mz.plCache[ed.pid]; mzToast('This playlist changed elsewhere. Reloaded it'); }
        else mzToast('Could not save. Your edits are still here');
        mzRender();
      });
  };

  // ─── edit mode: hold the ≡ handle and move a row; the new order is staged until Done ───
  (function () {
    var D = null;
    function content() { return mzEl('wm-content'); }
    function move(e) {
      if (!D) return;
      D.cy = e.clientY;
      var y = D.cy - D.sy + (content().scrollTop - D.scroll0);
      if (!D.sel) D.row.style.transform = 'translateY(' + y + 'px)'; dragLayout(D, y);
    }
    function scrollLoop() {
      if (!D) return;
      var c = content(), r = c.getBoundingClientRect(), v = 0;
      if (D.cy < r.top + 70) v = -Math.ceil((r.top + 70 - D.cy) / 6);
      else if (D.cy > r.bottom - 70) v = Math.ceil((D.cy - (r.bottom - 70)) / 6);
      if (v) { c.scrollTop += v; move({ clientY: D.cy }); }
      D.raf = requestAnimationFrame(scrollLoop);
    }
    function end(e) {
      if (!D) return;
      var d = D; D = null; cancelAnimationFrame(d.raf);
      document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', end); document.removeEventListener('pointercancel', end);
      d.rows.forEach(function (r) { r.style.transform = ''; r.style.transition = ''; r.classList.remove('moving'); });
      d.rows.forEach(function (r) { r.classList.remove('dragging'); }); content().classList.remove('reordering');
      if (e.type === 'pointercancel' || d.to === d.from) return;
      var ids = edit && edit.draft; if (!ids) return;
      // rows show only tracks the library knows; the draft also keeps any it doesn't, in their slots
      var at = []; ids.forEach(function (id, i) { if (mz.byId.has(id)) at.push(i); });
      if (at.length !== d.rows.length) return;
      var shown = at.map(function (i) { return ids[i]; }), grabbed = shown[d.from];
      if (edit.sel.size > 1 && edit.sel.has(grabbed)) shown = groupShown(shown, edit.sel, grabbed, d.to);        // the whole selection moves
      else { var m = shown.splice(d.from, 1)[0]; shown.splice(d.to, 0, m); }
      var next = ids.slice(); at.forEach(function (i, k) { next[i] = shown[k]; });
      edit.draft = next; mzHaptic('tick'); mzRender();
    }
    document.addEventListener('pointerdown', function (e) {
      var g = e.target.closest && e.target.closest('.sp-grip'); if (!g || D) return;
      var row = g.closest('.sp-row'), list = row && row.parentElement; if (!row || !list || !edit || mz.view.type !== 'playlist') return;
      e.preventDefault(); e.stopPropagation();
      var rows = Array.prototype.slice.call(list.querySelectorAll('.sp-row.trk')), from = rows.indexOf(row); if (from < 0) return;
      D = { row: row, rows: rows, ids: rows.map(function (r) { return r.dataset.t; }), from: from, to: from, h: row.offsetHeight, top0: from * row.offsetHeight, sy: e.clientY, cy: e.clientY, scroll0: content().scrollTop, raf: 0 };
      if (edit.sel.size > 1 && edit.sel.has(D.ids[from])) D.sel = edit.sel;
      rows.forEach(function (r) { r.classList.add('moving'); if (D.sel && D.sel.has(r.dataset.t)) r.classList.add('dragging'); });
      row.classList.add('dragging'); content().classList.add('reordering'); mzHaptic('tick');
      document.addEventListener('pointermove', move); document.addEventListener('pointerup', end); document.addEventListener('pointercancel', end);
      D.raf = requestAnimationFrame(scrollLoop);
    }, true);
  })();

  // phone: swipe a song row to the right to add it to the queue (the row fills green as you drag; let go past the middle to add it)
  (function () {
    var S = null, swallow = 0, THRESH = 90;
    function end(e, cancelled) {
      if (!S) return;
      var d = S; S = null;
      d.row.classList.remove('swq', 'swq-ok'); d.row.style.removeProperty('--sw');
      if (!d.on) return;
      swallow = Date.now();
      if (!cancelled && d.dx >= THRESH) { var t = mz.byId.get(d.row.dataset.t); if (t) { mzQueueAdd(t); } }
    }
    document.addEventListener('pointerdown', function (e) {
      if (S || e.pointerType === 'mouse' || mz.theme !== 'spotify' || typeof mzIsMobile !== 'function' || !mzIsMobile()) return;
      var t = e.target; if (!t.closest || t.closest('button, input, .sp-grip, .star')) return;
      var row = t.closest('#wm-content .sp-row.trk[data-t]'); if (!row || row.querySelector('.sp-grip')) return;
      S = { row: row, x: e.clientX, y: e.clientY, dx: 0, on: false, id: e.pointerId };
    }, true);
    document.addEventListener('pointermove', function (e) {
      if (!S || e.pointerId !== S.id) return;
      var dx = e.clientX - S.x, dy = e.clientY - S.y;
      if (!S.on) {
        if (Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx)) { S = null; return; }          // it is a scroll
        if (dx > 14 && dx > Math.abs(dy) * 1.6) { S.on = true; S.row.classList.add('swq'); mzHaptic('tick'); } else return;
      }
      S.dx = Math.max(0, dx);
      var ok = S.dx >= THRESH;
      S.row.style.setProperty('--sw', Math.min(S.dx, 220) + 'px');
      if (ok !== S.row.classList.contains('swq-ok')) { S.row.classList.toggle('swq-ok', ok); if (ok) mzHaptic('tick'); }
    }, true);
    document.addEventListener('pointerup', function (e) { end(e, false); }, true);
    document.addEventListener('pointercancel', function (e) { if (S && S.on && S.dx >= THRESH) end(e, false); else end(e, true); }, true);
    document.addEventListener('click', function (e) { if (Date.now() - swallow < 450) { e.stopPropagation(); e.preventDefault(); } }, true);
  })();

  // desktop: press a row in a playlist and drag it somewhere else; the new order is saved when you let go
  (function () {
    var P = null, D = null, swallow = 0;
    function content() { return mzEl('wm-content'); }
    function move(e) {
      if (!D) return;
      D.cy = e.clientY;
      var y = D.cy - D.sy + (content().scrollTop - D.scroll0);
      if (!D.sel) D.row.style.transform = 'translateY(' + y + 'px)'; dragLayout(D, y);
    }
    function scrollLoop() {
      if (!D) return;
      var c = content(), r = c.getBoundingClientRect(), v = 0;
      if (D.cy < r.top + 70) v = -Math.ceil((r.top + 70 - D.cy) / 6);
      else if (D.cy > r.bottom - 70) v = Math.ceil((D.cy - (r.bottom - 70)) / 6);
      if (v) { c.scrollTop += v; move({ clientY: D.cy }); }
      D.raf = requestAnimationFrame(scrollLoop);
    }
    function start(e) {
      var row = P.row, list = row.parentElement, rows = Array.prototype.slice.call(list.querySelectorAll('.sp-row.trk')), from = rows.indexOf(row);
      var ids = mz.plCache[mz.view.key] || [], known = ids.filter(function (id) { return mz.byId.has(id); });
      var shown = rows.map(function (r) { return r.dataset.t; });
      if (from < 0 || shown.length !== known.length || shown.some(function (id, i) { return id !== known[i]; })) {   // sorted by a column: the rows are not in playlist order
        P = null; document.removeEventListener('pointermove', onMove); document.removeEventListener('pointerup', onUp); mzToast('Clear the sorting to reorder this playlist'); return;
      }
      D = { row: row, rows: rows, ids: shown, from: from, to: from, h: row.offsetHeight, top0: from * row.offsetHeight, sy: P.y, cy: e.clientY, scroll0: content().scrollTop, raf: 0, pid: mz.view.key };
      if (dsel.pid === D.pid && dsel.ids.size > 1 && dsel.ids.has(shown[from])) D.sel = dsel.ids;
      rows.forEach(function (r) { r.classList.add('moving'); if (D.sel && D.sel.has(r.dataset.t)) r.classList.add('dragging'); });
      row.classList.add('dragging'); content().classList.add('reordering');
      D.raf = requestAnimationFrame(scrollLoop);
    }
    function onMove(e) {
      if (!P) return;
      if (!D) { if (Math.abs(e.clientY - P.y) < 6 && Math.abs(e.clientX - P.x) < 6) return; start(e); if (!D) return; }
      move(e);
    }
    function onUp(e) {
      document.removeEventListener('pointermove', onMove); document.removeEventListener('pointerup', onUp); document.removeEventListener('pointercancel', onUp);
      P = null; if (!D) return;
      var d = D; D = null; cancelAnimationFrame(d.raf); swallow = Date.now();
      d.rows.forEach(function (r) { r.style.transform = ''; r.style.transition = ''; r.classList.remove('moving'); });
      d.rows.forEach(function (r) { r.classList.remove('dragging'); }); content().classList.remove('reordering');
      if (e.type === 'pointercancel' || d.to === d.from || mz.view.type !== 'playlist' || mz.view.key !== d.pid) return;
      var ids = mz.plCache[d.pid]; if (!ids) return;
      var at = []; ids.forEach(function (id, i) { if (mz.byId.has(id)) at.push(i); });         // tracks the library does not know keep their slots
      if (at.length !== d.rows.length) return;
      var shown = at.map(function (i) { return ids[i]; }), grabbed = shown[d.from];
      if (dsel.pid === d.pid && dsel.ids.size > 1 && dsel.ids.has(grabbed)) shown = groupShown(shown, dsel.ids, grabbed, d.to);
      else { var m = shown.splice(d.from, 1)[0]; shown.splice(d.to, 0, m); }
      var next = ids.slice(); at.forEach(function (i, k) { next[i] = shown[k]; });
      mz.plCache[d.pid] = next; mzRender();
      jpost('/api/music/playlist/' + encodeURIComponent(d.pid) + '/order', { ids: next, base: ids.length }).catch(function (err) {
        if (/changed elsewhere/.test(err.message || '')) { delete mz.plCache[d.pid]; mzToast('This playlist changed elsewhere. Reloaded it'); }
        else { mz.plCache[d.pid] = ids; mzToast('Could not save the new order'); }
        mzRender();
      });
    }
    document.addEventListener('pointerdown', function (e) {
      if (P || D || mz.theme !== 'spotify' || mz.view.type !== 'playlist' || edit || e.button !== 0 || e.pointerType !== 'mouse') return;
      if (typeof mzIsMobile === 'function' && mzIsMobile()) return;
      var t = e.target; if (!t.closest || t.closest('button, a, input, .star, .sp-lk')) return;
      var row = t.closest('#wm-content .sp-row.trk[data-t]'); if (!row || !row.closest('#music-screen')) return;
      P = { row: row, x: e.clientX, y: e.clientY };
      document.addEventListener('pointermove', onMove); document.addEventListener('pointerup', onUp); document.addEventListener('pointercancel', onUp);
    }, true);
    document.addEventListener('click', function (e) {                                      // letting go of a drag must not also play the track
      if (Date.now() - swallow < 350) { e.stopPropagation(); e.preventDefault(); }
    }, true);
  })();

  // Back from the left screen edge: the page follows the finger, and letting go far enough (or flicking) goes back
  (function () {
    var G = null, EDGE = 36;
    function content() { return mzEl('wm-content'); }
    function reset(animate) {
      var c = content(); if (!c) return;
      c.style.transition = animate ? 'transform .2s ease, opacity .2s ease' : 'none';
      c.style.transform = ''; c.style.opacity = '';
      if (animate) setTimeout(function () { c.style.transition = ''; }, 220);
    }
    document.addEventListener('touchstart', function (e) {
      G = null; var f = e.touches[0];
      if (!f || e.touches.length !== 1 || f.clientX > EDGE || mz.theme !== 'spotify' || !mzIsMobile() || edit || npIsOpen) return;
      if (typeof navCanBack !== 'function' || !navCanBack()) return;
      G = { x: f.clientX, y: f.clientY, on: false, v: 0, last: { x: f.clientX, t: performance.now() } };
    }, { capture: true, passive: true });
    document.addEventListener('touchmove', function (e) {
      if (!G) return;
      var f = e.touches[0], dx = f.clientX - G.x, dy = f.clientY - G.y, now = performance.now();
      if (!G.on) { if (Math.abs(dy) > Math.abs(dx) * 1.2 && Math.abs(dy) > 8) { G = null; return; } if (dx < 10) return; G.on = true; }
      G.v = 0.6 * G.v + 0.4 * ((f.clientX - G.last.x) / Math.max(1, now - G.last.t)); G.last = { x: f.clientX, t: now };
      var c = content(); if (!c) return;
      var w = window.innerWidth;
      c.style.transition = 'none'; c.style.transform = 'translateX(' + Math.max(0, dx) * 0.8 + 'px)'; c.style.opacity = String(1 - Math.min(.5, dx / w));
      if (!G.past && dx > w * 0.3) { G.past = true; mzHaptic('detent'); } else if (dx < w * 0.3) G.past = false;
    }, { capture: true, passive: true });
    function end(e) {
      var g = G; G = null; if (!g || !g.on) return;
      var go = e.type !== 'touchcancel' && (g.past || g.v > 0.6);
      reset(!go);
      if (go) { lastDragAt = Date.now(); history.back(); }
    }
    document.addEventListener('touchend', end, { capture: true, passive: true });
    document.addEventListener('touchcancel', end, { capture: true, passive: true });
  })();

  // Pull down at the top of a page to reload the library (the spinner follows the finger, then spins while it loads)
  (function () {
    var P = null, el = null, busy = false, LIMIT = 64;
    function node() {
      if (el && el.isConnected) return el;
      el = document.createElement('div'); el.className = 'sp-ptr';
      el.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v5h-5"/></svg>';
      (document.querySelector('#music-screen .wm') || document.body).appendChild(el); return el;
    }
    function paint(y, spin) {
      var n = node(); n.style.transition = spin === 'out' ? 'transform .22s ease, opacity .22s ease' : 'none';
      n.style.opacity = y > 4 || spin ? '1' : '0';
      n.style.transform = 'translate(-50%, ' + y + 'px)' + (spin ? '' : ' rotate(' + y * 4 + 'deg)');
      n.classList.toggle('spin', spin === true);
    }
    document.addEventListener('touchstart', function (e) {
      P = null; if (busy || mz.theme !== 'spotify' || !mzIsMobile() || e.touches.length !== 1 || edit) return;
      var c = mzEl('wm-content'); if (!c || !c.contains(e.target) || c.scrollTop > 0 || npIsOpen) return;
      if (e.target.closest('input, .sp-grip, .sp-cards, .sp-chips')) return;
      P = { x: e.touches[0].clientX, y: e.touches[0].clientY, on: false };
    }, { capture: true, passive: true });
    document.addEventListener('touchmove', function (e) {
      if (!P) return;
      var dy = e.touches[0].clientY - P.y, dx = e.touches[0].clientX - P.x, c = mzEl('wm-content');
      if (!P.on) { if (dy < -4 || Math.abs(dx) > Math.abs(dy)) { P = null; return; } if (dy < 12) return; if (c.scrollTop > 0) { P = null; return; } P.on = true; }
      var pull = Math.min(LIMIT + 16, (dy - 12) * 0.5); paint(pull + 8, false);
      if (pull >= LIMIT && !P.past) { P.past = true; mzHaptic('detent'); } else if (pull < LIMIT) P.past = false;
    }, { capture: true, passive: true });
    function release(e) {
      var p = P; P = null; if (!p || !p.on) return;
      if (p.past && e.type !== 'touchcancel') {
        busy = true; paint(LIMIT * 0.6 + 8, true); mz.freshNext = true;
        var t0 = Date.now();
        loadMusic().then(function () { return new Promise(function (r) { setTimeout(r, Math.max(0, 600 - (Date.now() - t0))); }); })
          .catch(function () { mzToast('Could not refresh'); })
          .then(function () { paint(-40, 'out'); busy = false; if (el) el.style.opacity = '0'; });
      } else paint(-40, 'out');
    }
    document.addEventListener('touchend', release, { capture: true, passive: true });
    document.addEventListener('touchcancel', release, { capture: true, passive: true });
  })();

  // Touch feedback the moment a finger lands (not after the browser has decided it is a tap); dropped as soon as the finger scrolls
  (function () {
    var SEL = '.sp-row, .sp-li, .sp-quick, .sp-rec, .sp-cardx, .sp-chip, .sp-tabbar button, .sp-qi-row, .sp-addrow, .sp-mi, .sp-topres, .sp-tile', cur = null, x0 = 0, y0 = 0;
    function clear() { if (cur) { cur.classList.remove('pressed'); cur = null; } }
    document.addEventListener('touchstart', function (e) {
      clear();
      var f = e.touches[0]; if (!f || e.touches.length > 1) return;
      var el = e.target.closest && e.target.closest(SEL); if (!el || !el.closest('#music-screen') || el.closest('.sp-editbar')) return;
      cur = el; x0 = f.clientX; y0 = f.clientY; el.classList.add('pressed');
    }, { capture: true, passive: true });
    document.addEventListener('touchmove', function (e) { var f = e.touches[0]; if (cur && f && (Math.abs(f.clientX - x0) > 6 || Math.abs(f.clientY - y0) > 6)) clear(); }, { capture: true, passive: true });
    ['touchend', 'touchcancel'].forEach(function (n) { document.addEventListener(n, function () { var el = cur; cur = null; if (el) setTimeout(function () { el.classList.remove('pressed'); }, 90); }, { capture: true, passive: true }); });
    document.addEventListener('scroll', clear, { capture: true, passive: true });
  })();

  // Scrolling must never open an artist or album: a finger that lands on a name to stop a fling, or drags across it, is not a tap
  (function () {
    var lastScroll = 0, t0 = null;
    document.addEventListener('scroll', function () { lastScroll = Date.now(); }, { capture: true, passive: true });
    document.addEventListener('touchstart', function (e) {
      var f = e.touches[0]; if (!f) return;
      t0 = { x: f.clientX, y: f.clientY, rolling: Date.now() - lastScroll < 180, moved: false };            // the list was still moving: this touch only stops it
    }, { capture: true, passive: true });
    document.addEventListener('touchmove', function (e) {
      var f = e.touches[0]; if (t0 && f && (Math.abs(f.clientX - t0.x) > 8 || Math.abs(f.clientY - t0.y) > 8)) t0.moved = true;
    }, { capture: true, passive: true });
    window.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('#music-screen a[data-act]'); if (!a) return;
      if (Date.now() - lastScroll < 120 || (t0 && (t0.rolling || t0.moved) && Date.now() - lastScroll < 400)) { e.stopPropagation(); e.preventDefault(); }
    }, true);
  })();

  // long press on a track inside a playlist (phone): the same sheet, with "Remove from this playlist" on top
  (function () {
    var timer = 0, sx = 0, sy = 0, swallow = 0;
    function rowOf(e) {
      if (mz.theme !== 'spotify' || typeof mzIsMobile !== 'function' || !mzIsMobile() || mz.view.type !== 'playlist' || edit) return null;
      if (e.target.closest && e.target.closest('.sp-grip')) return null;                    // the drag handle has its own gesture
      var c = e.target.closest ? e.target.closest('#wm-content .trk[data-t]') : null;
      return c && c.closest('#music-screen') ? c : null;
    }
    function cancel() { clearTimeout(timer); timer = 0; }
    document.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse') return;
      var r = rowOf(e); if (!r) return;
      sx = e.clientX; sy = e.clientY;
      timer = setTimeout(function () {
        timer = 0; var t = mz.byId.get(r.dataset.t); if (!t) return;
        swallow = Date.now(); SP.addMenu(null, t, { pid: mz.view.key });
      }, 480);
    }, true);
    document.addEventListener('pointermove', function (e) { if (timer && (Math.abs(e.clientX - sx) > 8 || Math.abs(e.clientY - sy) > 8)) cancel(); }, true);
    ['pointerup', 'pointercancel', 'scroll'].forEach(function (n) { document.addEventListener(n, cancel, true); });
    // press feedback for touch: only when the finger rests on something (a scroll or swipe never "presses" what it started on)
    (function () {
      var PRESS = '.sp-row, .sp-rec, .sp-chip, .sp-cardx, .sp-quick, .sp-topres, .sp-tile', timer = 0, el = null, x0 = 0, y0 = 0;
      function off() { clearTimeout(timer); if (el) el.classList.remove('pr'); el = null; }
      var scope = document.getElementById('music-screen') || document;
      scope.addEventListener('touchstart', function (e) {
        off(); var t = e.touches[0], hit = e.touches.length === 1 && e.target.closest && e.target.closest(PRESS); if (!hit) return;
        x0 = t.clientX; y0 = t.clientY; var h = hit;
        timer = setTimeout(function () { el = h; h.classList.add('pr'); }, 120);
      }, { passive: true });
      scope.addEventListener('touchmove', function (e) { var t = e.touches[0]; if (Math.abs(t.clientX - x0) > 6 || Math.abs(t.clientY - y0) > 6) off(); }, { passive: true });
      ['touchend', 'touchcancel'].forEach(function (n) { scope.addEventListener(n, function () { setTimeout(off, 60); }, { passive: true }); });
      scope.addEventListener('scroll', off, { capture: true, passive: true });
    })();
    document.addEventListener('click', function (e) { if (swallow && Date.now() - swallow < 700) { swallow = 0; e.stopPropagation(); e.preventDefault(); } }, true);
    document.addEventListener('contextmenu', function (e) { if (rowOf(e)) { e.preventDefault(); e.stopPropagation(); } }, true);   // else Android shows the desktop menu on a long press
  })();

  SP.initNP = function () {
    var n = sheet(), w = rootEl(); if (!n || !w) return;
    var tr = w.querySelector('.wm-transport');
    function phone() { return mz.theme === 'spotify' && mzIsMobile(); }

    // seek bar inside the sheet
    var sk = mzEl('sp-np-seek');
    function seekDur() { var t = mzCur(); return mz.remote ? (t && t.d) : ((musicAudio && isFinite(musicAudio.duration) && musicAudio.duration) || (t && t.d)); }
    sk.addEventListener('input', function () { mz.seeking = true; sk.style.setProperty('--p', sk.value / 10 + '%'); var d = seekDur(); if (d) mzEl('sp-np-cur').textContent = mzFmt(d * sk.value / 1000); });
    sk.addEventListener('change', function () { var d = seekDur(); if (d) mzMediaSeekTo(d * sk.value / 1000); mz.seeking = false; mzHaptic('tick'); });
    mzEl('sp-np-more').addEventListener('click', function (e) {
      e.stopPropagation();                                        // else the root click handler closes the menu straight away
      var t = mzCur(); if (!t) return;
      var r = e.currentTarget.getBoundingClientRect(); mzOpenMenu(r.left, r.bottom, t.f, false, null);
    });

    // Closing the player: pull it down while its content is at the top. Lower down, a drag is a scroll and the page does the scrolling.
    var sc = mzEl('sp-np-scroll'), td = null;
    n.addEventListener('touchstart', function (e) {
      if (!phone() || e.touches.length !== 1) { td = null; return; }
      var f = e.touches[0], now = performance.now();
      var caught = sheetFlying();
      if (caught && sc) sc.style.overflowY = 'hidden';                 // the content must not scroll along while the finger moves the sheet
      td = { x: f.clientX, y: f.clientY, drag: false, v: 0, t0: now, last: { y: f.clientY, t: now }, tgt: e.target, H: sheetH(), caught: caught, base: caught ? catchSheet() : 0 };
    }, { passive: true });
    n.addEventListener('touchmove', function (e) {
      if (!td) return;
      var f = e.touches[0], dy = f.clientY - td.y, dx = f.clientX - td.x;
      if (!td.drag && td.caught) { if (Math.abs(dy) < 2) return; td.drag = true; td.y = f.clientY; dy = 0; }      // caught mid-slide: follows the finger either way at once
      if (!td.drag) {
        if (td.tgt.closest && td.tgt.closest('input[type=range]')) { td = null; return; }                // the seek bar is dragged sideways: leave it alone
        if (sc && sc.scrollTop > 0) { td = null; return; }                                               // scrolled down: this is a scroll
        if (dy < 10 || Math.abs(dy) < Math.abs(dx) * 1.2) { if (dy < -4) td = null; return; }           // up or sideways is not a pull-down
        td.v = dy / Math.max(16, performance.now() - td.t0); td.drag = true; td.y = f.clientY - 10; dy = 10;
        if (sc) sc.style.overflowY = 'hidden';                                                           // the finger now moves the sheet: the content must not scroll along when it turns back up (put back in tEnd)
        clearTimeout(npHideT);
      }
      var now = performance.now(); td.v = 0.6 * td.v + 0.4 * ((f.clientY - td.last.y) / Math.max(1, now - td.last.t)); td.last = { y: f.clientY, t: now };
      var pos = Math.min(td.H, Math.max(0, td.base + dy));
      var past = pos > td.H * 0.18; if (past !== td.past) { td.past = past; mzHaptic('detent'); }      // a small buzz as you cross the point of no return
      dragY(pos);
    }, { passive: true });          // passive: the page is at its top and contained, so there is nothing to scroll, and the browser need not wait for this code before it moves on
    function tEnd(e) {
      if (sc) sc.style.overflowY = '';
      if (!td || !td.drag) { td = null; return; }
      var d = td, f = e.changedTouches[0]; td = null;
      lastDragAt = Date.now(); dragFlush();
      var h = d.H, dy = f.clientY - d.y, pos = Math.min(h, Math.max(0, d.base + dy));
      var closing = d.caught ? (d.v > 0.3 || (d.v >= -0.3 && pos > h * 0.5)) : (pos > h * 0.18 || d.v > 0.5);       // caught mid-slide: the direction you were going decides
      if (e.type !== 'touchcancel' && closing) {
        SP.npSet(false, true, d.v);
        if (nav.cur === 'music/player' && navCanBack()) history.back(); else if (!d.caught) navSet(mzRoute(mz.view));
      } else if (d.caught) {                                                                                                         // caught mid-close and let go going up: it opens again
        SP.npSet(true, true, d.v < -0.4 ? -d.v : 0);
        if (nav.cur !== 'music/player') navSet('music/player');
      } else setY(0, true, dur(npY, 0, 220, 380));                                                                                // not far enough: spring back
    }
    n.addEventListener('touchend', tEnd); n.addEventListener('touchcancel', tEnd);

    // Opening it: pull the mini player up (pointer events: the mini player has nothing to scroll)
    var g = null;
    function begin(e) {
      if (e.target.closest('button, input, a') || (e.pointerType === 'mouse' && e.button !== 0)) return;
      var cgt = sheetFlying();
      g = { id: e.pointerId, el: e.currentTarget, x0: e.clientX, y0: e.clientY, last: { y: e.clientY, t: performance.now() }, v: 0, moved: false, H: sheetH(), caught: cgt };
      g.base = cgt ? catchSheet() : g.H;
      if (!npIsOpen && mzCur()) npSync();                          // the player's content is built now, while the finger is still, so the first moves of the drag only move the sheet
      try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) {}      // keeps the drag alive when the pointer leaves the small mini player
    }
    function move(e) {
      if (!g || e.pointerId !== g.id) return;
      var dy = e.clientY - g.y0;                                   // < 0 = finger moving up
      if (!g.moved && !g.h) {                                      // sideways on the mini player: skip to the next / previous song
        var dx0 = e.clientX - g.x0;
        if (Math.abs(dx0) >= 10 && Math.abs(dx0) > Math.abs(dy) * 1.2) g.h = true;
      }
      if (g.h) {
        var dx = e.clientX - g.x0, nw = mzEl('wm-now');
        if (!g.hp && Math.abs(dx) > 70) { g.hp = true; mzHaptic('detent'); } else if (g.hp && Math.abs(dx) <= 70) g.hp = false;
        if (tr) tr.classList.add('swiping');
        if (nw) { nw.style.transition = 'none'; nw.style.transform = 'translateX(' + dx * 0.55 + 'px)'; nw.style.opacity = String(Math.max(.35, 1 - Math.abs(dx) / 320)); }
        return;
      }
      if (!g.moved) {
        if (Math.abs(dy) < (g.caught ? 2 : 8)) return;
        if (dy > 0 && !g.caught) { g = null; return; }             // the mini player only opens upward (unless the sheet was caught mid-slide)
        g.moved = true;
        clearTimeout(npHideT);
        n.style.visibility = 'visible'; n.classList.add('shown');
        npSync(); if (!g.caught) setY(g.H, false);
      }
      var now = performance.now();
      g.v = 0.6 * g.v + 0.4 * ((e.clientY - g.last.y) / Math.max(1, now - g.last.t));    // px/ms, smoothed
      g.last = { y: e.clientY, t: now };
      var h = g.H, pos = Math.min(h, Math.max(0, g.base + dy));
      var past = pos < h * 0.8; if (past !== g.past) { g.past = past; mzHaptic('detent'); }
      dragY(pos);
    }
    function end(e) {
      if (!g || e.pointerId !== g.id) return;
      var d = g; g = null;
      try { d.el.releasePointerCapture(e.pointerId); } catch (_) {}
      if (d.h) {
        var dxe = e.clientX - d.x0, nw2 = mzEl('wm-now'); lastDragAt = Date.now();
        if (nw2) { nw2.style.transition = 'transform .22s ease, opacity .22s ease'; nw2.style.transform = ''; nw2.style.opacity = ''; setTimeout(function () { nw2.style.transition = ''; if (tr) tr.classList.remove('swiping'); }, 260); }
        if (Math.abs(dxe) > 70 && mzCur()) { if (dxe < 0) nextSong(); else prevSong(); }
        return;
      }
      if (!d.moved) { if (d.caught) SP.npSet(npIsOpen, true); else if (phone() && mzCur()) mzNowTap(); return; }   // a tap on the mini player (the click is retargeted by the capture, so handle it here)
      lastDragAt = Date.now(); dragFlush();
      var h = d.H, dy = e.clientY - d.y0, pos = Math.min(h, Math.max(0, d.base + dy));
      var opening = d.caught ? (d.v < -0.3 || (d.v <= 0.3 && pos < h * 0.5)) : (pos < h * 0.8 || d.v < -0.4);
      if (opening) { if (nav.cur !== 'music/player') navSet('music/player'); SP.npSet(true, true, Math.abs(d.v) > 0.4 ? Math.abs(d.v) : 0); }
      else SP.npSet(false, true, Math.abs(d.v) > 0.4 ? Math.abs(d.v) : 0);
    }
    function cancel(e) { if (g && e.pointerId === g.id) { var d = g; g = null; if (d.h) { var nw = mzEl('wm-now'); if (tr) tr.classList.remove('swiping'); if (nw) { nw.style.transform = ''; nw.style.opacity = ''; nw.style.transition = ''; } } else if (d.moved) SP.npSet(false, true); } }
    if (tr) {
      tr.addEventListener('pointerdown', function (e) { if (phone() && mzCur()) begin(e); });
      tr.addEventListener('pointermove', move);
      tr.addEventListener('pointerup', end);
      tr.addEventListener('pointercancel', cancel);
    }
    window.addEventListener('resize', function () { if (n.classList.contains('shown') && !g && !td) setY(0, false); });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', SP.initNP); else SP.initNP();

  return SP;
})();
