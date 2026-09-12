window.addEventListener('load', function () {
    const loader = document.getElementById('loader');
    if (loader) {
        setTimeout(function () {
            loader.classList.add('hidden');
        }, 400);
    }
});

(function setMinDates() {
    const today = new Date().toISOString().split('T')[0];
    document.querySelectorAll("input[type='date']").forEach(function (el) {
        if (!el.min) {
            el.min = today;
        }
    });
})();
