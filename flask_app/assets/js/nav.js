// Global navigation indicator + page transition
(function () {
  const NAV_DURATION = 300; // ms
  const PAGE_DURATION = 220; // ms

  const navContainer = document.querySelector('.js-nav');
  const indicator = navContainer ? navContainer.querySelector('.nav-indicator') : null;
  const links = navContainer ? Array.from(navContainer.querySelectorAll('a[data-nav]')) : [];
  const page = document.getElementById('page-content');

    function setIndicatorTo(el, animate = true) {
        if (!indicator || !el) return;
        const label = el.querySelector('.nav-label') || el;
        
        // 获取导航容器和文字标签的精确屏幕位置
        const navRect = navContainer.getBoundingClientRect();
        const labelRect = label.getBoundingClientRect();

        // 计算文字相对于导航容器的 left 和 top
        const left = labelRect.left - navRect.left;
        const top = el.offsetTop + el.offsetHeight - 2; // 垂直位置保持不变
        const width = labelRect.width; // 宽度与文字完全一致

        indicator.style.transition = animate ? 'left 300ms ease, width 300ms ease, top 300ms ease' : 'none';
        indicator.style.left = left + 'px';
        indicator.style.top = top + 'px';
        indicator.style.bottom = 'auto';
        indicator.style.width = width + 'px';
    }

  function initIndicator() {
    if (!indicator || !links.length) return;
    // Base style in case CSS didn't apply yet
    indicator.style.position = 'absolute';
  indicator.style.top = '0px';
    indicator.style.height = '2px';
    indicator.style.background = '#0F766E';
    indicator.style.borderRadius = '2px';

  const active = links.find((a) => a.hasAttribute('data-active')) || links[0];
  // 初次渲染与字体加载后再校准一次
  setIndicatorTo(active, false);
  window.requestAnimationFrame(() => setIndicatorTo(active, false));
  window.addEventListener('load', () => setIndicatorTo(active, false));

    // 按你的需求：不再跟随悬停移动指示条，保持在当前激活项下方

    // Keep in sync on resize
    window.addEventListener('resize', () => {
      const act = links.find((a) => a.hasAttribute('data-active')) || links[0];
      setIndicatorTo(act, false);
    });
  }

  function findNavLinkByHref(href) {
    if (!href) return null;
    const targetPath = new URL(href, window.location.href).pathname;
    return links.find((l) => new URL(l.href, window.location.href).pathname === targetPath) || null;
  }

  function enablePageTransitions() {
    if (!page) return;
    // Enter transition on load
    page.classList.add('page-enter');
    requestAnimationFrame(() => {
      page.classList.add('page-enter-active');
    });

    // Intercept nav clicks and buttons with data-transition
    const clickable = [
      ...links,
      ...Array.from(document.querySelectorAll('a[data-transition]')),
    ];

    clickable.forEach((a) => {
      a.addEventListener('click', (e) => {
        const href = a.getAttribute('href');
        if (!href || href.startsWith('#') || a.target === '_blank') return;
        // Only animate internal navigation
        if (href.startsWith('http')) return;
        e.preventDefault();
        // Move indicator to the nav item matching destination
        const targetNav = links.includes(a) ? a : findNavLinkByHref(href);
        if (targetNav) setIndicatorTo(targetNav);
        // Leave animation
        page.classList.add('page-leave');
        setTimeout(() => {
          window.location.href = href;
        }, Math.max(PAGE_DURATION, NAV_DURATION) - 20);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initIndicator();
    enablePageTransitions();
  });
})();
