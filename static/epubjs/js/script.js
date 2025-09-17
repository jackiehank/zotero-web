// 3. JavaScript 核心逻辑
document.addEventListener('DOMContentLoaded', function () {

    // --- 全局变量 ---
    let book;
    let rendition;

    // --- 获取URL参数 ---
    const urlParams = new URLSearchParams(window.location.search);
    let epubUrl = urlParams.get("file");

    // console.log("🔍 原始参数:", window.location.search);
    // console.log("🔍 获取到 file:", epubUrl);

    if (!epubUrl) {
        showError("缺少文件参数");
        alert("请提供 EPUB 文件路径，例如：?file=your-book.epub");
        throw new Error("Missing file parameter");
    }

    // 关键修复：不进行URL解码，直接使用编码后的URL
    // console.log("📖 使用编码后的URL:", epubUrl);

    // 检查URL是否是绝对URL
    if (epubUrl.startsWith('http://') || epubUrl.startsWith('https://')) {
        // console.log("📖 使用绝对URL:", epubUrl);
    } else {
        // 如果是相对URL，转换为绝对URL
        const baseUrl = window.location.origin;
        epubUrl = baseUrl + epubUrl;
        // console.log("📖 转换为绝对URL:", epubUrl);
    }

    // --- DOM 元素引用 ---
    const sidebarEl = document.getElementById('sidebar');
    const tocEl = document.getElementById('toc');
    const toggleTocBtn = document.getElementById('toggle-toc');
    const viewerEl = document.getElementById('viewer');
    const prevBtn = document.getElementById('prev');
    const nextBtn = document.getElementById('next');
    const titleEl = document.getElementById('title');
    const progressEl = document.getElementById('progress');
    const loaderEl = document.getElementById('loader');
    const errorMessageEl = document.getElementById('error-message');

    // --- 初始化函数 ---
    function initEPUB() {
        showLoader();

        // 创建 Book 对象
        book = ePub(epubUrl, {
            requestCredentials: true,
            requestHeaders: {
                'Accept': 'application/epub+zip',
            },
            openAs: 'epub', // 明确指定打开类型
            method: 'binary' // 使用二进制方法
        });

        // 设置 Rendition (渲染器)
        rendition = book.renderTo(viewerEl, {
            width: '100%',
            height: '100%',
            manager: 'default', // 使用默认的分页管理器，这是实现分页和懒加载的关键
            flow: 'scrolled',  // paginated 设置为分页模式（'scrolled' 则为滚动模式）
            spread: "none",  // 可选：设置双页视图
        });

        // 注册关键事件监听器
        setupEventListeners();

        // 初始化阅读器并显示内容
        rendition.display()
            .then(() => {
                hideLoader();
                // 书籍加载后，获取并渲染目录
                book.loaded.navigation.then(function (nav) {
                    renderToc(nav.toc);
                });
                // 更新书籍标题
                book.loaded.metadata.then(function (meta) {
                    titleEl.textContent = meta.title || 'ePub 阅读器';
                });

                // 动态调整字体大小以适应不同设备
                updateEpubFontSize();
            })
            .catch(error => {
                console.error('渲染电子书失败:', error);
                hideLoader();
                showError('无法加载电子书: ' + error.message);
            });

    }

    // --- 事件监听器设置 ---
    function setupEventListeners() {
        // 目录显示/隐藏切换
        toggleTocBtn.addEventListener('click', function () {
            sidebarEl.classList.toggle('hidden');
        });

        // 上一页/下一页导航
        prevBtn.addEventListener('click', function () {
            rendition.prev();
        });
        nextBtn.addEventListener('click', function () {
            rendition.next();
        });

        // 键盘快捷键（左/右箭头翻页）
        document.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowLeft') {
                rendition.prev();
            } else if (e.key === 'ArrowRight') {
                rendition.next();
            }
        });
    }

    // --- 核心功能函数 ---

    // 渲染目录
    function renderToc(toc) {
        // 清空现有目录
        tocEl.innerHTML = '';

        if (!toc || toc.length === 0) {
            tocEl.innerHTML = '<p>此电子书没有目录。</p>';
            return;
        }

        // 递归函数来构建嵌套的目录列表
        function createTocList(items, parentEl) {
            const ul = document.createElement('ul');
            parentEl.appendChild(ul);

            items.forEach(item => {
                const li = document.createElement('li');
                const link = document.createElement('a');
                link.href = '#';
                link.textContent = item.label;

                // 点击目录项跳转到对应位置
                link.addEventListener('click', function (e) {
                    e.preventDefault();
                    rendition.display(item.href).then(() => {
                        // 可选：跳转后自动隐藏目录侧边栏
                        sidebarEl.classList.add('hidden');
                    });
                });

                li.appendChild(link);
                ul.appendChild(li);

                // 如果当前项有子项，递归创建子列表
                if (item.subitems && item.subitems.length > 0) {
                    createTocList(item.subitems, li);
                }
            });
        }

        createTocList(toc, tocEl);
    }

    // 显示/隐藏加载指示器
    function showLoader() {
        loaderEl.style.display = 'block';
    }
    function hideLoader() {
        loaderEl.style.display = 'none';
    }

    // 显示错误信息
    function showError(message) {
        errorMessageEl.textContent = message;
        errorMessageEl.style.display = 'block';
    }

    // 响应式字体大小调整
    function updateEpubFontSize() {
        const width = window.innerWidth;

        let fontSize;
        if (width <= 480) {
            fontSize = 18; // 手机小屏（如 iPhone SE）
        } else if (width <= 768) {
            fontSize = 18; // 手机大屏/折叠屏（如 iPhone 14 Pro Max）
        } else if (width <= 1024) {
            fontSize = 22; // 平板（iPad）
        } else {
            fontSize = 22; // 电脑（桌面浏览器）
        }

        rendition.themes.fontSize(fontSize + "px");
    }

    // --- 启动应用 ---
    initEPUB();

});