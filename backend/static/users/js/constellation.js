(() => {
    'use strict';

    const canvas = document.getElementById('constellation');
    if (!canvas || typeof canvas.getContext !== 'function') {
        return;
    }

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = canvas.getContext('2d');

    const COLORS = {
        node: 'rgba(180, 200, 220, 0.7)',
        line: 'rgba(120, 160, 200,',
        accent: 'rgba(120, 220, 150, 0.9)',
    };

    let width = 0;
    let height = 0;
    let dpr = 1;
    let points = [];
    let animationId = null;
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
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        createPoints();
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);
        const linkDistance = width < 640 ? 110 : 150;

        for (let i = 0; i < points.length; i += 1) {
            const p = points[i];

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
                const dx = p.x - q.x;
                const dy = p.y - q.y;
                const dist = Math.hypot(dx, dy);
                if (dist < linkDistance) {
                    const alpha = (1 - dist / linkDistance) * 0.5;
                    ctx.strokeStyle = `${COLORS.line} ${alpha})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(q.x, q.y);
                    ctx.stroke();
                }
            }

            ctx.fillStyle = p.accent ? COLORS.accent : COLORS.node;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fill();
        }

        animationId = window.requestAnimationFrame(draw);
    }

    function renderStatic() {
        // Single frame for reduced-motion users: points only, no links.
        ctx.clearRect(0, 0, width, height);
        points.forEach((p) => {
            ctx.fillStyle = p.accent ? COLORS.accent : COLORS.node;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fill();
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

    let resizeTimer = null;
    window.addEventListener('resize', () => {
        window.clearTimeout(resizeTimer);
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
