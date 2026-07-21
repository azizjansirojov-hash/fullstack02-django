(function () {
    'use strict';

    if (typeof St === 'undefined' || !St.PageFlip) return;

    var FONT_STEPS = ['0.95rem', '1.05rem', '1.18rem'];
    var LINE_STEPS = [1.65, 1.75, 1.9];
    var SETTINGS_KEY = 'luma-reader:settings';
    var PROGRESS_PREFIX = 'luma-reader:';

    var reader = document.getElementById('book-reader');
    if (!reader) return;

    // Respect saved/query reading mode before St.PageFlip initialises.
    try {
        var slugEarly = reader.dataset.slug;
        var params = new URLSearchParams(window.location.search);
        var queryMode = params.get('mode');
        var savedMode = slugEarly ? localStorage.getItem('luma-reader:' + slugEarly + ':mode') : null;
        if ((queryMode || savedMode) === 'pdf') {
            reader.setAttribute('data-skip-flip', 'true');
        }
    } catch (e) { /* ignore */ }

    // Skip initialisation when PDF mode is active.
    if (reader.getAttribute('data-skip-flip') === 'true') return;

    var source = document.getElementById('book-source');
    var mount = document.getElementById('book-mount');
    var loading = document.getElementById('book-loading');
    var counter = document.getElementById('book-counter');
    var btnLineHeight = document.getElementById('btn-line-height');
    var btnFontSize = document.getElementById('btn-font-size');

    var slug = reader.dataset.slug;
    var pageFlip = null;
    var resizeTimer = null;
    var navZones = [];

    var settings = loadSettings();
    applySettingsToRoot();

    function loadSettings() {
        try {
            var stored = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
            return {
                fontIndex: clampIndex(stored.fontIndex, FONT_STEPS.length, 1),
                lineIndex: clampIndex(stored.lineIndex, LINE_STEPS.length, 1),
            };
        } catch (e) {
            return { fontIndex: 1, lineIndex: 1 };
        }
    }

    function saveSettings() {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    }

    function clampIndex(value, length, fallback) {
        var idx = typeof value === 'number' ? value : fallback;
        return Math.max(0, Math.min(length - 1, idx));
    }

    function applySettingsToRoot() {
        document.documentElement.style.setProperty('--reader-font-size', FONT_STEPS[settings.fontIndex]);
        document.documentElement.style.setProperty('--reader-line-height', String(LINE_STEPS[settings.lineIndex]));
    }

    function prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function getFlipTime() {
        return prefersReducedMotion() ? 0 : 680;
    }

    function getPageDimensions() {
        var maxSpreadWidth = Math.min(window.innerWidth * 0.92, 1000);
        var maxHeight = window.innerHeight - 190;
        var isPortrait = window.innerWidth < 720;

        if (isPortrait) {
            var singleWidth = Math.min(maxSpreadWidth, 420);
            var singleHeight = Math.min(maxHeight, Math.round(singleWidth * 1.38));
            return { width: singleWidth, height: singleHeight, isPortrait: true };
        }

        var pageWidth = Math.floor(maxSpreadWidth / 2);
        var pageHeight = Math.min(maxHeight, Math.round(pageWidth * 1.38));
        return { width: pageWidth, height: pageHeight, isPortrait: false };
    }

    function getParagraphs() {
        var nodes = source.querySelectorAll('p');
        if (nodes.length) {
            return Array.prototype.map.call(nodes, function (p) {
                return p.innerHTML.trim();
            }).filter(Boolean);
        }
        var text = (source.textContent || '').trim();
        if (!text) return [];
        return text.split(/\n\s*\n/).map(function (chunk) {
            return chunk.trim();
        }).filter(Boolean);
    }

    function createMeasureBox(width, height) {
        var box = document.createElement('div');
        box.className = 'book-reader__measure';
        box.style.cssText =
            'position:fixed;left:-9999px;top:0;width:' + width + 'px;height:' + height +
            'px;visibility:hidden;pointer-events:none;overflow:hidden;';
        box.innerHTML = '<div class="page-content"></div>';
        document.body.appendChild(box);
        return box;
    }

    function pageFits(measureContent, html) {
        measureContent.innerHTML = html;
        return measureContent.scrollHeight <= measureContent.clientHeight + 1;
    }

    function splitParagraphByWords(html, measureContent) {
        var temp = document.createElement('div');
        temp.innerHTML = html;
        var text = temp.textContent || '';
        var words = text.split(/\s+/).filter(Boolean);
        if (!words.length) return [html];

        var chunks = [];
        var current = [];

        words.forEach(function (word) {
            current.push(word);
            var trial = '<p>' + escapeHtml(current.join(' ')) + '</p>';
            if (!pageFits(measureContent, trial) && current.length > 1) {
                current.pop();
                chunks.push('<p>' + escapeHtml(current.join(' ')) + '</p>');
                current = [word];
            }
        });

        if (current.length) {
            chunks.push('<p>' + escapeHtml(current.join(' ')) + '</p>');
        }
        return chunks;
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function paginateContent(paragraphs, width, height) {
        var measureBox = createMeasureBox(width, height);
        var measureContent = measureBox.querySelector('.page-content');
        var pages = [];
        var currentHtml = '';

        function flushPage() {
            if (currentHtml.trim()) {
                pages.push(currentHtml);
                currentHtml = '';
            }
        }

        paragraphs.forEach(function (para) {
            var paraHtml = para.indexOf('<') >= 0 ? '<p>' + para + '</p>' : '<p>' + escapeHtml(para) + '</p>';

            if (!currentHtml) {
                if (pageFits(measureContent, paraHtml)) {
                    currentHtml = paraHtml;
                } else {
                    splitParagraphByWords(para, measureContent).forEach(function (chunk) {
                        if (pageFits(measureContent, currentHtml + chunk)) {
                            currentHtml += chunk;
                        } else {
                            flushPage();
                            currentHtml = chunk;
                        }
                    });
                }
                return;
            }

            var trial = currentHtml + paraHtml;
            if (pageFits(measureContent, trial)) {
                currentHtml = trial;
            } else {
                flushPage();
                if (pageFits(measureContent, paraHtml)) {
                    currentHtml = paraHtml;
                } else {
                    splitParagraphByWords(para, measureContent).forEach(function (chunk) {
                        if (pageFits(measureContent, currentHtml + chunk)) {
                            currentHtml += chunk;
                        } else {
                            flushPage();
                            currentHtml = chunk;
                        }
                    });
                }
            }
        });

        flushPage();
        document.body.removeChild(measureBox);

        if (!pages.length) {
            pages.push('<p></p>');
        }
        return pages;
    }

    function buildPageElements(pages) {
        var globalSentenceIndex = 0;
        return pages.map(function (html) {
            var page = document.createElement('div');
            page.className = 'page';
            page.innerHTML = '<div class="page-content">' + html + '</div>';
            if (reader.dataset.sentenceWrap === 'true') {
                globalSentenceIndex = wrapSentences(page, globalSentenceIndex);
            }
            return page;
        });
    }

    function wrapSentences(pageElement, startIndex) {
        var splitSentences = (window.LumaSplitSentences && window.LumaSplitSentences.splitSentences)
            || function (text) {
                var trimmed = (text || '').trim();
                if (!trimmed) return [];
                var chunks = trimmed.match(/[^.!?]+[.!?]?/g);
                if (!chunks) return [];
                return chunks.map(function (chunk) { return chunk.trim(); }).filter(Boolean);
            };
        var paragraphs = pageElement.querySelectorAll('.page-content p');
        var sentenceIndex = startIndex;
        Array.prototype.forEach.call(paragraphs, function (paragraph) {
            var chunks = splitSentences(paragraph.textContent || '');
            if (!chunks.length) return;
            paragraph.innerHTML = chunks.map(function (chunk) {
                var text = escapeHtml(chunk);
                if (!text) return '';
                var html = '<span class="reader-sentence" data-sentence-index="' + sentenceIndex + '">' + text + '</span>';
                sentenceIndex += 1;
                return html;
            }).join(' ');
        });
        return sentenceIndex;
    }

    function getSavedPageIndex(totalPages) {
        try {
            var saved = parseInt(localStorage.getItem(PROGRESS_PREFIX + slug + ':page'), 10);
            if (isNaN(saved)) return 0;
            return Math.max(0, Math.min(totalPages - 1, saved));
        } catch (e) {
            return 0;
        }
    }

    function saveProgress(index) {
        try {
            localStorage.setItem(PROGRESS_PREFIX + slug + ':page', String(index));
        } catch (e) { /* ignore */ }
    }

    function updateCounter() {
        if (!pageFlip) return;
        var current = pageFlip.getCurrentPageIndex() + 1;
        var total = pageFlip.getPageCount();
        counter.textContent = current + ' / ' + total + ' sahifa';
    }

    function destroyFlip() {
        // St.PageFlip.destroy() removes the mount node from the DOM (block.remove()).
        // Capture siblings first so we can re-insert a fresh #book-mount afterward.
        var stage = mount.parentNode;
        var anchor = mount.nextSibling;
        if (pageFlip) {
            try {
                pageFlip.destroy();
            } catch (e) { /* ignore */ }
            pageFlip = null;
        }
        if (!mount.isConnected) {
            var fresh = document.createElement('div');
            fresh.id = 'book-mount';
            fresh.className = 'book-reader__mount';
            if (stage) {
                stage.insertBefore(fresh, anchor);
            }
            mount = fresh;
        } else {
            mount.innerHTML = '';
        }
        navZones.forEach(function (zone) {
            if (zone.parentNode) zone.parentNode.removeChild(zone);
        });
        navZones = [];
    }

    function addNavZones() {
        if (!mount) return;

        var prev = document.createElement('button');
        prev.type = 'button';
        prev.className = 'book-reader__nav-zone book-reader__nav-zone--prev';
        prev.setAttribute('aria-label', 'Previous page');
        prev.addEventListener('click', function () {
            if (pageFlip) pageFlip.flipPrev();
        });

        var next = document.createElement('button');
        next.type = 'button';
        next.className = 'book-reader__nav-zone book-reader__nav-zone--next';
        next.setAttribute('aria-label', 'Next page');
        next.addEventListener('click', function () {
            if (pageFlip) pageFlip.flipNext();
        });

        mount.appendChild(prev);
        mount.appendChild(next);
        navZones = [prev, next];
    }

    function scheduleRelayout(delay) {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(rebuildReader, typeof delay === 'number' ? delay : 250);
    }

    function updateBridge() {
        window.LumaFlipReaderBridge = {
            flipPrev: function () {
                if (pageFlip) pageFlip.flipPrev();
            },
            flipNext: function () {
                if (pageFlip) pageFlip.flipNext();
            },
            turnToPage: function (index) {
                if (pageFlip) pageFlip.turnToPage(index);
            },
            relayout: function () {
                scheduleRelayout(0);
            },
        };
    }

    function initReader(preserveIndex) {
        var dims = getPageDimensions();
        var paragraphs = getParagraphs();
        var pagesHtml = paginateContent(paragraphs, dims.width, dims.height);
        var pageElements = buildPageElements(pagesHtml);

        var targetIndex = typeof preserveIndex === 'number'
            ? Math.max(0, Math.min(pagesHtml.length - 1, preserveIndex))
            : getSavedPageIndex(pagesHtml.length);

        destroyFlip();

        pageElements.forEach(function (el) {
            mount.appendChild(el);
        });

        pageFlip = new St.PageFlip(mount, {
            width: dims.width,
            height: dims.height,
            size: 'stretch',
            minWidth: 280,
            maxWidth: 520,
            minHeight: 380,
            maxHeight: 900,
            maxShadowOpacity: 0.55,
            showCover: false,
            mobileScrollSupport: false,
            usePortrait: dims.isPortrait,
            drawShadow: true,
            flippingTime: getFlipTime(),
            useMouseEvents: true,
        });

        pageFlip.loadFromHTML(pageElements);

        pageFlip.on('flip', function (e) {
            saveProgress(e.data);
            updateCounter();
            window.dispatchEvent(new CustomEvent('luma:pagechange', {
                detail: { current: e.data + 1, total: pageFlip.getPageCount() }
            }));
        });

        pageFlip.on('changeState', function (e) {
            if (e.data === 'read') updateCounter();
        });

        if (targetIndex > 0) {
            pageFlip.turnToPage(targetIndex);
        }

        addNavZones();
        updateCounter();
        updateBridge();
        loading.classList.add('is-hidden');
        window.dispatchEvent(new CustomEvent('luma:flipready'));
    }

    function rebuildReader() {
        var currentIndex = pageFlip ? pageFlip.getCurrentPageIndex() : 0;
        loading.classList.remove('is-hidden');
        requestAnimationFrame(function () {
            initReader(currentIndex);
        });
    }

    /* Toolbar handlers (font/line live in ReaderToolbar; prev/next/fullscreen/close via orchestrator) */
    if (btnFontSize) {
        btnFontSize.addEventListener('click', function () {
            settings.fontIndex = (settings.fontIndex + 1) % FONT_STEPS.length;
            saveSettings();
            applySettingsToRoot();
            rebuildReader();
        });
    }

    if (btnLineHeight) {
        btnLineHeight.addEventListener('click', function () {
            settings.lineIndex = (settings.lineIndex + 1) % LINE_STEPS.length;
            saveSettings();
            applySettingsToRoot();
            rebuildReader();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (!pageFlip) return;
        if (reader.getAttribute('data-reader-mode') !== 'flip') return;

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            pageFlip.flipNext();
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            pageFlip.flipPrev();
        }
    });

    window.addEventListener('resize', function () {
        scheduleRelayout(250);
    });

    /* Init on DOM ready (scripts are defer-loaded) */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initReader();
        });
    } else {
        initReader();
    }
})();
