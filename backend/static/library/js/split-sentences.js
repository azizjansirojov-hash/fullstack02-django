/** Non-module shim so legacy reader.js can share sentence splitting. */
(function (global) {
    function splitSentences(text) {
        var trimmed = (text || "").trim();
        if (!trimmed) return [];
        var chunks = trimmed.match(/[^.!?]+[.!?]?/g);
        if (!chunks) return [];
        return chunks.map(function (chunk) { return chunk.trim(); }).filter(Boolean);
    }

    global.LumaSplitSentences = { splitSentences: splitSentences };
}(typeof window !== "undefined" ? window : globalThis));
