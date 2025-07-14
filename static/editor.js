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
    const undoBtn = document.getElementById('undo_btn');
    if (undoBtn && editor) {
        undoBtn.addEventListener('click', () => execCmd('undo'));
    }
    const redoBtn = document.getElementById('redo_btn');
    if (redoBtn && editor) {
        redoBtn.addEventListener('click', () => execCmd('redo'));
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

    const sidebar = document.getElementById('notes_sidebar');
    const resizer = document.getElementById('notes_resizer');
    if (sidebar && resizer) {
        const storedWidth = localStorage.getItem('notesWidth');
        if (storedWidth) sidebar.style.width = storedWidth;
        let startX, startWidth;
        const saveWidth = () => {
            localStorage.setItem('notesWidth', sidebar.style.width);
        };
        const onMove = e => {
            const dx = e.clientX - startX;
            sidebar.style.width = (startWidth - dx) + 'px';
        };
        const stopDrag = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', stopDrag);
            saveWidth();
        };
        resizer.addEventListener('mousedown', e => {
            startX = e.clientX;
            startWidth = sidebar.offsetWidth;
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', stopDrag);
        });
    }

    setupTabs();

    document.querySelectorAll('.sortable').forEach(ul => {
        enableDragSort(ul);
    });
});

function setupTabs() {
    const tabsEl = document.getElementById('chapter_tabs');
    if (!tabsEl) return;
    const currentFolder = tabsEl.dataset.folder;
    const currentChapter = tabsEl.dataset.chapter;
    let tabs = JSON.parse(localStorage.getItem('open_chapters') || '[]');
    const existing = tabs.find(t => t.folder === currentFolder && t.chapter === currentChapter);
    if (!existing) {
        tabs.push({folder: currentFolder, chapter: currentChapter});
        localStorage.setItem('open_chapters', JSON.stringify(tabs));
    }
    renderTabs(tabsEl, tabs, currentFolder, currentChapter);
}

function renderTabs(container, tabs, currentFolder, currentChapter) {
    container.innerHTML = '';
    tabs.forEach((t, i) => {
        const tab = document.createElement('span');
        tab.className = 'chapter-tab' + (t.folder === currentFolder && t.chapter === currentChapter ? ' active' : '');
        tab.dataset.folder = t.folder;
        tab.dataset.chapter = t.chapter;
        const link = document.createElement('a');
        link.textContent = t.chapter;
        link.href = `/folder/${t.folder}/chapter/${t.chapter}`;
        tab.appendChild(link);
        const close = document.createElement('button');
        close.textContent = '×';
        close.className = 'close-tab';
        close.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            tabs.splice(i,1);
            localStorage.setItem('open_chapters', JSON.stringify(tabs));
            if (t.folder === currentFolder && t.chapter === currentChapter) {
                if (tabs.length) {
                    const next = tabs[tabs.length-1];
                    window.location.href = `/folder/${next.folder}/chapter/${next.chapter}`;
                } else {
                    window.location.href = `/folder/${t.folder}`;
                }
            } else {
                renderTabs(container, tabs, currentFolder, currentChapter);
            }
        });
        tab.appendChild(close);
        container.appendChild(tab);
    });
    enableTabDrag(container, tabs, currentFolder, currentChapter);
}

function enableTabDrag(container, tabs, currentFolder, currentChapter) {
    let dragging;
    Array.from(container.children).forEach((tab, idx) => {
        tab.draggable = true;
        tab.addEventListener('dragstart', () => {
            dragging = tab;
        });
        tab.addEventListener('dragover', e => {
            e.preventDefault();
            const rect = tab.getBoundingClientRect();
            const next = (e.clientX - rect.left) > (rect.width / 2);
            container.insertBefore(dragging, next ? tab.nextSibling : tab);
        });
        tab.addEventListener('drop', () => {
            const newOrder = Array.from(container.children).map(el => ({
                folder: el.dataset.folder,
                chapter: el.dataset.chapter
            }));
            tabs.splice(0, tabs.length, ...newOrder);
            localStorage.setItem('open_chapters', JSON.stringify(tabs));
            renderTabs(container, tabs, currentFolder, currentChapter);
        });
    });
}

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
