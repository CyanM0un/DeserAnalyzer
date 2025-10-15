class SeamlessSlider {
    constructor(container) {
        this.container = container;
        this.sliderItems = container.querySelectorAll('.slider-item');
        this.dots = container.querySelectorAll('.dot');
        this.prevBtn = container.querySelector('.prev-btn');
        this.nextBtn = container.querySelector('.next-btn');
        this.currentIndex = 0;
        this.totalSlides = this.sliderItems.length;
        this.autoPlayInterval = null;
        
        this.init();
    }
    
    init() {
        // 绑定事件
        this.prevBtn.addEventListener('click', () => this.prevSlide());
        this.nextBtn.addEventListener('click', () => this.nextSlide());
        
        // 点导航事件
        this.dots.forEach((dot, index) => {
            dot.addEventListener('click', () => this.goToSlide(index));
        });
        
        // 键盘导航
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // 触摸滑动支持
        this.enableTouchSwipe();
        

    }
    
    goToSlide(index) {
        if (index < 0) index = this.totalSlides - 1;
        if (index >= this.totalSlides) index = 0;
        
        // 隐藏当前幻灯片
        this.sliderItems[this.currentIndex].classList.remove('active');
        this.dots[this.currentIndex].classList.remove('active');
        
        // 显示新幻灯片
        this.sliderItems[index].classList.add('active');
        this.dots[index].classList.add('active');
        
        this.currentIndex = index;
        

    }
    
    nextSlide() {
        this.goToSlide(this.currentIndex + 1);
    }
    
    prevSlide() {
        this.goToSlide(this.currentIndex - 1);
    }
    
    handleKeydown(e) {
        switch(e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                this.prevSlide();
                break;
            case 'ArrowRight':
                e.preventDefault();
                this.nextSlide();
                break;
            case 'Home':
                e.preventDefault();
                this.goToSlide(0);
                break;
            case 'End':
                e.preventDefault();
                this.goToSlide(this.totalSlides - 1);
                break;
        }
    }
    
    enableTouchSwipe() {
        let startX = 0;
        let endX = 0;
        const minSwipeDistance = 50;
        
        this.container.addEventListener('touchstart', (e) => {
            startX = e.changedTouches[0].screenX;
            this.pauseAutoPlay();
        });
        
        this.container.addEventListener('touchend', (e) => {
            endX = e.changedTouches[0].screenX;
            const diffX = startX - endX;
            
            if (Math.abs(diffX) > minSwipeDistance) {
                if (diffX > 0) {
                    this.nextSlide();
                } else {
                    this.prevSlide();
                }
            }
            
            this.startAutoPlay();
        });
    }
    

}

// 初始化所有滑块
document.addEventListener('DOMContentLoaded', function() {
    const sliders = document.querySelectorAll('.seamless-slider');
    sliders.forEach(container => {
        new SeamlessSlider(container);
    });
});