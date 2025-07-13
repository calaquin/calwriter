function execCmd(command) {
    document.execCommand(command, false, null);
}
function prepareSubmit() {
    document.getElementById('text').value = document.getElementById('editor').innerHTML;
}
