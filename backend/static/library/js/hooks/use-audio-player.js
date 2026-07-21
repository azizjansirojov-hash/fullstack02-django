export function createAudioPlayer(audioUrl) {
    const audio = new Audio(audioUrl || "");
    audio.preload = "metadata";
    const errorSubscribers = new Set();

    audio.addEventListener("error", () => {
        errorSubscribers.forEach((cb) => cb(audio.error));
    });

    return {
        audio,
        play: () => audio.play(),
        pause: () => audio.pause(),
        seek: (seconds) => {
            audio.currentTime = Math.max(0, Number(seconds) || 0);
        },
        setRate: (rate) => {
            audio.playbackRate = rate;
        },
        setVolume: (volume) => {
            audio.volume = Math.max(0, Math.min(1, volume));
        },
        toggleMute: () => {
            audio.muted = !audio.muted;
            return audio.muted;
        },
        onError: (cb) => {
            errorSubscribers.add(cb);
            return () => errorSubscribers.delete(cb);
        },
        getState: () => ({
            currentTime: audio.currentTime || 0,
            duration: audio.duration || 0,
            rate: audio.playbackRate || 1,
            muted: audio.muted,
            volume: audio.volume,
            paused: audio.paused,
            hasSource: Boolean(audioUrl),
            error: audio.error,
        }),
    };
}
