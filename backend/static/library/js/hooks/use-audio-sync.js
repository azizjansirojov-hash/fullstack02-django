import { splitSentencesFromSource } from "./split-sentences.js";

function rowsFromSentences(sentences) {
    return sentences.map((text, index) => ({ index, text, start: 0, end: 0 }));
}

export function createAudioSync(sourceNode, syncRows) {
    const rawRows = Array.isArray(syncRows) && syncRows.length
        ? syncRows
        : rowsFromSentences(splitSentencesFromSource(sourceNode));
    const rows = rawRows.map((row, index) => ({
        ...row,
        index: typeof row.index === "number" ? row.index : index,
    }));
    let activeSentenceIndex = 0;
    const subscribers = new Set();

    function notify() {
        subscribers.forEach((subscriber) => subscriber(activeSentenceIndex, rows.length));
    }

    function getIndexForTime(time) {
        if (!rows.length) return 0;
        const withRealTiming = rows.some(
            (row) => typeof row.start === "number" && typeof row.end === "number" && row.end > 0
        );
        if (!withRealTiming) {
            return Math.min(rows.length - 1, Math.floor(time / 4));
        }
        const foundIndex = rows.findIndex((row) => time >= row.start && time <= row.end);
        if (foundIndex >= 0) return foundIndex;
        let nearest = 0;
        for (let i = 0; i < rows.length; i += 1) {
            if (typeof rows[i].start === "number" && time >= rows[i].start) {
                nearest = i;
            }
        }
        return nearest;
    }

    return {
        getRows: () => rows,
        getActiveIndex: () => activeSentenceIndex,
        setFromTime: (time) => {
            const next = getIndexForTime(time);
            if (next !== activeSentenceIndex) {
                activeSentenceIndex = next;
                notify();
            }
            return next;
        },
        goToSentence: (index) => {
            activeSentenceIndex = Math.max(0, Math.min(rows.length - 1, index));
            notify();
            return rows[activeSentenceIndex];
        },
        subscribe: (cb) => {
            subscribers.add(cb);
            cb(activeSentenceIndex, rows.length);
            return () => subscribers.delete(cb);
        },
    };
}
