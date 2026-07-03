const ENTERPRISE_EMAIL = "daniel@ageos-labs.com";

const RESET = "\x1b[0m";
const MUTED = "\x1b[2;38;5;245m";
const SUCCESS = "\x1b[1;38;5;157m";
const STARSHIP_CHAR = "\x1b[1;38;2;134;239;172m❯ \x1b[0m";
const HIGHLIGHT = "\x1b[1;38;2;134;239;172m";
const DIM = "\x1b[2;38;5;245m";

function starshipSegment([r, g, b], text) {
  return `\x1b[48;2;${r};${g};${b}m\x1b[38;2;255;255;255m ${text} ${RESET}`;
}

function writeStarshipPrompt(term, segments = []) {
  if (segments.length > 0) {
    term.write(segments.join(""));
    term.writeln("");
  }

  term.write(STARSHIP_CHAR);
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const text = button.getAttribute("data-copy");

    try {
      await navigator.clipboard.writeText(text);
      const previousLabel = button.textContent;
      button.textContent = "Copied";
      button.classList.add("is-copied");

      window.setTimeout(() => {
        button.textContent = previousLabel;
        button.classList.remove("is-copied");
      }, 1400);
    } catch {
      button.textContent = "Select text";
    }
  });
});

const demoTerminalMount = document.querySelector("#demo-terminal");
let demoTerminalInitialized = false;

function getFitAddonClass() {
  const fitAddon = window.FitAddon;

  if (typeof fitAddon === "function") {
    return fitAddon;
  }

  return fitAddon?.FitAddon;
}

function initDemoTerminal() {
  if (demoTerminalInitialized) {
    return true;
  }

  const FitAddonClass = getFitAddonClass();

  if (!demoTerminalMount || typeof window.Terminal !== "function" || typeof FitAddonClass !== "function") {
    return false;
  }

  demoTerminalInitialized = true;

  const term = new Terminal({
    cursorBlink: true,
    blinkIntervalDuration: 600,
    cursorStyle: "block",
    cursorInactiveStyle: "block",
    disableStdin: true,
    allowTransparency: true,
    fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace',
    fontSize: 14,
    lineHeight: 1.35,
    scrollback: 64,
    theme: {
      background: "rgba(0, 0, 0, 0)",
      foreground: "#dbeafe",
      cursor: "#86efac",
      cursorAccent: "#020617",
      selectionBackground: "rgba(103, 232, 249, 0.18)",
      black: "#020617",
      red: "#fb7185",
      green: "#86efac",
      yellow: "#facc15",
      blue: "#93c5fd",
      magenta: "#c4b5fd",
      cyan: "#67e8f9",
      white: "#dbeafe",
    },
  });

  const fitAddon = new FitAddonClass();
  term.loadAddon(fitAddon);
  term.open(demoTerminalMount);

  let demoStarted = false;

  const startDemo = () => {
    fitAddon.fit();

    if (term.cols > 0 && term.rows > 0) {
      if (!demoStarted) {
        demoStarted = true;
        runDemoLoop();
      }
      return true;
    }

    return false;
  };

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const bubbleHubSegments = [starshipSegment([0, 111, 189], "~")];

  function ensureCursorVisible() {
    term.options.cursorBlink = true;
    term.options.blinkIntervalDuration = 600;
    term.focus();
    term.write("\x1b[?25h");
  }

  async function pauseAtPrompt(segments, delay) {
    ensureCursorVisible();
    writeStarshipPrompt(term, segments);
    await sleep(delay);
  }

  async function typeResponse(text, speed = 24) {
    term.focus();
    term.write(` ${MUTED}`);

    for (const character of text) {
      term.write(character);
      await sleep(speed);
    }

    term.write(RESET);
    term.writeln("");
    await sleep(420);
  }

  async function typeCommand(segments, command, { skipPrompt = false, speed = 26 } = {}) {
    ensureCursorVisible();

    if (!skipPrompt) {
      writeStarshipPrompt(term, segments);
    }

    for (const character of command) {
      term.write(character);
      await sleep(speed);
    }
  }

  async function typeMuted(text, speed = 24) {
    term.focus();
    term.write(`${MUTED}  │ ${RESET}${MUTED}`);

    for (const character of text) {
      term.write(character);
      await sleep(speed);
    }

    term.write(RESET);
    term.writeln("");
    await sleep(520);
  }
  async function typeNormal(text, speed = 24) {
    term.focus();
    term.write(`${RESET}`);

    for (const character of text) {
      term.write(character);
      await sleep(speed);
    }
  }

  function viewportRow(bufferRow) {
    return bufferRow - term.buffer.active.baseY + 1;
  }

  async function showPermissionMenu(question, options) {
    const targetIndex = Math.floor(Math.random() * options.length);
    const questionLine =
      starshipSegment([147, 51, 234], "openclaw") + ` ${question}${RESET}`;

    if (term.buffer.active.cursorX > 0) {
      term.writeln("");
    }

    const questionRow = term.buffer.active.cursorY;
    term.writeln(questionLine);
    const menuStartRow = Math.max(term.buffer.active.cursorY, questionRow + 1);
    const confirmRow = menuStartRow + options.length;

    let activeIndex = 0;

    const drawQuestion = () => {
      term.write(`\x1b[${viewportRow(questionRow)};1H${questionLine}\x1b[K`);
    };

    const drawMenu = () => {
      drawQuestion();

      for (let index = 0; index < options.length; index += 1) {
        const line =
          index === activeIndex
            ? `${HIGHLIGHT}❯ ${options[index]}${RESET}`
            : `  ${DIM}${options[index]}${RESET}`;
        term.write(`\x1b[${viewportRow(menuStartRow + index)};1H${line}\x1b[K`);
      }
    };

    term.scrollToLine(Math.max(0, questionRow - 1));
    drawMenu();
    await sleep(480);

    while (activeIndex !== targetIndex) {
      activeIndex += activeIndex < targetIndex ? 1 : -1;
      drawMenu();
      await sleep(320);
    }

    await sleep(420);
    drawQuestion();
    term.write(
      `\x1b[${viewportRow(confirmRow)};1H${HIGHLIGHT}✓ ${options[targetIndex]}${RESET}\x1b[K`,
    );
    term.writeln("");

    const buffer = term.buffer.active;
    term.write(`\x1b[${viewportRow(buffer.cursorY)};${buffer.cursorX + 1}H`);
    await sleep(420);

    return targetIndex;
  }

  async function runDemoOnce() {
    term.focus();

    await typeCommand(bubbleHubSegments, 'bubble prompt "Hello, how are you?"');
    term.writeln("");
    await typeMuted("Hi! I'm a local nemotron, how can I help you today?");
    await sleep(700);
    await typeCommand([], "bubble run --binary ./openclaw", { skipPrompt: false });
    term.writeln("");
    await typeMuted("openclaw agent is reading your WhatsApp messages");
    await sleep(700);
    await showPermissionMenu("Allow agent to use WhatsApp?", ["Always", "Never", "Ask every time"]);
    term.writeln("");
    term.writeln("");
    await typeNormal("updating agent manifest");
    await sleep(2200);

  }

  async function runDemoLoop() {
    while (true) {
      term.reset();
      await runDemoOnce();
    }
  }

  const resizeTerminal = () => {
    fitAddon.fit();
  };

  window.addEventListener("resize", resizeTerminal);

  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(resizeTerminal);
    resizeObserver.observe(demoTerminalMount);
  }

  if (!startDemo()) {
    const startWhenSized = () => {
      if (startDemo()) {
        sizeObserver.disconnect();
      }
    };

    const sizeObserver = new ResizeObserver(startWhenSized);
    sizeObserver.observe(demoTerminalMount);
    window.setTimeout(startWhenSized, 250);
    window.setTimeout(startWhenSized, 1000);
  }

  return true;
}

function bootDemoTerminal(attempt = 0) {
  if (initDemoTerminal()) {
    return;
  }

  if (attempt < 50) {
    window.setTimeout(() => bootDemoTerminal(attempt + 1), 100);
  }
}

bootDemoTerminal();

const downloadForm = document.querySelector("#download-form");

downloadForm?.addEventListener("submit", (event) => {
  event.preventDefault();

  const formData = new FormData(downloadForm);
  const os = formData.get("os")?.toString();

  if (os === "linux" || os === "windows") {
    window.location.href = `/download/${os}`;
  }
});

const enterpriseForm = document.querySelector("#enterprise-form");

enterpriseForm?.addEventListener("submit", (event) => {
  event.preventDefault();

  const formData = new FormData(enterpriseForm);
  const name = formData.get("name")?.toString().trim() || "Unknown";
  const email = formData.get("email")?.toString().trim() || "Unknown";
  const company = formData.get("company")?.toString().trim() || "Unknown";
  const message = formData.get("message")?.toString().trim() || "";

  const subject = encodeURIComponent(`BubbleHub enterprise inquiry from ${company}`);
  const body = encodeURIComponent(
    [
      `Name: ${name}`,
      `Email: ${email}`,
      `Company: ${company}`,
      "",
      "What they want to run locally:",
      message,
    ].join("\n"),
  );

  window.location.href = `mailto:${ENTERPRISE_EMAIL}?subject=${subject}&body=${body}`;
});

function initAgentMarquee() {
  const track = document.querySelector(".agent-marquee-track");
  const group = track?.querySelector(".agent-marquee-group");

  if (!track || !group || track.dataset.marqueeReady === "true") {
    return;
  }

  track.dataset.marqueeReady = "true";

  const clone = group.cloneNode(true);
  clone.setAttribute("aria-hidden", "true");
  clone.querySelectorAll("a").forEach((link) => {
    link.tabIndex = -1;
    link.removeAttribute("aria-label");
    link.querySelectorAll("img").forEach((image) => {
      image.alt = "";
    });
  });
  track.appendChild(clone);
}

initAgentMarquee();

function initDocsCodeCopy() {
  document.querySelectorAll("[data-copy-code]").forEach((button) => {
    button.addEventListener("click", async () => {
      const code = button.closest(".docs-code-block")?.querySelector("code")?.textContent || "";
      const previousLabel = button.textContent;

      try {
        await navigator.clipboard.writeText(code);
        button.textContent = "Copied";
        button.classList.add("is-copied");

        window.setTimeout(() => {
          button.textContent = previousLabel;
          button.classList.remove("is-copied");
        }, 1400);
      } catch {
        button.textContent = "Select text";
      }
    });
  });
}

function initDocsSearch() {
  const input = document.querySelector("[data-docs-search]");
  const results = document.querySelector("[data-docs-search-results]");

  if (!input || !results) {
    return;
  }

  let searchIndex = [];
  let isLoaded = false;

  const loadIndex = async () => {
    if (isLoaded) {
      return searchIndex;
    }

    isLoaded = true;
    const indexUrl = input.getAttribute("data-search-index");

    try {
      const response = await fetch(indexUrl);
      if (!response.ok) {
        throw new Error(`Docs search index failed: ${response.status}`);
      }
      searchIndex = await response.json();
    } catch {
      searchIndex = [];
    }

    return searchIndex;
  };

  const clearResults = () => {
    results.hidden = true;
    results.replaceChildren();
  };

  const renderResults = (matches, query) => {
    results.replaceChildren();

    if (matches.length === 0) {
      const empty = document.createElement("div");
      empty.className = "docs-search-empty";
      empty.textContent = `No docs found for "${query}".`;
      results.append(empty);
      results.hidden = false;
      return;
    }

    matches.slice(0, 6).forEach((entry) => {
      const link = document.createElement("a");
      link.className = "docs-search-result";
      link.href = entry.href;

      const title = document.createElement("strong");
      title.textContent = entry.title;
      const description = document.createElement("span");
      description.textContent = entry.description;

      link.append(title, description);
      results.append(link);
    });

    results.hidden = false;
  };

  const scoreEntry = (entry, terms) => {
    const title = entry.title.toLowerCase();
    const description = entry.description.toLowerCase();
    const text = entry.text.toLowerCase();

    return terms.reduce((score, term) => {
      if (title.includes(term)) {
        return score + 4;
      }
      if (description.includes(term)) {
        return score + 2;
      }
      if (text.includes(term)) {
        return score + 1;
      }
      return score;
    }, 0);
  };

  input.addEventListener("input", async () => {
    const query = input.value.trim().toLowerCase();

    if (query.length < 2) {
      clearResults();
      return;
    }

    const terms = query.split(/\s+/).filter(Boolean);
    const index = await loadIndex();
    const matches = index
      .map((entry) => ({ ...entry, score: scoreEntry(entry, terms) }))
      .filter((entry) => entry.score > 0)
      .sort((left, right) => right.score - left.score);

    renderResults(matches, query);
  });

  document.addEventListener("click", (event) => {
    if (!results.contains(event.target) && event.target !== input) {
      clearResults();
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      clearResults();
      input.blur();
    }
  });
}

initDocsCodeCopy();
initDocsSearch();
