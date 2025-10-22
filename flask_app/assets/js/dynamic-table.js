// 动态表格组件
class DynamicTable {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            jsonFile: container.dataset.jsonFile,
            tableType: container.dataset.tableType || 'default',
            ...options
        };
        
        this.data = null;
        
        this.init();
    }
    
    // 初始化表格
    async init() {
        this.createStructure();
        await this.loadData();
        this.renderTable();
        this.bindEvents();
    }
    
    // 创建表格结构
    createStructure() {
        this.container.innerHTML = `
            <div class="table-wrapper">
                <div class="table-loading">
                    <div class="loading-spinner"></div>
                    正在加载数据...
                </div>
            </div>
        `;
        
        this.wrapper = this.container.querySelector('.table-wrapper');
    }
    
    // 加载JSON数据
    async loadData() {
        try {
            const response = await fetch(this.options.jsonFile);
            if (!response.ok) throw new Error('数据加载失败');
            
            const rawData = await response.json();
            
            // 根据JSON结构提取数据数组
            if (this.options.tableType === 'php') {
                // PHP数据在Applications数组中
                this.data = rawData.Applications || [];
                this.processPHPData();
            } else if (this.options.tableType === 'java') {
                // Java数据在libraries数组中
                this.data = rawData.libraries || [];
                this.processJavaData();
            }
            
        } catch (error) {
            console.error('加载表格数据失败:', error);
            this.showError('数据加载失败，请检查数据文件');
        }
    }
    
    // 处理PHP数据
    processPHPData() {
        if (!this.data || !Array.isArray(this.data)) return;
        
        // 扁平化PHP数据，将嵌套的工具数据展开为列
        this.flatData = this.data.map(item => {
            const flatItem = { name: item.Name };
            
            // 处理PHP-GGC数据
            if (item['PHP-GGC']) {
                flatItem.phpggc_chains = item['PHP-GGC'].Chains || 0;
            }
            
            // 处理FUGIO数据
            if (item.FUGIO) {
                flatItem.fugio_time = item.FUGIO.Time || 'N/A';
                flatItem.fugio_detected = item.FUGIO.Detected || 0;
                flatItem.fugio_new = item.FUGIO.New || 0;
            }
            
            // 处理PFORTIFIER数据
            if (item.PFORTIFIER) {
                flatItem.pfortifier_time = item.PFORTIFIER.Time || 'N/A';
                flatItem.pfortifier_detected = item.PFORTIFIER.Detected || 0;  // 添加这个
                flatItem.pfortifier_new = item.PFORTIFIER.New || 0;           // 添加这个
                flatItem.pfortifier_coverage = item.PFORTIFIER['Patch Coverage'] || '0%';
                flatItem.pfortifier_suggestion = item.PFORTIFIER['Patch Suggestion Coverage'] || '0%';
            }
            
            return flatItem;
        });
        
        this.columns = [
            { key: 'name', name: 'Name', width: 150 },
            { key: 'phpggc_chains', name: 'PHP-GGC Chains', width: 100 },           // 添加这个
            { key: 'fugio_detected', name: 'FUGIO Detected', width: 100 },
            { key: 'fugio_new', name: 'FUGIO New', width: 100 },
            { key: 'fugio_time', name: 'FUGIO Time', width: 100 },
            { key: 'pfortifier_detected', name: 'PFORTIFIER Detected', width: 100 },  // 添加这个
            { key: 'pfortifier_new', name: 'PFORTIFIER New', width: 100 },             // 添加这个
            { key: 'pfortifier_time', name: 'PFORTIFIER Time', width: 120 },
            { key: 'pfortifier_coverage', name: 'PFORTIFIER Patch Coverage', width: 100 },
            { key: 'pfortifier_suggestion', name: 'PFORTIFIER Patch Suggestion Coverage', width: 100 }
        ];
    }
    
    // 处理Java数据
    processJavaData() {
        if (!this.data || !Array.isArray(this.data)) return;
        
        // 扁平化Java数据，将嵌套的工具数据展开为列
        this.flatData = this.data.map(item => {
            const flatItem = { name: item.name || 'N/A', know: item.know || 0 };
            
            // 处理Tabby数据
            if (item.tabby) {
                flatItem.tabby_all = item.tabby.all || 0;
                flatItem.tabby_dd = item.tabby.dd || 0;
                flatItem.tabby_cov = item.tabby.cov || 0;
                flatItem.tabby_new = item.tabby.new || 0;
            }
            
            // 处理Crystallizer数据
            if (item.crystallizer) {
                flatItem.crystallizer_all = item.crystallizer.all || 0;
                flatItem.crystallizer_dd = item.crystallizer.dd || 0;
                flatItem.crystallizer_cov = item.crystallizer.cov || 0;
                flatItem.crystallizer_new = item.crystallizer.new || 0;
            }
            
            // 处理JDD数据
            if (item.jdd) {
                flatItem.jdd_all = item.jdd.all_r || '0(0)';
                flatItem.jdd_dd = item.jdd.dd || 0;
                flatItem.jdd_cov = item.jdd.cov || 0;
                flatItem.jdd_new = item.jdd.new || 0;
            }
            
            // 处理Flash数据
            if (item.flash) {
                flatItem.flash_all = item.flash.all || 0;
                flatItem.flash_dd = item.flash.dd || 0;
                flatItem.flash_cov = item.flash.cov || 0;
                flatItem.flash_new = item.flash.new || 0;
            }
            
            return flatItem;
        });
        
        this.columns = [
            { key: 'name', name: 'Library', width: 120 },
            { key: 'know', name: 'Know', width: 80 },
            
            // Tabby列
            { key: 'tabby_all', name: 'Tabby All', width: 80 },
            { key: 'tabby_dd', name: 'Tabby DD', width: 80 },
            { key: 'tabby_cov', name: 'Tabby Cov', width: 80 },
            { key: 'tabby_new', name: 'Tabby New', width: 80 },
            
            // Crystallizer列
            { key: 'crystallizer_all', name: 'Crystallizer All', width: 100 },
            { key: 'crystallizer_dd', name: 'Crystallizer DD', width: 100 },
            { key: 'crystallizer_cov', name: 'Crystallizer Cov', width: 100 },
            { key: 'crystallizer_new', name: 'Crystallizer New', width: 100 },
            
            // JDD列
            { key: 'jdd_all', name: 'JDD All(F⁷)', width: 100 },
            { key: 'jdd_dd', name: 'JDD DD', width: 80 },
            { key: 'jdd_cov', name: 'JDD Cov', width: 80 },
            { key: 'jdd_new', name: 'JDD New', width: 80 },
            
            // Flash列
            { key: 'flash_all', name: 'Flash All', width: 80 },
            { key: 'flash_dd', name: 'Flash DD', width: 80 },
            { key: 'flash_cov', name: 'Flash Cov', width: 80 },
            { key: 'flash_new', name: 'Flash New', width: 80 }
        ];
    }
    
    // 渲染表格
    renderTable() {
        if (!this.flatData || !this.columns) {
            this.showError('数据格式错误');
            return;
        }
        
        const tableHTML = `
            <table class="dynamic-table">
                <thead>
                    <tr>
                        ${this.columns.map(col => 
                            `<th style="width: ${col.width}px">${col.name}</th>`
                        ).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${this.flatData.map(row => `
                        <tr>
                            ${this.columns.map(col => {
                                const value = row[col.key];
                                return `<td>${this.formatCell(value, col.key)}</td>`;
                            }).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        this.wrapper.innerHTML = tableHTML;
    }
    
    // 格式化单元格内容
    formatCell(value, key) {
        if (value === null || value === undefined) return '-';
        
        // 数字格式化
        if (typeof value === 'number') {
            return value.toLocaleString();
        }
        
        // 百分比格式化
        if (typeof value === 'string' && value.includes('%')) {
            return `<span class="text-primary fw-bold">${value}</span>`;
        }
        
        // 时间格式化
        if (typeof value === 'string' && (key.includes('time') || key.includes('Time'))) {
            return `<span class="text-info">${value}</span>`;
        }
        
        return value;
    }
    

    
    // 绑定事件
    bindEvents() {
        // 窗口大小变化时重新渲染表格
        window.addEventListener('resize', () => {
            // 可以在这里添加响应式调整逻辑
        });
    }
    
    // 绑定拖拽事件
    bindDragEvents() {
        const handles = this.container.querySelectorAll('.drag-handle');
        
        handles.forEach(handle => {
            handle.addEventListener('mousedown', (e) => {
                this.startDrag(e, handle.classList[1]);
            });
        });
        
        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.handleDrag(e);
            }
        });
        
        document.addEventListener('mouseup', () => {
            this.isDragging = false;
            handles.forEach(h => h.style.background = 'rgba(0, 123, 255, 0.1)');
        });
    }
    
    // 开始拖拽
    startDrag(e, direction) {
        this.isDragging = true;
        this.dragDirection = direction;
        this.dragStart = { x: e.clientX, y: e.clientY };
        this.startViewport = { ...this.viewport };
        
        e.target.style.background = 'rgba(0, 123, 255, 0.3)';
    }
    
    // 处理拖拽
    handleDrag(e) {
        const deltaX = e.clientX - this.dragStart.x;
        const deltaY = e.clientY - this.dragStart.y;
        
        switch (this.dragDirection) {
            case 'top':
                this.viewport.y = Math.max(0, this.startViewport.y + deltaY);
                this.viewport.height = Math.max(100, this.startViewport.height - deltaY);
                break;
            case 'bottom':
                this.viewport.height = Math.max(100, this.startViewport.height + deltaY);
                break;
            case 'left':
                this.viewport.x = Math.max(0, this.startViewport.x + deltaX);
                this.viewport.width = Math.max(200, this.startViewport.width - deltaX);
                break;
            case 'right':
                this.viewport.width = Math.max(200, this.startViewport.width + deltaX);
                break;
        }
        
        this.applyViewport();
    }
    
    // 更新视口信息
    updateViewport() {
        const rect = this.wrapper.getBoundingClientRect();
        this.viewport = {
            x: 0,
            y: 0,
            width: rect.width,
            height: rect.height
        };
    }
    
    // 应用视口设置
    applyViewport() {
        this.wrapper.style.transform = `translate(${this.viewport.x}px, ${this.viewport.y}px)`;
        this.wrapper.style.width = `${this.viewport.width}px`;
        this.wrapper.style.height = `${this.viewport.height}px`;
    }
    

    
    // 显示错误
    showError(message) {
        this.wrapper.innerHTML = `
            <div class="table-empty">
                <div class="empty-icon">⚠️</div>
                <div>${message}</div>
            </div>
        `;
    }
}

// 初始化所有动态表格
document.addEventListener('DOMContentLoaded', function() {
    const tableContainers = document.querySelectorAll('.dynamic-table-container');
    
    tableContainers.forEach(container => {
        new DynamicTable(container);
    });
});

// 导出类供外部使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DynamicTable;
}