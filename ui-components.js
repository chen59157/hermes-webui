/**
 * Hermes WebUI - UI Components
 * 通用UI组件JavaScript库
 */

// ============================================
// Toast 通知组件
// ============================================

class HermesToast {
  static container = null;
  static queue = [];
  static maxToasts = 5;
  static defaultDuration = 3000;

  /**
   * 初始化Toast容器
   */
  static init() {
    if (this.container) return;

    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    this.container.setAttribute('aria-live', 'polite');
    document.body.appendChild(this.container);
  }

  /**
   * 显示Toast通知
   * @param {string} message - 消息内容
   * @param {string} type - 类型: 'success', 'error', 'warning', 'info'
   * @param {Object} options - 配置选项
   */
  static show(message, type = 'info', options = {}) {
    this.init();

    const {
      title = '',
      duration = this.defaultDuration,
      closable = true,
      onClick = null
    } = options;

    // 创建Toast元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');

    // 构建内容
    let html = `
      <div class="toast-icon">
        ${this.getIcon(type)}
      </div>
      <div class="toast-content">
        ${title ? `<div class="toast-title">${title}</div>` : ''}
        <div class="toast-message">${message}</div>
      </div>
    `;

    if (closable) {
      html += `
        <button class="toast-close" aria-label="关闭">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 1L13 13M1 13L13 1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
      `;
    }

    toast.innerHTML = html;

    // 绑定事件
    if (closable) {
      const closeBtn = toast.querySelector('.toast-close');
      closeBtn.addEventListener('click', () => this.remove(toast));
    }

    if (onClick) {
      toast.style.cursor = 'pointer';
      toast.addEventListener('click', (e) => {
        if (!e.target.closest('.toast-close')) {
          onClick();
        }
      });
    }

    // 添加到容器
    this.container.appendChild(toast);

    // 触发动画
    requestAnimationFrame(() => {
      toast.classList.add('toast-enter');
    });

    // 自动消失
    if (duration > 0) {
      setTimeout(() => this.remove(toast), duration);
    }

    // 限制数量
    this.queue.push(toast);
    if (this.queue.length > this.maxToasts) {
      this.remove(this.queue[0]);
    }

    return toast;
  }

  /**
   * 移除Toast
   */
  static remove(toast) {
    if (!toast || !toast.parentNode) return;

    toast.classList.add('toast-exit');
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
      const index = this.queue.indexOf(toast);
      if (index > -1) {
        this.queue.splice(index, 1);
      }
    }, 300);
  }

  /**
   * 获取图标SVG
   */
  static getIcon(type) {
    const icons = {
      success: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 0C4.48 0 0 4.48 0 10s4.48 10 10 10 10-4.48 10-10S15.52 0 10 0zm-1 15l-5-5 1.41-1.41L9 12.17l7.59-7.59L18 6l-9 9z" fill="currentColor"/></svg>',
      error: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 0C4.48 0 0 4.48 0 10s4.48 10 10 10 10-4.48 10-10S15.52 0 10 0zm1 15H9v-2h2v2zm0-4H9V5h2v6z" fill="currentColor"/></svg>',
      warning: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M1 17h18L10 1 1 17zm9-2.5h-.01V14.5h.01v0zm0-3.5h-.01V8h.01v3z" fill="currentColor"/></svg>',
      info: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 0C4.48 0 0 4.48 0 10s4.48 10 10 10 10-4.48 10-10S15.52 0 10 0zm1 15H9V9h2v6zm0-8H9V5h2v2z" fill="currentColor"/></svg>'
    };
    return icons[type] || icons.info;
  }

  // 快捷方法
  static success(message, options = {}) {
    return this.show(message, 'success', options);
  }

  static error(message, options = {}) {
    return this.show(message, 'error', { duration: 5000, ...options });
  }

  static warning(message, options = {}) {
    return this.show(message, 'warning', { duration: 4000, ...options });
  }

  static info(message, options = {}) {
    return this.show(message, 'info', options);
  }
}

// ============================================
// Dialog 弹窗组件
// ============================================

class HermesDialog {
  static activeDialog = null;

  /**
   * 显示错误弹窗
   */
  static showError(title, message, details = '') {
    return this.show({
      type: 'error',
      title,
      message,
      details,
      buttons: [
        { text: '确定', type: 'primary', action: 'close' }
      ]
    });
  }

  /**
   * 显示确认弹窗
   */
  static showConfirm(title, message, onConfirm, onCancel = null) {
    return this.show({
      type: 'warning',
      title,
      message,
      buttons: [
        { text: '取消', type: 'secondary', action: 'cancel' },
        { text: '确定', type: 'primary', action: 'confirm' }
      ],
      onAction: (action) => {
        if (action === 'confirm' && onConfirm) onConfirm();
        if (action === 'cancel' && onCancel) onCancel();
      }
    });
  }

  /**
   * 显示弹窗
   */
  static show(options) {
    const {
      type = 'info',
      title = '',
      message = '',
      details = '',
      buttons = [],
      onAction = null,
      closable = true
    } = options;

    // 移除现有弹窗
    if (this.activeDialog) {
      this.remove(this.activeDialog);
    }

    // 创建遮罩
    const overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';

    // 创建弹窗
    const dialog = document.createElement('div');
    dialog.className = `dialog dialog-${type}`;

    // 构建内容
    let html = `
      <div class="dialog-header">
        <div class="dialog-icon">${this.getIcon(type)}</div>
        <h3 class="dialog-title">${title}</h3>
        ${closable ? `
          <button class="dialog-close" aria-label="关闭">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M1 1L15 15M1 15L15 1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </button>
        ` : ''}
      </div>
      <div class="dialog-body">
        <p class="dialog-message">${message}</p>
        ${details ? `<div class="dialog-details"><pre>${details}</pre></div>` : ''}
      </div>
    `;

    if (buttons.length > 0) {
      html += `
        <div class="dialog-footer">
          ${buttons.map(btn => `
            <button class="btn btn-${btn.type}" data-action="${btn.action}">
              ${btn.text}
            </button>
          `).join('')}
        </div>
      `;
    }

    dialog.innerHTML = html;
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // 绑定事件
    if (closable) {
      const closeBtn = dialog.querySelector('.dialog-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => this.remove(overlay));
      }
    }

    // 按钮事件
    dialog.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        if (onAction) onAction(action);
        this.remove(overlay);
      });
    });

    // 点击遮罩关闭
    if (closable) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          this.remove(overlay);
        }
      });
    }

    // ESC键关闭
    const escHandler = (e) => {
      if (e.key === 'Escape' && closable) {
        this.remove(overlay);
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);

    // 触发动画
    requestAnimationFrame(() => {
      overlay.classList.add('dialog-enter');
    });

    this.activeDialog = overlay;
    return overlay;
  }

  /**
   * 移除弹窗
   */
  static remove(overlay) {
    if (!overlay || !overlay.parentNode) return;

    overlay.classList.add('dialog-exit');
    setTimeout(() => {
      if (overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
      if (this.activeDialog === overlay) {
        this.activeDialog = null;
      }
    }, 300);
  }

  /**
   * 获取图标SVG
   */
  static getIcon(type) {
    const icons = {
      error: '<svg width="48" height="48" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" fill="var(--color-error)" opacity="0.2"/><path d="M24 12v16M24 32v2" stroke="var(--color-error)" stroke-width="3" stroke-linecap="round"/></svg>',
      warning: '<svg width="48" height="48" viewBox="0 0 48 48" fill="none"><path d="M24 8L4 42h40L24 8z" fill="var(--color-warning)" opacity="0.2"/><path d="M24 18v10M24 32v2" stroke="var(--color-warning)" stroke-width="3" stroke-linecap="round"/></svg>',
      info: '<svg width="48" height="48" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" fill="var(--color-info)" opacity="0.2"/><path d="M24 16v2M24 22v12" stroke="var(--color-info)" stroke-width="3" stroke-linecap="round"/></svg>',
      success: '<svg width="48" height="48" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" fill="var(--color-success)" opacity="0.2"/><path d="M14 24l7 7 13-13" stroke="var(--color-success)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    };
    return icons[type] || icons.info;
  }
}

// ============================================
// Loading 加载组件
// ============================================

class HermesLoading {
  static overlay = null;
  static spinner = null;

  /**
   * 显示全屏加载
   */
  static show(message = '加载中...') {
    if (this.overlay) return;

    this.overlay = document.createElement('div');
    this.overlay.className = 'loading-overlay';
    this.overlay.innerHTML = `
      <div class="loading-content">
        <div class="loading-spinner"></div>
        <div class="loading-text">${message}</div>
      </div>
    `;

    document.body.appendChild(this.overlay);
    requestAnimationFrame(() => {
      this.overlay.classList.add('loading-enter');
    });
  }

  /**
   * 隐藏全屏加载
   */
  static hide() {
    if (!this.overlay) return;

    this.overlay.classList.add('loading-exit');
    setTimeout(() => {
      if (this.overlay && this.overlay.parentNode) {
        this.overlay.parentNode.removeChild(this.overlay);
        this.overlay = null;
      }
    }, 300);
  }

  /**
   * 更新加载消息
   */
  static updateMessage(message) {
    if (!this.overlay) return;
    const text = this.overlay.querySelector('.loading-text');
    if (text) text.textContent = message;
  }

  /**
   * 显示内联加载
   */
  static showInline(element, message = '') {
    if (!element) return;

    const spinner = document.createElement('div');
    spinner.className = 'loading-inline';
    spinner.innerHTML = `
      <div class="loading-spinner-small"></div>
      ${message ? `<span class="loading-inline-text">${message}</span>` : ''}
    `;

    element.appendChild(spinner);
    return spinner;
  }

  /**
   * 隐藏内联加载
   */
  static hideInline(spinner) {
    if (spinner && spinner.parentNode) {
      spinner.parentNode.removeChild(spinner);
    }
  }

  /**
   * 更新进度
   */
  static updateProgress(progress) {
    // 可用于带进度条的加载场景
    console.log(`Loading progress: ${progress}%`);
  }
}

// ============================================
// 工具函数
// ============================================

class HermesUtils {
  /**
   * 防抖函数
   */
  static debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * 节流函数
   */
  static throttle(func, limit = 300) {
    let inThrottle;
    return function executedFunction(...args) {
      if (!inThrottle) {
        func(...args);
        inThrottle = true;
        setTimeout(() => {
          inThrottle = false;
        }, limit);
      }
    };
  }

  /**
   * 格式化文件大小
   */
  static formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * 格式化时间
   */
  static formatTime(seconds) {
    if (seconds < 60) return `${Math.floor(seconds)}秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`;
    return `${Math.floor(seconds / 3600)}小时${Math.floor((seconds % 3600) / 60)}分钟`;
  }

  /**
   * 复制到剪贴板
   */
  static async copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      HermesToast.success('已复制到剪贴板');
      return true;
    } catch (err) {
      // 降级方案
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        HermesToast.success('已复制到剪贴板');
        return true;
      } catch (err) {
        HermesToast.error('复制失败');
        return false;
      } finally {
        document.body.removeChild(textArea);
      }
    }
  }

  /**
   * 深拷贝
   */
  static deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof RegExp) return new RegExp(obj);
    if (Array.isArray(obj)) return obj.map(item => this.deepClone(item));

    const cloned = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = this.deepClone(obj[key]);
      }
    }
    return cloned;
  }

  /**
   * 生成唯一ID
   */
  static generateId() {
    return 'hermes_' + Date.now().toString(36) + Math.random().toString(36).substr(2);
  }

  /**
   * 延迟执行
   */
  static delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 安全的JSON解析
   */
  static safeJsonParse(str, defaultValue = null) {
    try {
      return JSON.parse(str);
    } catch (e) {
      return defaultValue;
    }
  }
}

// ============================================
// 主题管理
// ============================================

class HermesTheme {
  static currentTheme = 'dark';
  static listeners = [];

  /**
   * 初始化主题
   */
  static init() {
    // 从localStorage读取保存的主题
    const savedTheme = localStorage.getItem('hermes-theme') || 'dark';
    this.setTheme(savedTheme);

    // 监听系统主题变化
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      mediaQuery.addEventListener('change', (e) => {
        if (!localStorage.getItem('hermes-theme')) {
          this.setTheme(e.matches ? 'dark' : 'light');
        }
      });
    }
  }

  /**
   * 设置主题
   */
  static setTheme(theme) {
    this.currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);

    // 通知监听器
    this.listeners.forEach(listener => listener(theme));
  }

  /**
   * 切换主题
   */
  static toggle() {
    const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.setTheme(newTheme);
    localStorage.setItem('hermes-theme', newTheme);
    return newTheme;
  }

  /**
   * 获取当前主题
   */
  static getTheme() {
    return this.currentTheme;
  }

  /**
   * 添加主题变化监听器
   */
  static onChange(callback) {
    this.listeners.push(callback);
    return () => {
      const index = this.listeners.indexOf(callback);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }
}

// ============================================
// 自动初始化
// ============================================

// 在DOM加载完成后初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    HermesTheme.init();
  });
} else {
  HermesTheme.init();
}

// 暴露到全局
window.HermesToast = HermesToast;
window.HermesDialog = HermesDialog;
window.HermesLoading = HermesLoading;
window.HermesUtils = HermesUtils;
window.HermesTheme = HermesTheme;

// 兼容旧代码
window._hermesSetStatus = function(message, isError = false) {
  if (isError) {
    HermesToast.error(message);
  } else {
    HermesToast.info(message);
  }
};

window._hermesSetProgress = function(progress) {
  HermesLoading.updateProgress(progress);
};

console.log('[Hermes] UI Components initialized');
