document.addEventListener('DOMContentLoaded', () => {
  // 读取后端注入的项目数据
  const projectsFromServer = (() => {
    try {
      const el = document.getElementById('projects-json');
      if (el && el.textContent && el.textContent.trim()) {
        return JSON.parse(el.textContent);
      }
    } catch (e) { console.warn('projects-json parse failed:', e); }
    return null;
  })();

  const sampleProjects = [
    {
      id: 'p1', name: 'Example-Java', language: 'Java',
      chains: [
        {
          id: 'c1', entry: 'readObject',
          nodes: [
            { id: 'A', label: 'ObjectInputStream.readObject', short: 'readObject', type: 'entry' },
            { id: 'B', label: 'GadgetA.trigger()', short: 'trigger', type: 'gadget' },
            { id: 'C', label: 'Runtime.exec()', short: 'exec', type: 'sink' }
          ],
          edges: [
            { from: 'A', to: 'B', label: 'calls' },
            { from: 'B', to: 'C', label: 'leads to' }
          ]
        }
      ]
    }
  ];

  const projects = projectsFromServer || sampleProjects;

  // UI 元素
  const projectListEl = document.getElementById('project-list');
  const projectCountEl = document.getElementById('project-count');
  const graphTitleEl = document.getElementById('graph-title');
  const graphMetaEl = document.getElementById('graph-meta');
  const chainSelect = document.getElementById('chain-select'); // 原生 select（隐藏）
  const chainWrap = document.getElementById('chain-select-wrap');
  const chainTrigger = document.getElementById('chain-trigger');
  const chainMenu = document.getElementById('chain-menu');

  function closeMenu() {
    if (!chainMenu) return;
    chainMenu.classList.remove('show');
    chainTrigger && chainTrigger.setAttribute('aria-expanded', 'false');
  }

  function openMenu() {
    if (!chainMenu) return;
    chainMenu.classList.add('show');
    chainTrigger && chainTrigger.setAttribute('aria-expanded', 'true');
  }

  function rebuildMenuFromSelect() {
    if (!chainMenu || !chainSelect) return;
    chainMenu.innerHTML = '';
    Array.from(chainSelect.options).forEach((opt, idx) => {
      const li = document.createElement('li');
      li.className = 'cs-option' + (opt.selected ? ' is-active' : '');
      li.setAttribute('role', 'option');
      li.dataset.value = opt.value;
      li.textContent = opt.textContent;
      li.addEventListener('click', () => {
        chainSelect.value = opt.value;
        if (chainTrigger) chainTrigger.textContent = opt.textContent;
        Array.from(chainMenu.children).forEach(c => c.classList.remove('is-active'));
        li.classList.add('is-active');
        chainSelect.dispatchEvent(new Event('change', { bubbles: true }));
        closeMenu();
      });
      chainMenu.appendChild(li);
      if (idx === 0 && chainTrigger && !chainTrigger.textContent.trim()) {
        chainTrigger.textContent = opt.textContent;
      }
    });
  }

  if (chainTrigger && chainMenu) {
    chainTrigger.addEventListener('click', () => {
      if (chainMenu.classList.contains('show')) closeMenu(); else openMenu();
    });
    document.addEventListener('click', (e) => {
      if (chainWrap && !chainWrap.contains(e.target)) closeMenu();
    });
  }

  // 渲染项目列表
  function renderProjectList(items) {
    projectListEl.innerHTML = '';
    if (!items || items.length === 0) {
      projectListEl.innerHTML = '<div class="text-sm text-gray-500 py-8 text-center">暂无项目</div>';
      projectCountEl.textContent = '0 个';
      return;
    }
    projectCountEl.textContent = `${items.length} 个`;
    const projUrl = (document.getElementById('project-btn')?.dataset.projectUrl) || '/project';
    items.forEach((p, idx) => {
      const el = document.createElement('div');
      el.className = 'py-3 px-2 cursor-pointer list-hover';
      const hash = encodeURIComponent(p.file_hash || '');
      el.innerHTML = `
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium text-gray-900">${p.name}</div>
            <div class="text-xs text-gray-500 mt-0.5">语言：${p.language} · 链：${p.chains?.length || 0}</div>
          </div>
          <div class="flex items-center gap-2">
            <a class="text-primary text-xs hover:text-accent" href="${projUrl}?hash=${hash}" onclick="event.stopPropagation()">
              <i class="fa fa-list-alt mr-0.5"></i> 项目分析
            </a>
            <div class="chip">${idx + 1}</div>
          </div>
        </div>`;
      el.addEventListener('click', () => selectProject(p));
      projectListEl.appendChild(el);
    });
  }

  // 颜色
  function colorForType(t) {
    switch (t) {
      case 'entry': return '#10b981';
      case 'gadget': return '#38bdf8';
      case 'sink': return '#ef4444';
      default: return '#14b8a6';
    }
  }

  // 图谱
  let network = null;
  function createNetwork(container, data) {
    const options = {
      layout: { improvedLayout: true },
      physics: { stabilization: true, barnesHut: { springLength: 120 } },
      interaction: { hover: true },
      nodes: { shape: 'dot', size: 18, font: { color: '#0F172A', face: 'Inter', size: 12 }, borderWidth: 1 },
      edges: { arrows: { to: { enabled: true, scaleFactor: 0.7 } }, color: { color: '#94a3b8' }, smooth: { type: 'dynamic' }, font: { align: 'top' } }
    };
    network = new vis.Network(container, data, options);

    // 悬停提示：紧跟鼠标右下角，限制在容器内
    const tooltipEl = document.getElementById('graph-tooltip');
    const graphEl = container; // #graph
    let hoveredNodeId = null;
    const offset = 10;

    function placeNear(x, y) {
      const contW = graphEl.clientWidth;
      const contH = graphEl.clientHeight;
      const tw = tooltipEl.offsetWidth || 220;
      const th = tooltipEl.offsetHeight || 32;
      let left = x + offset;
      let top = y + offset;
      // 边界防溢出，必要时翻转到左/上侧
      if (left + tw > contW - 8) left = x - tw - offset;
      if (top + th > contH - 8) top = y - th - offset;
      tooltipEl.style.left = left + 'px';
      tooltipEl.style.top = top + 'px';
    }

    network.on('hoverNode', (params) => {
      const node = data.nodes.get(params.node);
      if (!node) return;
      hoveredNodeId = params.node;
      tooltipEl.textContent = node.title || node.label || '';
      tooltipEl.style.display = 'block';
    });

    network.on('blurNode', () => {
      hoveredNodeId = null;
      tooltipEl.style.display = 'none';
    });

    // 跟随鼠标移动（DOM 坐标，已相对容器）
    network.on('pointerMove', (params) => {
      if (!hoveredNodeId) return;
      const { x, y } = params.pointer.DOM;
      placeNear(x, y);
    });

    // 缩放/拖拽时用节点位置微调，避免偏离
    ['zoom', 'dragging', 'afterDrawing'].forEach(evt => {
      network.on(evt, () => {
        if (!hoveredNodeId) return;
        const pos = network.getPositions([hoveredNodeId])[hoveredNodeId];
        if (!pos) return;
        const dom = network.canvasToDOM(pos);
        placeNear(dom.x, dom.y);
      });
    });

    // 删除原先基于 e.clientX/Y 的 mousemove 跟随
    // （如果你文件中还有 container.addEventListener('mousemove', ...) 相关代码，直接移除）
  }

  function renderGraph(project, chainIdx = 0) {
    const container = document.getElementById('graph');
    const sk = document.getElementById('graph-skeleton');

    if (!project || !project.chains || project.chains.length === 0) {
      graphTitleEl.textContent = '（无数据）';
      graphMetaEl.textContent = '0 节点 · 0 边';
      container.innerHTML = '<div class="h-full flex items-center justify-center text-gray-400">暂无调用链</div>';
      return;
    }
    graphTitleEl.textContent = `${project.name}`;

  const useAll = (chainIdx === 'all');
  // 大图合并时显示骨架屏，提升感知速度
  if (sk) sk.classList.toggle('hidden', !useAll);
    let nodes, edges;

    if (useAll) {
      // 合并多个链：用完整 label 去重节点，保留类型优先级 entry > gadget > sink
      const nodeMap = new Map();
      const edgePairs = [];
      const typeRank = { 'entry': 2, 'gadget': 1, 'sink': 0 };

      project.chains.forEach(ch => {
        const localIdToLabel = new Map(ch.nodes.map(n => [n.id, n.label]));
        ch.nodes.forEach(n => {
          const key = n.label;
          const exist = nodeMap.get(key);
          if (!exist || typeRank[n.type] > typeRank[exist.type]) nodeMap.set(key, n);
        });
        ch.edges.forEach(e => {
          const fromLabel = localIdToLabel.get(e.from) || e.from;
          const toLabel = localIdToLabel.get(e.to) || e.to;
          edgePairs.push({ fromLabel, toLabel, label: e.label });
        });
      });

      const idMap = new Map();
      let idSeq = 0;
      const arr = Array.from(nodeMap.values());
      arr.forEach(n => { idMap.set(n.label, `m${idSeq++}`); });

      nodes = new vis.DataSet(arr.map(n => ({
        id: idMap.get(n.label),
        label: (n.short || n.label),
        title: n.label,
        color: colorForType(n.type)
      })));
      edges = new vis.DataSet(edgePairs.map(e => ({
        from: idMap.get(e.fromLabel),
        to: idMap.get(e.toLabel),
        label: e.label
      })));
    } else {
      const chain = project.chains[chainIdx];
      nodes = new vis.DataSet(chain.nodes.map(n => ({
        id: n.id, label: (n.short || n.label), title: n.label, color: colorForType(n.type)
      })));
      edges = new vis.DataSet(chain.edges.map(e => ({ from: e.from, to: e.to, label: e.label })));
    }

    const nCount = typeof nodes.length === 'number' ? nodes.length : nodes.getIds().length;
    const eCount = typeof edges.length === 'number' ? edges.length : edges.getIds().length;
    graphMetaEl.textContent = `${nCount} 节点 · ${eCount} 边`;

    container.innerHTML = '';
    createNetwork(container, { nodes, edges });
    if (useAll && network) {
      const hideSk = () => { if (sk) sk.classList.add('hidden'); network.off('stabilizationIterationsDone', hideSk); };
      network.once('stabilizationIterationsDone', hideSk);
      // 最坏兜底：2s 后仍未触发则手动隐藏
      setTimeout(() => { if (sk) sk.classList.add('hidden'); }, 2000);
    }
  }

  // 图表统计
  let pie = null, bar = null;
  const pieCtx = document.getElementById('pieChart');
  const barCtx = document.getElementById('barChart');

  // 保障画布高度，避免 0 高导致不可见
  try {
    if (pieCtx && !pieCtx.height) pieCtx.height = 240;
    if (barCtx && !barCtx.height) barCtx.height = 240;
  } catch (_) {}

  // 统一 Chart 外观
  if (window.Chart) {
    Chart.defaults.font.family = 'Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"';
    Chart.defaults.color = '#334155';
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
  }

  // 柱状图数值标签
  const valueLabelPlugin = {
    id: 'valueLabel',
    afterDatasetsDraw(chart) {
      if (chart.config.type !== 'bar') return;
      const { ctx } = chart;
      ctx.save();
      ctx.fillStyle = '#0F172A';
      ctx.font = '600 12px Inter, system-ui';
      chart.data.datasets.forEach((dataset, i) => {
        const meta = chart.getDatasetMeta(i);
        meta.data.forEach((bar, index) => {
          const val = dataset.data[index];
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(String(val), bar.x, bar.y - 4);
        });
      });
      ctx.restore();
    }
  };

  // 环形图中心文本（Top 语言 + 百分比）
  const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart, args, opts) {
      if (!opts || chart.config.type !== 'doughnut') return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      const cx = (chartArea.left + chartArea.right) / 2;
      const cy = (chartArea.top + chartArea.bottom) / 2;
      ctx.save();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      if (opts.title) {
        ctx.fillStyle = '#0F766E';
        ctx.font = '600 13px Inter, system-ui';
        ctx.fillText(String(opts.title), cx, cy - 8);
      }
      if (opts.subtitle) {
        ctx.fillStyle = '#0f172a';
        ctx.font = '700 16px Inter, system-ui';
        ctx.fillText(String(opts.subtitle), cx, cy + 12);
      }
      ctx.restore();
    }
  };

  if (window.Chart) Chart.register(valueLabelPlugin, centerTextPlugin);

  function computeStats(ps) {
    const byLang = {};
    let totalChains = 0;
    ps.forEach(p => {
      byLang[p.language] = (byLang[p.language] || 0) + 1;
      totalChains += (p.chains?.length || 0);
    });
    return { byLang, totalProjects: ps.length, totalChains };
  }

  function updateCharts() {
    if (!window.Chart || !pieCtx || !barCtx) return;
    const stats = computeStats(projects);
    const labels = Object.keys(stats.byLang);
    const data = Object.values(stats.byLang);
    // 项目主色：与站点主题保持一致（#008080 为主，逐步明亮）
    const colors = ['#008080', '#0fa4a4', '#14b8a6', '#22d3ee', '#8b5cf6', '#f59e0b'];

    // 环形图数据兜底
    const _labels = labels.length ? labels : ['暂无数据'];
    const _data = labels.length ? data : [1];
    const _bg = labels.length ? colors.slice(0, _labels.length) : ['#e5e7eb'];

    if (pie) pie.destroy();
    // 计算中心文本
  const total = _data.reduce((a, b) => a + b, 0);
    pie = new Chart(pieCtx, {
      type: 'doughnut',
      data: { labels: _labels, datasets: [{ data: _data, backgroundColor: _bg, borderColor: '#fff', borderWidth: 2, hoverOffset: 8 }] },
      options: {
        maintainAspectRatio: false,
        cutout: '72%',
        spacing: 2,
        animation: { animateScale: true, duration: 800, easing: 'easeOutQuart' },
        plugins: {
          legend: { position: 'bottom', align: 'center', labels: { usePointStyle: true, padding: 8, boxWidth: 10 } },
          title: { display: false },
          // 中心固定文案：项目分布
          centerText: { title: '项目分布' },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const v = ctx.parsed;
                const pct = total ? ((v / total) * 100).toFixed(1) : '0.0';
                return `${ctx.label}: ${v} (${pct}%)`;
              }
            }
          }
        }
      },
      plugins: []
    });

    if (bar) bar.destroy();
    const bctx = barCtx.getContext('2d');
    const grad = bctx ? bctx.createLinearGradient(0, 0, 0, 220) : null;
    if (grad) { grad.addColorStop(0, '#008080'); grad.addColorStop(1, '#14b8a6'); }
    bar = new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: ['Gadget 链总数'],
        datasets: [{ label: '总链路', data: [stats.totalChains], backgroundColor: grad || '#0ea5e922', borderRadius: 8, borderSkipped: false, maxBarThickness: 48 }]
      },
      options: {
        maintainAspectRatio: false,
        animation: { duration: 700, easing: 'easeOutQuart' },
        plugins: { legend: { display: false }, title: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155' } },
          y: { beginAtZero: true, ticks: { precision: 0, padding: 6, color: '#64748b' }, grid: { color: 'rgba(148,163,184,.22)' } }
        }
      },
      plugins: [valueLabelPlugin]
    });
  }

  // 交互
  document.getElementById('fit-btn').addEventListener('click', () => network && network.fit());
  document.getElementById('focus-entry-btn').addEventListener('click', () => {
    if (!network) return;
    const nodes = network.body.data.nodes.get();
    const entry = nodes.find(n => n.color === '#10b981');
    if (entry) network.focus(entry.id, { scale: 1.2, animation: true });
  });
  // 删除多余的调试与残留代码，改用统一流程构建下拉

  chainSelect.addEventListener('change', (e) => {
    const val = e.target.value;
    renderGraph(currentProject, val === 'all' ? 'all' : parseInt(val, 10));
  });

  function selectProject(p) {
    currentProject = p;
    // 更新“项目分析”按钮的可用性
    const projBtn = document.getElementById('project-btn');
    if (projBtn) {
      projBtn.disabled = !p?.file_hash;
      projBtn.classList.toggle('opacity-50', !p?.file_hash);
    }
    chainSelect.innerHTML = '<option value="all">全部链路</option>';
    (p.chains || []).forEach((ch, idx) => {
      const opt = document.createElement('option');
      opt.value = String(idx);
      const label = ch.name ? `链 ${idx + 1}: ${ch.name}` : `链 ${idx + 1}: ${ch.entry}`;
      opt.textContent = label;
      opt.title = ch.name ? `入口: ${ch.entry}` : label;
      chainSelect.appendChild(opt);
    });
    // 默认只渲染第 1 条链，提升首屏速度
    if ((p.chains || []).length > 0) {
      chainSelect.value = '0';
      const firstOpt = Array.from(chainSelect.options).find(o => o.value === '0');
      if (chainTrigger && firstOpt) chainTrigger.textContent = firstOpt.textContent;
    } else {
      if (chainTrigger) chainTrigger.textContent = '全部链路';
    }
    // 重建自定义菜单（会根据当前 selected 高亮）
    rebuildMenuFromSelect();
    renderGraph(p, (p.chains && p.chains.length) ? 0 : 'all');
    updateCharts();
  }

    // 在线审计
    const auditBtn = document.getElementById('audit-btn');
    if (auditBtn) {
      auditBtn.addEventListener('click', () => {
        if (!currentProject) return;
        let idx = 0;
        if (chainSelect && chainSelect.value !== 'all') {
          idx = parseInt(chainSelect.value, 10) || 0;
        }
        const params = new URLSearchParams({
          hash: currentProject.file_hash || '',
          idx: String(idx),
          lang: currentProject.language || ''
        });
        const auditUrl = auditBtn.dataset.auditUrl || '/audit';
        window.location.href = `${auditUrl}?${params.toString()}`;
      });
    }

    // 项目分析：跳转到 /project?hash=...
    const projBtn = document.getElementById('project-btn');
    if (projBtn) {
      projBtn.addEventListener('click', () => {
        if (!currentProject || !currentProject.file_hash) return;
        const url = projBtn.dataset.projectUrl || '/project';
        const params = new URLSearchParams({ hash: currentProject.file_hash });
        window.location.href = `${url}?${params.toString()}`;
      });
    }

  // 初始化
  let currentProject = null;
  renderProjectList(projects);
  if (projects.length) {
    selectProject(projects[0]);
    updateCharts();
  }

  // 初次生成菜单（即使没有项目也不会报错）
  rebuildMenuFromSelect();
});