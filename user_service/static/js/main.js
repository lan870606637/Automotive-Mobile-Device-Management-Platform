/**
 * 车载测试设备管理系统 - 用户端JS
 */

// Toast提示功能
function showToast(message, duration = 2000) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

// 格式化日期
function formatDate(date, format = 'YYYY-MM-DD') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hour = String(d.getHours()).padStart(2, '0');
    const minute = String(d.getMinutes()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hour)
        .replace('mm', minute);
}

// 手机号脱敏
function maskPhone(phone) {
    if (!phone || phone.length !== 11) return phone;
    return phone.substring(0, 3) + '****' + phone.substring(7);
}

// 防抖函数
function debounce(func, wait) {
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

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// AJAX请求封装
function request(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    
    if (mergedOptions.body && typeof mergedOptions.body === 'object') {
        mergedOptions.body = JSON.stringify(mergedOptions.body);
    }
    
    return fetch(url, mergedOptions)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        });
}

// 本地存储封装
const storage = {
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.error('Storage set error:', e);
        }
    },
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.error('Storage get error:', e);
            return defaultValue;
        }
    },
    remove(key) {
        try {
            localStorage.removeItem(key);
        } catch (e) {
            console.error('Storage remove error:', e);
        }
    }
};

// 表单验证
const validators = {
    required(value, message = '此项为必填') {
        if (!value || value.trim() === '') {
            return message;
        }
        return true;
    },
    
    phone(value, message = '请输入正确的手机号') {
        const phoneRegex = /^1[3-9]\d{9}$/;
        if (!phoneRegex.test(value)) {
            return message;
        }
        return true;
    },
    
    minLength(value, length, message) {
        message = message || `最少需要${length}个字符`;
        if (value.length < length) {
            return message;
        }
        return true;
    },
    
    maxLength(value, length, message) {
        message = message || `最多${length}个字符`;
        if (value.length > length) {
            return message;
        }
        return true;
    }
};

// 验证表单
function validateForm(formData, rules) {
    const errors = {};
    
    for (const field in rules) {
        const value = formData[field];
        const fieldRules = rules[field];
        
        for (const rule of fieldRules) {
            let result;
            if (typeof rule === 'function') {
                result = rule(value);
            } else if (typeof rule === 'string') {
                result = validators.required(value, rule);
            } else if (Array.isArray(rule)) {
                const [validatorName, ...args] = rule;
                result = validators[validatorName](value, ...args);
            }
            
            if (result !== true) {
                errors[field] = result;
                break;
            }
        }
    }
    
    return {
        isValid: Object.keys(errors).length === 0,
        errors
    };
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 添加页面转场动画
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.3s';
        document.body.style.opacity = '1';
    }, 10);
    
    // 阻止双击缩放
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, false);
    
    // iOS底部安全区域适配
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    if (isIOS) {
        document.body.style.paddingBottom = 'env(safe-area-inset-bottom)';
    }
});

// 微信JS-SDK初始化（实际使用时需要配置）
function initWechatSDK() {
    // 这里需要后端提供签名
    // wx.config({
    //     debug: false,
    //     appId: '',
    //     timestamp: '',
    //     nonceStr: '',
    //     signature: '',
    //     jsApiList: ['getLocation', 'scanQRCode']
    // });
}

// 获取地理位置
function getCurrentLocation(callback) {
    if (typeof wx !== 'undefined') {
        // 微信环境
        wx.getLocation({
            type: 'gcj02',
            success: function(res) {
                callback && callback({
                    latitude: res.latitude,
                    longitude: res.longitude,
                    success: true
                });
            },
            fail: function() {
                callback && callback({ success: false });
            }
        });
    } else if (navigator.geolocation) {
        // 浏览器环境
        navigator.geolocation.getCurrentPosition(
            function(position) {
                callback && callback({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    success: true
                });
            },
            function() {
                callback && callback({ success: false });
            }
        );
    } else {
        callback && callback({ success: false });
    }
}

// 显示原因/备注气泡提示
function showReasonTooltip(btn, reason) {
    let tooltip = document.getElementById('reasonTooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'reasonTooltip';
        tooltip.style.cssText = 'position:fixed;display:none;background:#333;color:#fff;padding:8px 12px;border-radius:4px;font-size:12px;max-width:300px;z-index:10000;word-wrap:break-word;';
        document.body.appendChild(tooltip);
    }
    tooltip.textContent = reason;
    const rect = btn.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.bottom + 8) + 'px';
    tooltip.style.display = 'block';
    setTimeout(() => {
        document.addEventListener('click', function hide() {
            tooltip.style.display = 'none';
            document.removeEventListener('click', hide);
        });
    }, 100);
}

// 导出全局函数
window.showToast = showToast;
window.formatDate = formatDate;
window.maskPhone = maskPhone;
window.debounce = debounce;
window.throttle = throttle;
window.request = request;
window.storage = storage;
window.validateForm = validateForm;
window.getCurrentLocation = getCurrentLocation;
window.showReasonTooltip = showReasonTooltip;
