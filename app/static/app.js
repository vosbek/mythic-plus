// Mythic+ Tracker - minimal JS (HTMX handles most interactivity)

// Auto-dismiss flash messages after 3 seconds
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.flash-success').forEach(function(el) {
        setTimeout(function() { el.style.display = 'none'; }, 3000);
    });
});

// Format seconds as MM:SS
function formatTime(seconds) {
    if (!seconds) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
}
