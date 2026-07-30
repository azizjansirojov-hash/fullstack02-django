(() => {
    'use strict';

    type Point = { x: number; y: number; vx: number; vy: number; r: number; accent: boolean };

    const canvas = document.getElementById('constellation') as HTMLCanvasElement | null;
    if (!canvas || typeof canvas.getContext !== 'function') {
        return;
    }

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        return;
    }
    const activeCanvas = canvas;
    const activeCtx = ctx;

    const COLORS = {
        node: 'rgba(180, 200, 220, 0.7)',
        line: 'rgba(120, 160, 200,',
        accent: 'rgba(120, 220, 150, 0.9)',
    };

    let width = 0;
    let height = 0;
    let dpr = 1;
    let points: Point[] = [];
    let animationId: number | null = null;
    const pointer = { x: -9999, y: -9999 };

    function pointCount() {
        // Density scales with viewport, capped for performance.
        return Math.min(110, Math.max(36, Math.round((width * height) / 16000)));
    }

    function createPoints() {
        const count = pointCount();
        points = Array.from({ length: count }, () => ({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.28,
            vy: (Math.random() - 0.5) * 0.28,
            r: Math.random() * 1.4 + 0.6,
            accent: Math.random() < 0.12,
        }));
    }

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = window.innerWidth;
        height = window.innerHeight;
        activeCanvas.width = Math.floor(width * dpr);
        activeCanvas.height = Math.floor(height * dpr);
        activeCanvas.style.width = `${width}px`;
        activeCanvas.style.height = `${height}px`;
        activeCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
        createPoints();
    }

    function draw() {
        activeCtx.clearRect(0, 0, width, height);
        const linkDistance = width < 640 ? 110 : 150;

        for (let i = 0; i < points.length; i += 1) {
            const p = points[i];
            if (!p) continue;

            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0 || p.x > width) p.vx *= -1;
            if (p.y < 0 || p.y > height) p.vy *= -1;

            // Gentle pointer attraction for subtle interactivity.
            const pdx = pointer.x - p.x;
            const pdy = pointer.y - p.y;
            const pDist = Math.hypot(pdx, pdy);
            if (pDist < 160 && pDist > 0.5) {
                p.x += (pdx / pDist) * 0.25;
                p.y += (pdy / pDist) * 0.25;
            }

            for (let j = i + 1; j < points.length; j += 1) {
                const q = points[j];
                if (!q) continue;
                const dx = p.x - q.x;
                const dy = p.y - q.y;
                const dist = Math.hypot(dx, dy);
                if (dist < linkDistance) {
                    const alpha = (1 - dist / linkDistance) * 0.5;
                    activeCtx.strokeStyle = `${COLORS.line} ${alpha})`;
                    activeCtx.lineWidth = 1;
                    activeCtx.beginPath();
                    activeCtx.moveTo(p.x, p.y);
                    activeCtx.lineTo(q.x, q.y);
                    activeCtx.stroke();
                }
            }

            activeCtx.fillStyle = p.accent ? COLORS.accent : COLORS.node;
            activeCtx.beginPath();
            activeCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            activeCtx.fill();
        }

        animationId = window.requestAnimationFrame(draw);
    }

    function renderStatic() {
        // Single frame for reduced-motion users: points only, no links.
        activeCtx.clearRect(0, 0, width, height);
        points.forEach((p) => {
            activeCtx.fillStyle = p.accent ? COLORS.accent : COLORS.node;
            activeCtx.beginPath();
            activeCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            activeCtx.fill();
        });
    }

    function start() {
        if (reduceMotion) {
            renderStatic();
            return;
        }
        if (animationId === null) {
            draw();
        }
    }

    function stop() {
        if (animationId !== null) {
            window.cancelAnimationFrame(animationId);
            animationId = null;
        }
    }

    let resizeTimer: number | null = null;
    window.addEventListener('resize', () => {
        if (resizeTimer !== null) window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(() => {
            resize();
            if (reduceMotion) {
                renderStatic();
            }
        }, 150);
    });

    window.addEventListener('pointermove', (event) => {
        pointer.x = event.clientX;
        pointer.y = event.clientY;
    });

    window.addEventListener('pointerleave', () => {
        pointer.x = -9999;
        pointer.y = -9999;
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stop();
        } else {
            start();
        }
    });

    resize();
    start();
})();

