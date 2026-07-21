import { ICONS } from "./reader-toolbar.js";

export function mountAudioPlaybackBar(mount, api) {
    if (!mount) return null;
    mount.innerHTML = `
        <div class="audio-playback" hidden>
            <div class="audio-playback__inner">
                <button type="button" class="audio-playback__toggle" data-audio-action="toggle" aria-label="Play or pause">
                    ${ICONS.play}
                </button>
                <div class="audio-playback__meta">
                    <span class="audio-playback__label">Tinglash</span>
                    <span id="audio-sentence-count" class="audio-playback__count">0 / 0</span>
                </div>
                <input type="range" class="audio-playback__seek" min="0" max="100" value="0" data-audio-action="seek" aria-label="Seek playback">
                <div class="audio-playback__controls">
                    <button type="button" class="audio-playback__btn" data-audio-action="prev" aria-label="Previous sentence">Prev</button>
                    <button type="button" class="audio-playback__btn" data-audio-action="speed" aria-label="Cycle speed">1x</button>
                    <button type="button" class="audio-playback__btn" data-audio-action="next" aria-label="Next sentence">Next</button>
                    <button type="button" class="audio-playback__btn" data-audio-action="mute" aria-label="Mute or unmute">Mute</button>
                    <button type="button" class="audio-playback__btn audio-playback__btn--close" data-audio-action="close" aria-label="Close audio player">Close</button>
                </div>
                <p class="audio-playback__error" id="audio-playback-error" hidden>Audio fayl mavjud emas yoki yuklanmadi.</p>
            </div>
        </div>
    `;
    const shell = mount.querySelector(".audio-playback");
    if (!api.hasAudio) return null;

    const toggleBtn = mount.querySelector("[data-audio-action='toggle']");
    const errorNode = mount.querySelector("#audio-playback-error");
    const speedSteps = [1, 1.25, 1.5, 2];
    let speedIndex = 0;

    function setToggleIcon(paused) {
        if (!toggleBtn) return;
        toggleBtn.innerHTML = paused ? ICONS.play : ICONS.pause;
        toggleBtn.setAttribute("aria-label", paused ? "Play" : "Pause");
    }

    function showError(message) {
        if (errorNode) {
            errorNode.textContent = message || "Audio fayl mavjud emas yoki yuklanmadi.";
            errorNode.hidden = false;
        }
        setToggleIcon(true);
    }

    setToggleIcon(true);

    mount.addEventListener("click", (event) => {
        const button = event.target.closest("[data-audio-action]");
        if (!button) return;
        const action = button.dataset.audioAction;
        if (action === "toggle") {
            api.toggle();
            setToggleIcon(api.isPaused());
        } else if (action === "prev") {
            api.prevSentence();
        } else if (action === "next") {
            api.nextSentence();
        } else if (action === "speed") {
            speedIndex = (speedIndex + 1) % speedSteps.length;
            api.setSpeed(speedSteps[speedIndex]);
            button.textContent = `${speedSteps[speedIndex]}x`;
        } else if (action === "mute") {
            const muted = api.toggleMute();
            button.textContent = muted ? "Unmute" : "Mute";
        } else if (action === "close") {
            api.pause();
            shell.hidden = true;
            setToggleIcon(true);
        }
    });

    const seek = mount.querySelector("[data-audio-action='seek']");
    seek?.addEventListener("input", () => {
        api.seekRatio(Number(seek.value) / 100);
    });

    return {
        setSentence(index, total) {
            const node = mount.querySelector("#audio-sentence-count");
            if (node) node.textContent = `${index + 1} / ${total}`;
        },
        setSeek(percent) {
            if (seek) seek.value = String(Math.round(percent));
        },
        setToggleIcon,
        showError,
    };
}
