/** Shared sentence splitting used by flip reader, PDF view, and audio sync. */

export function splitSentences(text) {
    const trimmed = (text || "").trim();
    if (!trimmed) return [];
    const chunks = trimmed.match(/[^.!?]+[.!?]?/g);
    if (!chunks) return [];
    return chunks.map((chunk) => chunk.trim()).filter(Boolean);
}

export function splitSentencesFromSource(sourceNode) {
    if (!sourceNode) return [];
    const paragraphs = sourceNode.querySelectorAll("p");
    if (paragraphs.length) {
        const sentences = [];
        paragraphs.forEach((paragraph) => {
            sentences.push(...splitSentences(paragraph.textContent || ""));
        });
        return sentences;
    }
    return splitSentences(sourceNode.textContent || "");
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}

/** Build sentence span HTML; mutates `counter` for global index assignment. */
export function buildSentenceSpans(text, counter) {
    return splitSentences(text)
        .map((chunk) => {
            const idx = counter.value;
            counter.value += 1;
            return `<span class="reader-sentence" data-sentence-index="${idx}">${escapeHtml(chunk)}</span>`;
        })
        .join(" ");
}
