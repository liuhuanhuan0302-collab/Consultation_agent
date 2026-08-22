/** 报告 HTML 的清洗与渲染工具 — 公开报告页与后台详情共用。 */

export function escapeHtmlText(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function reportHtmlToPlainText(value: string): string {
  const container = document.createElement("div");
  container.innerHTML = value
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(?:h[1-6]|p|section|div|li|tr)>/gi, "\n");
  return (container.textContent || "").replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

function inlineMarkdown(value: string): string {
  return escapeHtmlText(value).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function cleanAdvisorText(value: string): string {
  let cleaned = value.trim();
  const markers = ["本次诊断结果显示", "本次诊断显示", "诊断结果显示"];
  const positions = markers.map((marker) => cleaned.indexOf(marker)).filter((index) => index >= 0);
  if (positions.length) {
    cleaned = cleaned.slice(Math.min(...positions));
  }
  return cleaned
    .replace(/^好的，[\s\S]*?\n+/, "")
    .replace(/^---+\s*/, "")
    .replace(/^#{1,6}\s*\*\*.*?报告\*\*\s*/m, "")
    .replace(/^\*\*(致|发件人|主题)[:：]\*\*.*?\n/gm, "")
    .replace(/^\*\*(致|发件人|主题)[:：].*?\*\*\s*.*?\n/gm, "")
    .replace(/^尊敬的.*?团队[，,：:]?\s*/, "")
    .trim();
}

function renderAdvisorText(value: string): string {
  const lines = cleanAdvisorText(value)
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?[^>]+>/g, "")
    .split("\n")
    .map((line) => line.trim());
  const parts: string[] = [];
  let listItems: string[] = [];

  const flushList = () => {
    if (listItems.length) {
      parts.push(`<ul>${listItems.join("")}</ul>`);
      listItems = [];
    }
  };

  for (const line of lines) {
    if (!line || line === "---" || line.startsWith("```")) {
      flushList();
      continue;
    }
    const heading = line.match(/^#{1,6}\s*(.+)$/);
    if (heading) {
      flushList();
      const title = heading[1].replace(/^\*\*|\*\*$/g, "").trim();
      if (title.includes("诊断补充建议报告") || title.includes("管理摘要")) continue;
      parts.push(`<h4>${inlineMarkdown(title)}</h4>`);
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      listItems.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      continue;
    }
    parts.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  flushList();
  return parts.join("");
}

export function normalizeReportHtml(value: string): string {
  const normalized = value.replace(/<div class="report-ai-text">([\s\S]*?)<\/div>/g, (match, content: string) => {
    if (/<(?:h4|p|ul|ol|li)\b/i.test(content)) return match;
    return `<div class="report-ai-text">${renderAdvisorText(content)}</div>`;
  });
  return sanitizeReportHtml(normalized);
}

export function sanitizeReportHtml(value: string): string {
  const allowedTags = new Set(["ARTICLE", "SECTION", "H2", "H3", "H4", "P", "STRONG", "EM", "UL", "OL", "LI", "TABLE", "THEAD", "TBODY", "TR", "TH", "TD", "DIV", "SPAN", "BR", "A"]);
  const container = document.createElement("div");
  container.innerHTML = value;
  for (const paragraph of Array.from(container.querySelectorAll("p"))) {
    if ((paragraph.textContent || "").trim().startsWith("适用方向")) paragraph.remove();
  }
  for (const element of Array.from(container.querySelectorAll("*"))) {
    if (!allowedTags.has(element.tagName)) {
      element.replaceWith(document.createTextNode(element.textContent || ""));
      continue;
    }
    for (const attribute of Array.from(element.attributes)) {
      const isSafeLink = element.tagName === "A" && attribute.name === "href" && /^https?:\/\//i.test(attribute.value);
      if (attribute.name !== "class" && !isSafeLink) element.removeAttribute(attribute.name);
    }
  }
  for (const node of Array.from(container.querySelectorAll("article, section, div, p, li, td, span"))) {
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === Node.TEXT_NODE && child.textContent) {
        child.textContent = child.textContent.replace(/攻坚战|闪电战|升维战/g, "");
      }
    }
  }
  return container.innerHTML;
}
