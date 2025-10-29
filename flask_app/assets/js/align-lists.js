(function(){
  let resizeTimer;

  function equalizeListHeights() {
    const containerRows = document.querySelectorAll('.section .row.g-5');
    containerRows.forEach(row => {
      // 找到卡片内的两个 list-group（左右列）
      const lists = row.querySelectorAll('.bg-white .list-group.list-group-flush');
      if (lists.length < 2) return;

      const left = lists[0];
      const right = lists[1];

      // 重置高度，避免重复累积
      Array.from(left.children).forEach(li => li.style.height = '');
      Array.from(right.children).forEach(li => li.style.height = '');

      const count = Math.min(left.children.length, right.children.length);
      for (let i = 0; i < count; i++) {
        const l = left.children[i];
        const r = right.children[i];
        if (!l || !r) continue;
        const maxH = Math.max(l.offsetHeight, r.offsetHeight);
        l.style.height = r.style.height = maxH + 'px';
      }
    });
  }

  window.addEventListener('load', equalizeListHeights, { passive: true });
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(equalizeListHeights, 120);
  }, { passive: true });
})();
