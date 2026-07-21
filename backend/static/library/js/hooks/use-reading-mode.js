const MODE_REAL = "flip";
const MODE_PDF = "pdf";

function normalizeMode(mode) {
    return mode === MODE_PDF ? MODE_PDF : MODE_REAL;
}

export function getReadingMode(slug, search = window.location.search) {
    const params = new URLSearchParams(search);
    const queryMode = params.get("mode");
    if (queryMode) {
        return normalizeMode(queryMode);
    }

    try {
        const saved = localStorage.getItem(`luma-reader:${slug}:mode`);
        return normalizeMode(saved);
    } catch (_error) {
        return MODE_REAL;
    }
}

export function setReadingMode(slug, mode) {
    const value = normalizeMode(mode);
    try {
        localStorage.setItem(`luma-reader:${slug}:mode`, value);
    } catch (_error) {
        // ignore storage errors
    }
    return value;
}

export function withMode(url, mode) {
    const next = new URL(url, window.location.origin);
    next.searchParams.set("mode", normalizeMode(mode));
    return `${next.pathname}${next.search}`;
}

