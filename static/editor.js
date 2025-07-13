function execCmd(command) {
    document.execCommand(command, false, null);
}
function prepareSubmit() {
    document.getElementById('text').value = document.getElementById('editor').innerHTML;
}

function prepareChapter() {
    document.getElementById('chapter_text').value = document.getElementById('chapter_editor').innerHTML;
}
