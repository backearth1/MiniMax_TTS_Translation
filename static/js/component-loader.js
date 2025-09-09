/**
 * 组件加载器 - 用于动态加载HTML组件
 * 提供向后兼容的组件化解决方案
 */

class ComponentLoader {
    constructor() {
        this.loadedComponents = new Map();
        this.loadingPromises = new Map();
    }

    /**
     * 加载组件到指定容器
     * @param {string} componentPath - 组件路径，相对于 /static/components/
     * @param {string} targetSelector - 目标容器选择器
     * @param {boolean} replace - 是否替换容器内容（默认true）
     * @returns {Promise<void>}
     */
    async load(componentPath, targetSelector, replace = true) {
        try {
            // 如果已经在加载，返回现有的Promise
            const loadingKey = `${componentPath}:${targetSelector}`;
            if (this.loadingPromises.has(loadingKey)) {
                return this.loadingPromises.get(loadingKey);
            }

            const loadPromise = this._loadComponent(componentPath, targetSelector, replace);
            this.loadingPromises.set(loadingKey, loadPromise);

            await loadPromise;
            this.loadingPromises.delete(loadingKey);
        } catch (error) {
            console.error(`加载组件失败: ${componentPath}`, error);
            throw error;
        }
    }

    /**
     * 内部加载方法
     */
    async _loadComponent(componentPath, targetSelector, replace) {
        const target = document.querySelector(targetSelector);
        if (!target) {
            throw new Error(`找不到目标容器: ${targetSelector}`);
        }

        // 尝试从缓存获取
        let content = this.loadedComponents.get(componentPath);
        
        if (!content) {
            // 从服务器加载
            const response = await fetch(`/static/components/${componentPath}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            content = await response.text();
            this.loadedComponents.set(componentPath, content);
        }

        // 插入内容
        if (replace) {
            target.innerHTML = content;
        } else {
            target.insertAdjacentHTML('beforeend', content);
        }

        // 触发组件加载事件
        const event = new CustomEvent('componentLoaded', {
            detail: { componentPath, targetSelector, content }
        });
        document.dispatchEvent(event);
    }

    /**
     * 预加载组件
     * @param {string[]} componentPaths - 组件路径数组
     */
    async preload(componentPaths) {
        const promises = componentPaths.map(async (path) => {
            if (!this.loadedComponents.has(path)) {
                try {
                    const response = await fetch(`/static/components/${path}`);
                    if (response.ok) {
                        const content = await response.text();
                        this.loadedComponents.set(path, content);
                    }
                } catch (error) {
                    console.warn(`预加载组件失败: ${path}`, error);
                }
            }
        });

        await Promise.allSettled(promises);
    }

    /**
     * 清除缓存
     * @param {string} componentPath - 可选，清除特定组件缓存
     */
    clearCache(componentPath = null) {
        if (componentPath) {
            this.loadedComponents.delete(componentPath);
        } else {
            this.loadedComponents.clear();
        }
    }

    /**
     * 检查组件是否存在
     * @param {string} componentPath - 组件路径
     * @returns {Promise<boolean>}
     */
    async exists(componentPath) {
        try {
            const response = await fetch(`/static/components/${componentPath}`, { method: 'HEAD' });
            return response.ok;
        } catch (error) {
            return false;
        }
    }

    /**
     * 批量加载组件
     * @param {Array} components - 组件配置数组 [{path, target, replace}]
     */
    async loadBatch(components) {
        const promises = components.map(({ path, target, replace = true }) =>
            this.load(path, target, replace)
        );
        
        await Promise.allSettled(promises);
    }
}

// 创建全局实例
window.componentLoader = new ComponentLoader();

// 导出类供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ComponentLoader;
}