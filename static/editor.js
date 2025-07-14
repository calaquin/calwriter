function execCmd(command) {
    document.execCommand(command, false, null);
}
function toggleTree(el) {
    const li = el.closest('li');
    if (li) {
        li.classList.toggle('collapsed');
        const path = li.dataset.path;
        if (path) {
            const collapsed = li.classList.contains('collapsed');
            localStorage.setItem('collapsed:' + path, collapsed ? '1' : '0');
        }
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


document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('#sidebar .tree-item').forEach(li => {
        const path = li.dataset.path;
        if (path && localStorage.getItem('collapsed:' + path) === '1') {
            li.classList.add('collapsed');
        }
    });
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

    document.querySelectorAll('.sortable').forEach(ul => {
        enableDragSort(ul);
    });
});

function enableDragSort(ul) {
    let dragging;
    ul.querySelectorAll('li').forEach(li => {
        li.draggable = true;
        li.addEventListener('dragstart', () => {
            dragging = li;
        });
        li.addEventListener('dragover', e => {
            e.preventDefault();
            const rect = li.getBoundingClientRect();
            const next = (e.clientY - rect.top) > (rect.height / 2);
            ul.insertBefore(dragging, next ? li.nextSibling : li);
        });
        li.addEventListener('drop', () => {
            sendOrder(ul);
        });
    });
}

function sendOrder(ul) {
    const names = Array.from(ul.children).map(li => li.dataset.name);
    let url;
    if (ul.id === 'book_list') {
        url = '/books/reorder';
    } else {
        url = ul.dataset.reorderUrl;
    }
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: names, type: ul.dataset.type })
    });
}
