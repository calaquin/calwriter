function execCmd(command) {
    document.execCommand(command, false, null);
}
function prepareChapter() {
    document.getElementById('chapter_text').value = document.getElementById('chapter_editor').innerHTML;
}

function updateWordCount() {
    const editor = document.getElementById('chapter_editor');
    if (!editor) return;
    const text = editor.innerText || '';
    const words = text.trim().split(/\s+/).filter(Boolean);
    const counter = document.getElementById('word_count');
    if (counter) counter.textContent = words.length;
}

document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('chapter_editor');
    if (editor) {
        editor.addEventListener('input', updateWordCount);
        updateWordCount();
    }
    const notes = document.getElementById('notes_editor');
    if (notes) {
        let timeout;
        notes.addEventListener('input', () => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                fetch(notes.dataset.saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: new URLSearchParams({notes: notes.value})
                });
            }, 500);
        });
    }
});
