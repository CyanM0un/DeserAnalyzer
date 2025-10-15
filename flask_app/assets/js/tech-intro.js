// 技术介绍模块交互逻辑
document.addEventListener('DOMContentLoaded', function() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            // 移除所有active类
            document.querySelectorAll('.nav-item').forEach(el => {
                el.classList.remove('active');
            });
            
            // 为当前点击项添加active类
            this.classList.add('active');
            
            // 隐藏所有内容项
            document.querySelectorAll('.content-item').forEach(el => {
                el.classList.remove('active');
            });
            
            // 显示对应内容
            const targetId = this.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });
    
    // 初始化显示第一个内容项
    if (navItems.length > 0) {
        navItems[0].click();
    }
});