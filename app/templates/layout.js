// Same fit logic for browser preview and PDF. Never truncate course data.
(() => {
window.fitAttendanceBook = () => {
  const results = [];
  for (const [index, paper] of [...document.querySelectorAll('.page')].entries()) {
    paper.classList.remove('layout-overflow');
    const content = paper.querySelector('.page-content');
    content.style.zoom = '1';
    content.style.marginLeft = '0';
    const style = getComputedStyle(paper);
    // offset dimensions are unzoomed, unlike getBoundingClientRect in preview.
    const width = paper.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    const height = paper.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    const cells = paper.querySelectorAll('.schedule td');
    cells.forEach(cell => {cell.style.fontSize = ''; cell.style.lineHeight = '';});
    let naturalHeight = content.scrollHeight;
    if (naturalHeight > height + 2 && cells.length) {
      // A denser timetable can use tighter course typography before page scaling.
      for (const size of [8.5, 8, 7.5]) {
        cells.forEach(cell => {cell.style.fontSize = size + 'pt'; cell.style.lineHeight = '1.15';});
        naturalHeight = content.scrollHeight;
        if (naturalHeight <= height + 2) break;
      }
    }
    const scale = Math.min(1, width / Math.max(width, content.scrollWidth), height / Math.max(height, naturalHeight));
    const overflow = scale < 0.8;
    if (!overflow) {
      // Zoom affects pagination layout; transforms affect only paint and can
      // fragment a table onto the next print page before scaling.
      content.style.zoom = String(scale);
      content.style.marginLeft = `${width * (1-scale)/(2*scale)}px`;
    }
    else paper.classList.add('layout-overflow');
    paper.dataset.layoutScale = String(scale);
    results.push({page:index+1, title:paper.querySelector('h1,h2')?.textContent || '', overflow, scale});
  }
  return results;
};
const resizePreview = () => {
  document.documentElement.style.setProperty('--preview-scale', String(Math.min(1, window.innerWidth * 0.8 / (297*96/25.4))));
};
resizePreview();
if (window.attendanceResizeHandler) window.removeEventListener('resize', window.attendanceResizeHandler);
window.attendanceResizeHandler = resizePreview;
window.addEventListener('resize', resizePreview);
window.attendanceLayoutReady = document.fonts.ready.then(() => {
  const results = window.fitAttendanceBook();
  const warning = document.getElementById('layout-warning');
  const bad = results.filter(result => result.overflow);
  if (warning) warning.textContent = bad.length ? 'Pages need layout adjustment / 以下页面需调整: ' + bad.map(result => result.page + ' · ' + result.title).join('; ') : '';
  return results;
});
document.getElementById('print-book')?.addEventListener('click', async () => {
  const results = await window.attendanceLayoutReady;
  if (results.some(result => result.overflow)) {
    alert('Content does not fit a print page. Adjust the reported page before printing. / 内容超出打印页，请先调整提示的页面。');
    return;
  }
  window.print();
});
})();
