function execCmd(command) {
    document.execCommand(command, false, null);
}
function toggleTree(el) {
    const li = el.closest('li');
    if (li) {
        li.classList.toggle('collapsed');
    }
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

function copyChapter() {
    const editor = document.getElementById('chapter_editor');
    if (editor) {
        navigator.clipboard.writeText(editor.innerText).then(() => {
            alert('Chapter copied to clipboard');
        }).catch(() => {
            alert('Failed to copy chapter');
        });
    }
}

function copyNotes() {
    const notes = document.getElementById('notes_editor');
    if (notes) {
        navigator.clipboard.writeText(notes.value).then(() => {
            alert('Notes copied to clipboard');
        }).catch(() => {
            alert('Failed to copy notes');
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('chapter_editor');
    if (editor) {
        let timeout;
        editor.addEventListener('input', () => {
            updateWordCount();
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                fetch(editor.dataset.saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: new URLSearchParams({text: editor.innerHTML})
                });
            }, 1000);
        });
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
