(() => {
    'use strict';

    const toggle = document.getElementById('shelves-toggle');
    const panel = document.getElementById('shelves-panel');
    if (!toggle || !panel) {
        return;
    }

    function setOpen(isOpen) {
        toggle.classList.toggle('is-open', isOpen);
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        panel.classList.toggle('is-open', isOpen);
        if (isOpen) {
            panel.removeAttribute('hidden');
        } else {
            panel.setAttribute('hidden', '');
        }
    }

    toggle.addEventListener('click', () => {
        const next = toggle.getAttribute('aria-expanded') !== 'true';
        setOpen(next);
    });
})();

(() => {
    'use strict';

    const modal = document.getElementById('reader-launch-modal');
    if (!modal) return;

    const state = {
        slug: '',
        readUrl: '',
        pdfUrl: '',
        audioUrl: '',
        summary: '',
        audioDurationSec: null,
        lastData: null,
    };

    const titleNode = document.getElementById('launch-title');
    const bylineNode = document.getElementById('launch-byline');
    const metaNode = document.getElementById('launch-meta');
    const coverNode = document.getElementById('launch-cover');
    const readBtn = document.getElementById('launch-read');
    const listenBtn = document.getElementById('launch-listen');
    const startOverBtn = document.getElementById('launch-start-over');
    const downloadBtn = document.getElementById('launch-download');
    const progressText = document.getElementById('launch-progress-text');
    const pageText = document.getElementById('launch-page-text');
    const progressBar = document.getElementById('launch-progress-bar');
    const factsNode = document.getElementById('launch-facts');

    function buildReadUrl(mode, autoplay) {
        const url = new URL(state.readUrl, window.location.origin);
        if (mode === 'page') {
            url.searchParams.set('mode', 'pdf');
        } else {
            url.searchParams.set('mode', 'flip');
        }
        let href = `${url.pathname}${url.search}`;
        if (autoplay) {
            href += '#autoplay=1';
        }
        return href;
    }

    function formatDuration(seconds) {
        if (!seconds || !Number.isFinite(seconds)) return '';
        const total = Math.round(seconds);
        const hours = Math.floor(total / 3600);
        const mins = Math.floor((total % 3600) / 60);
        const secs = total % 60;
        if (hours > 0) {
            return `${hours} soat ${mins} daqiqa`;
        }
        if (mins > 0) {
            return `${mins} daqiqa`;
        }
        return `${secs} soniya`;
    }

    function getSavedPageIndex(slug) {
        try {
            const raw = localStorage.getItem(`luma-reader:${slug}:page`);
            const idx = parseInt(raw || '0', 10);
            return Number.isNaN(idx) ? 0 : Math.max(0, idx);
        } catch (_err) {
            return 0;
        }
    }

    function getFormats() {
        const formats = ['Matn'];
        if (state.pdfUrl) formats.push('PDF');
        if (state.audioUrl) formats.push('Audio');
        return formats.join(' · ');
    }

    function factRow(label, value) {
        if (value === null || value === undefined || value === '') return '';
        return `<div><dt>${label}</dt><dd>${escapeHtml(String(value))}</dd></div>`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderFacts(data) {
        const rows = [
            factRow('Muallif', data.author),
            factRow('Kategoriya', data.category),
            factRow('Nashr yili', data.year),
            factRow('Til', 'O‘zbek tili'),
            factRow('Format', getFormats()),
        ];

        if (state.audioUrl) {
            const listenValue = state.audioDurationSec
                ? formatDuration(state.audioDurationSec)
                : 'Yuklanmoqda…';
            rows.push(factRow('Tinglash vaqti', listenValue));
        }

        factsNode.innerHTML = rows.filter(Boolean).join('');

        metaNode.innerHTML = [
            data.category ? `<span class="reader-launch-modal__pill">${escapeHtml(data.category)}</span>` : '',
            data.year ? `<span class="reader-launch-modal__pill">${escapeHtml(data.year)}</span>` : '',
            state.pdfUrl ? '<span class="reader-launch-modal__pill">PDF</span>' : '',
            state.audioUrl ? '<span class="reader-launch-modal__pill">Audio</span>' : '',
        ].filter(Boolean).join('');
    }

    function loadAudioDuration(url) {
        state.audioDurationSec = null;
        if (!url) return;
        const probe = new Audio();
        probe.preload = 'metadata';
        probe.addEventListener('loadedmetadata', () => {
            if (probe.duration && Number.isFinite(probe.duration)) {
                state.audioDurationSec = probe.duration;
                if (state.lastData) renderFacts(state.lastData);
            }
        });
        probe.addEventListener('error', () => {
            state.audioDurationSec = null;
        });
        probe.src = url;
    }

    function updateProgressUI(slug) {
        const pageIndex = getSavedPageIndex(slug);
        if (pageIndex === 0) {
            progressText.textContent = 'Hali boshlanmagan';
            pageText.textContent = '';
            progressBar.style.width = '0%';
            progressBar.classList.remove('is-indeterminate');
        } else {
            progressText.textContent = 'O‘qish jarayoni saqlangan';
            pageText.textContent = `${pageIndex + 1}-sahifadan davom etasiz`;
            progressBar.style.width = '';
            progressBar.classList.add('is-indeterminate');
        }
        readBtn.href = buildReadUrl('focus', false);
    }

    function setListenState() {
        const disabled = !state.audioUrl;
        listenBtn.disabled = disabled;
        listenBtn.setAttribute('aria-disabled', String(disabled));
        modal.querySelector('[data-launch-choice="audio"]')?.toggleAttribute('disabled', disabled);
    }

    function setDownloadState() {
        if (state.pdfUrl) {
            downloadBtn.href = state.pdfUrl;
            downloadBtn.classList.remove('is-disabled');
            downloadBtn.removeAttribute('aria-disabled');
        } else {
            downloadBtn.href = '#';
            downloadBtn.classList.add('is-disabled');
            downloadBtn.setAttribute('aria-disabled', 'true');
        }
        modal.querySelector('[data-launch-choice="page"]')?.toggleAttribute('disabled', !state.pdfUrl);
    }

    function openModal(data) {
        state.slug = data.slug || '';
        state.readUrl = data.readUrl || '#';
        state.pdfUrl = data.pdfUrl || '';
        state.audioUrl = data.audioUrl || '';
        state.summary = data.summary || '';
        state.audioDurationSec = null;
        state.lastData = data;

        titleNode.textContent = data.title || 'Kitob';
        bylineNode.textContent = data.author
            ? `muallif ${data.author}${data.summary ? ` · ${data.summary}` : ''}`
            : (data.summary || '');

        if (data.coverUrl) {
            coverNode.innerHTML = `<img src="${data.coverUrl}" alt="" loading="lazy">`;
        } else {
            const initial = (data.title || 'K').trim().charAt(0).toUpperCase();
            coverNode.innerHTML = `<div class="reader-launch-modal__placeholder">${initial}</div>`;
        }

        renderFacts(data);
        updateProgressUI(state.slug);
        setListenState();
        setDownloadState();
        loadAudioDuration(state.audioUrl);

        modal.hidden = false;
        document.body.classList.add('has-launch-modal');
        readBtn.focus();
    }

    function closeModal() {
        modal.hidden = true;
        document.body.classList.remove('has-launch-modal');
    }

    function navigateRead(mode, autoplay, resetProgress) {
        if (resetProgress) {
            try {
                localStorage.removeItem(`luma-reader:${state.slug}:page`);
            } catch (_err) {
                // ignore
            }
        }
        try {
            localStorage.setItem(`luma-reader:${state.slug}:mode`, mode === 'page' ? 'pdf' : 'flip');
        } catch (_err) {
            // ignore
        }
        window.location.href = buildReadUrl(mode, autoplay);
    }

    document.addEventListener('click', (event) => {
        const launchNode = event.target.closest('[data-launch-modal="true"], .js-book-launch');
        if (launchNode) {
            event.preventDefault();
            openModal({
                slug: launchNode.dataset.slug,
                title: launchNode.dataset.title,
                author: launchNode.dataset.author,
                readUrl: launchNode.dataset.readUrl || launchNode.getAttribute('href'),
                pdfUrl: launchNode.dataset.pdfUrl,
                audioUrl: launchNode.dataset.audioUrl,
                coverUrl: launchNode.dataset.coverUrl,
                year: launchNode.dataset.year,
                category: launchNode.dataset.category,
                summary: launchNode.dataset.summary,
            });
            return;
        }

        if (event.target.closest('[data-launch-close]')) {
            closeModal();
            return;
        }

        const methodBtn = event.target.closest('[data-launch-choice]');
        if (methodBtn && !methodBtn.disabled) {
            const choice = methodBtn.dataset.launchChoice;
            if (choice === 'focus') navigateRead('focus', false, false);
            if (choice === 'page') navigateRead('page', false, false);
            if (choice === 'audio') navigateRead('focus', true, false);
        }
    });

    readBtn?.addEventListener('click', (event) => {
        event.preventDefault();
        navigateRead('focus', false, false);
    });

    listenBtn?.addEventListener('click', () => {
        if (!state.audioUrl) return;
        navigateRead('focus', true, false);
    });

    startOverBtn?.addEventListener('click', () => {
        navigateRead('focus', false, true);
    });

    downloadBtn?.addEventListener('click', (event) => {
        if (!state.pdfUrl) {
            event.preventDefault();
        }
    });

    modal.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeModal();
        }
    });
})();
