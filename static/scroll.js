var prevScrollpos = window.pageYOffset;
window.addEventListener('scroll', navFunction);

function navFunction() {
  var currentScrollPos = window.pageYOffset;
  if (prevScrollpos > currentScrollPos) {
    document.getElementsByTagName('nav')[0].style.top = "0";
  } else {
    document.getElementsByTagName('nav')[0].style.top = "-80px";
  }
  prevScrollpos = currentScrollPos;
}