const markedApi = (window.marked && window.marked.marked) || window.marked;

const state = {
  skills: [],
  query: "",
  repo: "liamamilin/skills",
  blobBase: "",
  rawBase: "",
  ready: false,
  failed: false,
};

const app = document.querySelector("#app");
let observer = null;
let composing = false;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function iconSearch() {
  return '<svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="6.5"/><path d="M16 16.5 20.5 21"/></svg>';
}

function iconSun() {
  return '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3.4"/><path d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5 5l1.6 1.6M17.4 17.4 19 19M19 5l-1.6 1.6M6.6 17.4 5 19"/></svg>';
}

function iconMoon() {
  return '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M16.2 13.4A6.2 6.2 0 0 1 10.6 4.8 6.6 6.6 0 1 0 16.2 13.4Z"/></svg>';
}

function themeName() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  try { localStorage.setItem("skills-theme", theme); } catch (e) {}
  const btn = document.querySelector("[data-theme-toggle]");
  if (!btn) return;
  const nextDark = theme !== "dark";
  btn.innerHTML = nextDark ? iconMoon() : iconSun();
  btn.setAttribute("aria-label", nextDark ? "切换到深色" : "切换到浅色");
}

function route() {
  let hash = location.hash.replace(/^#/, "");
  try { hash = decodeURIComponent(hash); } catch (e) {}
  if (!hash.startsWith("/")) hash = `/${hash}`;
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "s" && parts[1]) {
    return { name: "skill", slug: parts[1], example: parts[2] || "" };
  }
  return { name: "home" };
}

function skillHref(slug, example) {
  const base = `#/s/${encodeURIComponent(slug)}`;
  return example ? `${base}/${encodeURIComponent(example)}` : base;
}

function norm(value) {
  return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function haystack(skill) {
  return norm([
    skill.name,
    skill.description,
    skill.body,
    ...(skill.examples || []).flatMap((item) => [item.title, item.body]),
  ].join("\n"));
}

function matches(skill, query) {
  const terms = norm(query).split(" ").filter(Boolean);
  if (!terms.length) return true;
  const hay = skill._hay || "";
  return terms.every((term) => hay.includes(term));
}

function inlineText(tokens) {
  if (!tokens) return "";
  return tokens.map((token) => {
    if (token.tokens && token.tokens.length) return inlineText(token.tokens);
    return token.text || "";
  }).join("");
}

function safeHref(href) {
  const value = String(href || "").trim();
  if (!value) return "";
  if (/^(javascript|data):/i.test(value)) return "";
  return value;
}

function resolveHref(href, filePath, kind) {
  if (!href) return "";
  if (/^(https?:|mailto:|#)/i.test(href)) return href;
  const base = kind === "raw" ? state.rawBase : state.blobBase;
  if (!base) return href;
  const dir = filePath && filePath.includes("/") ? filePath.slice(0, filePath.lastIndexOf("/") + 1) : "";
  const combined = `${dir}${String(href).replace(/^\.\//, "")}`;
  const parts = [];
  for (const part of combined.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  return base + parts.map((part) => encodeURIComponent(part)).join("/");
}

function renderMarkdown(markdown, filePath, prefix) {
  const toc = [];
  let count = 0;
  if (!markedApi || typeof markedApi.parse !== "function") {
    return { html: `<pre>${esc(markdown || "")}</pre>`, toc };
  }
  const renderer = new markedApi.Renderer();
  renderer.heading = function heading({ tokens, depth }) {
    const html = this.parser.parseInline(tokens);
    const id = `${prefix}-h-${++count}`;
    toc.push({ depth, text: inlineText(tokens), id });
    return `<h${depth} id="${id}">${html}</h${depth}>\n`;
  };
  renderer.html = function dropHtml() { return ""; };
  renderer.link = function link({ href, title, tokens }) {
    const text = this.parser.parseInline(tokens);
    const url = safeHref(resolveHref(href, filePath, "blob"));
    const titleAttr = title ? ` title="${esc(title)}"` : "";
    const external = /^https?:/i.test(url) ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a href="${esc(url)}"${titleAttr}${external}>${text}</a>`;
  };
  renderer.image = function image({ href, title, text }) {
    const url = safeHref(resolveHref(href, filePath, "raw"));
    const titleAttr = title ? ` title="${esc(title)}"` : "";
    return `<img src="${esc(url)}" alt="${esc(text || "")}"${titleAttr}>`;
  };
  let html = "";
  try {
    html = markedApi.parse(markdown || "", { renderer, gfm: true, breaks: false });
  } catch (e) {
    html = `<pre>${esc(markdown || "")}</pre>`;
  }
  return { html, toc };
}

function visibleToc(toc) {
  if (!toc.length) return [];
  if (toc.some((item) => item.depth >= 2)) {
    return toc.filter((item) => item.depth === 2 || item.depth === 3);
  }
  return toc.filter((item) => item.depth === 1);
}

function tocList(items) {
  if (!items.length) return "";
  return `<ol>${items.map((item) => `<li><a href="#${item.id}" data-heading="${esc(item.id)}" data-depth="${item.depth}">${esc(item.text)}</a></li>`).join("")}</ol>`;
}

function mount() {
  const dark = themeName() === "dark";
  app.innerHTML = `
    <header class="header">
      <div class="wrap header-inner">
        <a class="brand" href="#/">
          <span class="seal" aria-hidden="true">技</span>
          <span class="brand-name" id="site-title">技能仓库</span>
        </a>
        <form class="search" role="search">
          ${iconSearch()}
          <input id="q" type="text" placeholder="搜索" aria-label="搜索" autocomplete="off" enterkeyhint="search">
          <button class="clear" type="button" data-clear hidden aria-label="清除">×</button>
        </form>
        <span class="grow"></span>
        <button class="icon-btn" type="button" data-theme-toggle aria-label="${dark ? "切换到浅色" : "切换到深色"}">${dark ? iconSun() : iconMoon()}</button>
      </div>
    </header>
    <main>
      <div class="wrap" id="view" aria-labelledby="site-title"></div>
    </main>
    <p class="sr" id="copy-status" aria-live="polite"></p>
  `;
  const input = document.querySelector("#q");
  const form = document.querySelector(".search");
  form.addEventListener("submit", (event) => event.preventDefault());
  input.addEventListener("compositionstart", () => { composing = true; });
  input.addEventListener("compositionend", () => {
    composing = false;
    onQuery(input.value);
  });
  input.addEventListener("input", () => {
    syncClear();
    if (!composing) onQuery(input.value);
  });
  app.addEventListener("click", onClick);
  app.addEventListener("keydown", onTabKey);
  window.addEventListener("hashchange", render);
  render();
}

function syncClear() {
  const input = document.querySelector("#q");
  const clear = document.querySelector("[data-clear]");
  if (input && clear) clear.hidden = !input.value;
}

function onQuery(value) {
  state.query = value;
  const current = route();
  if (current.name !== "home") {
    if (location.hash !== "#/" && location.hash !== "") {
      location.hash = "#/";
      return;
    }
  }
  render();
}

function onClick(event) {
  const themeBtn = event.target.closest("[data-theme-toggle]");
  if (themeBtn) {
    applyTheme(themeName() === "dark" ? "light" : "dark");
    return;
  }
  const clearBtn = event.target.closest("[data-clear]");
  if (clearBtn) {
    const input = document.querySelector("#q");
    input.value = "";
    syncClear();
    input.focus();
    onQuery("");
    return;
  }
  const copyBtn = event.target.closest("[data-copy]");
  if (copyBtn) {
    event.preventDefault();
    copyRaw(copyBtn);
    return;
  }
  const heading = event.target.closest("[data-heading]");
  if (heading) {
    event.preventDefault();
    const node = document.getElementById(heading.getAttribute("data-heading"));
    if (node) node.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function onTabKey(event) {
  if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
  const tab = event.target.closest?.('[role="tab"]');
  if (!tab) return;
  const tabs = [...tab.parentElement.querySelectorAll('[role="tab"]')];
  const index = tabs.indexOf(tab);
  if (index < 0) return;
  event.preventDefault();
  const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
  next.focus();
  if (next.getAttribute("href")) location.hash = next.getAttribute("href");
}

async function copyRaw(button) {
  const skill = currentSkill();
  const status = document.querySelector("#copy-status");
  if (!skill) return;
  let ok = false;
  try {
    await navigator.clipboard.writeText(skill.raw);
    ok = true;
  } catch (e) {
    const area = document.createElement("textarea");
    area.value = skill.raw;
    document.body.appendChild(area);
    area.select();
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    area.remove();
  }
  const message = ok ? "已复制" : "复制失败";
  button.textContent = message;
  if (status) status.textContent = message;
  window.setTimeout(() => {
    if (button.isConnected) button.textContent = "复制 SKILL.md";
  }, 1600);
}

function currentSkill() {
  const current = route();
  if (current.name !== "skill") return null;
  return state.skills.find((skill) => skill.slug === current.slug) || null;
}

function render() {
  const view = document.querySelector("#view");
  if (!view) return;
  document.title = "技能仓库";
  if (!state.ready) {
    view.innerHTML = `<p class="empty">${state.failed ? "无法加载技能目录" : "加载中"}</p>`;
    return;
  }
  const current = route();
  if (current.name === "skill") renderSkill(view, current);
  else renderHome(view);
  watchHeadings();
}

function renderHome(view) {
  const list = state.skills.filter((skill) => matches(skill, state.query));
  if (!state.skills.length) {
    view.innerHTML = '<p class="empty">还没有技能</p>';
    return;
  }
  if (!list.length) {
    view.innerHTML = '<p class="empty">无结果</p>';
    return;
  }
  view.innerHTML = `<div class="grid">${list.map(cardHtml).join("")}</div>`;
}

function cardHtml(skill) {
  const count = (skill.examples || []).length;
  return `<a class="card" href="${skillHref(skill.slug)}" data-skill="${esc(skill.slug)}">
    <h2>${esc(skill.name)}</h2>
    <p>${esc(skill.description)}</p>
    <div class="card-foot"><span class="count">${count} 个示例</span><span class="go" aria-hidden="true">→</span></div>
  </a>`;
}

function renderSkill(view, current) {
  const skill = state.skills.find((item) => item.slug === current.slug);
  if (!skill) {
    document.title = "没有这个技能 · 技能仓库";
    view.innerHTML = '<p class="empty">没有这个技能</p><p class="kicker"><a href="#/">全部技能</a></p>';
    return;
  }
  document.title = `${skill.name} · 技能仓库`;
  const rendered = renderMarkdown(skill.body, skill.path, "sk");
  const skillToc = visibleToc(rendered.toc);
  const examples = skill.examples || [];
  let example = examples.find((item) => item.slug === current.example) || examples[0] || null;
  let exampleHtml = "";
  let exampleToc = [];
  if (example) {
    const exampleRendered = renderMarkdown(example.body, example.path, "ex");
    exampleToc = visibleToc(exampleRendered.toc);
    const tabs = examples.map((item) => {
      const selected = item.slug === example.slug;
      return `<a class="tab" role="tab" id="tab-${esc(item.slug)}" href="${skillHref(skill.slug, item.slug)}" aria-selected="${selected ? "true" : "false"}" title="${esc(item.title)}">${esc(item.title)}</a>`;
    }).join("");
    exampleHtml = `
      <h2 class="section-label" id="examples">示例</h2>
      <div class="tabs" role="tablist" aria-label="示例">${tabs}</div>
      <div class="prose" role="tabpanel" aria-labelledby="tab-${esc(example.slug)}">${exampleRendered.html}</div>
    `;
  }
  const tocHtml = [
    skillToc.length ? `<div class="toc-label">正文</div>${tocList(skillToc)}` : "",
    exampleToc.length ? `<div class="toc-label">示例</div>${tocList(exampleToc)}` : "",
  ].join("");
  view.innerHTML = `
    <article>
      <p class="kicker"><a href="#/">全部技能</a></p>
      <h1 class="page-title">${esc(skill.name)}</h1>
      <p class="lead">${esc(skill.description)}</p>
      <div class="actions">
        <button class="btn primary" type="button" data-copy>复制 SKILL.md</button>
        <a class="btn" href="${esc(skill.url)}" target="_blank" rel="noopener noreferrer">在 GitHub 打开</a>
      </div>
      <div class="detail${tocHtml ? " has-toc" : ""}">
        ${tocHtml ? `<nav class="toc" aria-label="目录">${tocHtml}</nav>` : ""}
        <div class="detail-main">
          <div class="prose">${rendered.html}</div>
          ${exampleHtml}
        </div>
      </div>
    </article>
  `;
}

function watchHeadings() {
  if (observer) observer.disconnect();
  observer = null;
  const links = [...document.querySelectorAll(".toc [data-heading]")];
  if (!links.length) return;
  const heads = links.map((link) => document.getElementById(link.getAttribute("data-heading"))).filter(Boolean);
  const mark = () => {
    const line = 110;
    let current = heads[0];
    for (const head of heads) {
      if (head.getBoundingClientRect().top <= line) current = head;
    }
    for (const link of links) {
      link.classList.toggle("active", current && link.getAttribute("data-heading") === current.id);
    }
  };
  mark();
  window.addEventListener("scroll", mark, { passive: true });
  observer = { disconnect() { window.removeEventListener("scroll", mark); } };
}

async function load() {
  try {
    const response = await fetch(new URL("skills.json", document.baseURI), { cache: "no-cache" });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    state.repo = data.repo || state.repo;
    state.blobBase = data.blobBase || "";
    state.rawBase = data.rawBase || "";
    state.skills = (data.skills || []).map((skill) => {
      skill.examples = skill.examples || [];
      skill._hay = haystack(skill);
      return skill;
    });
    state.ready = true;
  } catch (e) {
    state.failed = true;
    state.ready = false;
  }
  render();
}

mount();
load();
