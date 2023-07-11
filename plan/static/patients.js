// Open object.
function click_function() {
    document.getElementById("drop_list").classList.toggle("show");
}
// Close object.
window.onclick = function(event) {
    if (!event.target.matches('.p_list')) {
        var dropdowns = document.getElementsByClassName("dropdown_content");
        var i;
    for (i = 0; i < dropdowns.length; i++) {
        var openDropdown = dropdowns[i];
        if (openDropdown.classList.contains('show')) {
            openDropdown.classList.remove('show');
        }
    }
    }
}