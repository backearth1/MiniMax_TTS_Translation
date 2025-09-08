/**
 * 内联编辑器模块
 * 为段落字幕提供双击内联编辑功能
 */

class InlineEditor {
    constructor() {
        this.isEnabled = true;
        this.currentEditingElement = null;
        this.originalValue = null;
        this.emotionOptions = [
            { value: 'auto', text: '自动检测' },
            { value: 'happy', text: '开心' },
            { value: 'sad', text: '悲伤' },
            { value: 'angry', text: '愤怒' },
            { value: 'fearful', text: '恐惧' },
            { value: 'disgusted', text: '厌恶' },
            { value: 'surprised', text: '惊讶' },
            { value: 'calm', text: '平静' }
        ];
        
        this.init();
    }

    init() {
        // 等待页面加载完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.enhance());
        } else {
            this.enhance();
        }

        // 监听段落列表更新
        this.observeSegmentUpdates();
    }

    /**
     * 增强现有页面元素，添加内联编辑功能
     */
    enhance() {
        // 等待segments数据加载
        const checkSegments = () => {
            if (typeof segments !== 'undefined' && segments.length > 0) {
                this.enhanceAllSegments();
            } else {
                setTimeout(checkSegments, 500);
            }
        };
        checkSegments();
    }

    /**
     * 监听段落列表的动态更新
     */
    observeSegmentUpdates() {
        const subtitleEditor = document.getElementById('subtitleEditor');
        if (!subtitleEditor) return;

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    // 延迟执行，确保DOM更新完成
                    setTimeout(() => this.enhanceAllSegments(), 100);
                }
            });
        });

        observer.observe(subtitleEditor, {
            childList: true,
            subtree: true
        });
    }

    /**
     * 为所有段落添加内联编辑功能
     */
    enhanceAllSegments() {
        const segmentItems = document.querySelectorAll('.segment-item');
        segmentItems.forEach(item => this.enhanceSegment(item));
    }

    /**
     * 为单个段落添加内联编辑功能
     */
    enhanceSegment(segmentElement) {
        // 避免重复增强
        if (segmentElement.dataset.inlineEditEnhanced) return;
        segmentElement.dataset.inlineEditEnhanced = 'true';

        // 增强时间字段
        this.enhanceTimeFields(segmentElement);
        
        // 增强角色字段
        this.enhanceSpeakerField(segmentElement);
        
        // 增强情绪字段
        this.enhanceEmotionField(segmentElement);
        
        // 增强语速字段
        this.enhanceSpeedField(segmentElement);
        
        // 增强文本字段
        this.enhanceTextFields(segmentElement);
    }

    /**
     * 增强时间字段（开始时间和结束时间）
     */
    enhanceTimeFields(segmentElement) {
        const timeElements = segmentElement.querySelectorAll('small[style*="color: var(--pink-600)"]');
        timeElements.forEach(timeEl => {
            const timeText = timeEl.textContent.trim();
            if (timeText.includes('→') && !timeEl.dataset.editableEnhanced) {
                timeEl.dataset.editableEnhanced = 'true';
                
                const [startTime, endTime] = timeText.split('→').map(t => t.trim());
                
                // 包装开始时间
                const startSpan = this.createEditableElement('time', startTime, 'start_time', segmentElement);
                
                // 包装结束时间
                const endSpan = this.createEditableElement('time', endTime, 'end_time', segmentElement);
                
                // 替换原内容但保持样式
                timeEl.innerHTML = '';
                timeEl.appendChild(startSpan);
                timeEl.appendChild(document.createTextNode(' → '));
                timeEl.appendChild(endSpan);
            }
        });
    }

    /**
     * 增强角色字段
     */
    enhanceSpeakerField(segmentElement) {
        const speakerEl = segmentElement.querySelector('.speaker-simple');
        if (speakerEl) {
            const speakerValue = speakerEl.textContent.trim();
            this.makeElementEditable(speakerEl, 'speaker', speakerValue, 'speaker', segmentElement);
        }
    }

    /**
     * 增强情绪字段
     */
    enhanceEmotionField(segmentElement) {
        const emotionEl = segmentElement.querySelector('.emotion-simple');
        if (emotionEl) {
            const emotionValue = emotionEl.textContent.trim();
            this.makeElementEditable(emotionEl, 'emotion', emotionValue, 'emotion', segmentElement);
        }
    }

    /**
     * 增强语速字段
     */
    enhanceSpeedField(segmentElement) {
        const speedElements = segmentElement.querySelectorAll('small[style*="color: var(--pink-600)"]');
        speedElements.forEach(speedEl => {
            const speedText = speedEl.textContent.trim();
            if (speedText.startsWith('×') && !speedEl.dataset.editableEnhanced) {
                speedEl.dataset.editableEnhanced = 'true';
                
                const speedValue = speedText.substring(1);
                const editableEl = this.createEditableElement('speed', speedValue, 'speed', segmentElement);
                speedEl.innerHTML = '×';
                speedEl.appendChild(editableEl);
            }
        });
    }

    /**
     * 增强文本字段（原文和译文）
     */
    enhanceTextFields(segmentElement) {
        // 原文
        const originalTextEl = segmentElement.querySelector('small[style*="color: var(--pink-700)"]');
        if (originalTextEl) {
            const fullText = originalTextEl.textContent.trim();
            const textContent = fullText.replace('原文: ', '');
            this.enhanceTextElement(originalTextEl, 'original-text', textContent, 'text', '原文: ', segmentElement);
        }

        // 译文
        const translatedTextEl = segmentElement.querySelector('small.translation-text');
        if (translatedTextEl) {
            const fullText = translatedTextEl.textContent.trim();
            const textContent = fullText.replace('译文: ', '');
            this.enhanceTextElement(translatedTextEl, 'translated-text', textContent, 'translated_text', '译文: ', segmentElement);
        }
    }

    /**
     * 增强文本元素
     */
    enhanceTextElement(element, type, value, field, prefix, segmentElement) {
        // 避免重复增强
        if (element.dataset.editableEnhanced) return;
        element.dataset.editableEnhanced = 'true';

        // 保存原始前缀
        element.dataset.textPrefix = prefix;
        
        // 创建可编辑的文本span
        const textSpan = document.createElement('span');
        textSpan.className = `editable-field editable-${type}`;
        textSpan.textContent = value;
        textSpan.setAttribute('data-field', field);
        textSpan.setAttribute('data-original-value', value);
        textSpan.setAttribute('tabindex', '0');
        textSpan.setAttribute('aria-label', `双击编辑${this.getFieldDisplayName(field)}`);

        // 添加编辑提示
        const hint = document.createElement('div');
        hint.className = 'edit-hint';
        hint.textContent = '双击编辑';
        textSpan.appendChild(hint);

        // 添加操作按钮组
        const actions = document.createElement('div');
        actions.className = 'inline-edit-actions';
        actions.innerHTML = `
            <button type="button" class="inline-edit-btn inline-edit-save" title="保存">✓</button>
            <button type="button" class="inline-edit-btn inline-edit-cancel" title="取消">✕</button>
        `;
        textSpan.appendChild(actions);

        // 重构元素内容
        element.innerHTML = prefix;
        element.appendChild(textSpan);

        // 绑定事件
        this.bindEditEvents(textSpan, type, segmentElement);
    }

    /**
     * 直接增强现有元素，使其可编辑
     */
    makeElementEditable(element, type, value, field, segmentElement) {
        // 避免重复增强
        if (element.dataset.editableEnhanced) return;
        element.dataset.editableEnhanced = 'true';

        // 添加可编辑样式类
        element.classList.add('editable-field', `editable-${type}`);
        element.setAttribute('data-field', field);
        element.setAttribute('data-original-value', value);
        element.setAttribute('tabindex', '0');
        element.setAttribute('aria-label', `双击编辑${this.getFieldDisplayName(field)}`);

        // 添加编辑提示
        const hint = document.createElement('div');
        hint.className = 'edit-hint';
        hint.textContent = '双击编辑';
        element.appendChild(hint);

        // 添加操作按钮组
        const actions = document.createElement('div');
        actions.className = 'inline-edit-actions';
        actions.innerHTML = `
            <button type="button" class="inline-edit-btn inline-edit-save" title="保存">✓</button>
            <button type="button" class="inline-edit-btn inline-edit-cancel" title="取消">✕</button>
        `;
        element.appendChild(actions);

        // 绑定事件
        this.bindEditEvents(element, type, segmentElement);

        return element;
    }

    /**
     * 创建可编辑元素（用于时间和文本字段）
     */
    createEditableElement(type, value, field, segmentElement) {
        const span = document.createElement('span');
        span.className = `editable-field editable-${type}`;
        span.textContent = value;
        span.setAttribute('data-field', field);
        span.setAttribute('data-original-value', value);
        span.setAttribute('tabindex', '0');
        span.setAttribute('aria-label', `双击编辑${this.getFieldDisplayName(field)}`);

        // 添加编辑提示
        const hint = document.createElement('div');
        hint.className = 'edit-hint';
        hint.textContent = '双击编辑';
        span.appendChild(hint);

        // 添加操作按钮组
        const actions = document.createElement('div');
        actions.className = 'inline-edit-actions';
        actions.innerHTML = `
            <button type="button" class="inline-edit-btn inline-edit-save" title="保存">✓</button>
            <button type="button" class="inline-edit-btn inline-edit-cancel" title="取消">✕</button>
        `;
        span.appendChild(actions);

        // 绑定事件
        this.bindEditEvents(span, type, segmentElement);

        return span;
    }

    /**
     * 绑定编辑事件
     */
    bindEditEvents(element, type, segmentElement) {
        // 双击进入编辑
        element.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            this.startEdit(element, type, segmentElement);
        });

        // 键盘快捷键
        element.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.startEdit(element, type, segmentElement);
            }
        });

        // 绑定操作按钮
        const saveBtn = element.querySelector('.inline-edit-save');
        const cancelBtn = element.querySelector('.inline-edit-cancel');

        saveBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.saveEdit(element, segmentElement);
        });

        cancelBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.cancelEdit(element);
        });
    }

    /**
     * 开始编辑
     */
    startEdit(element, type, segmentElement) {
        // 如果已有其他元素在编辑，先保存
        if (this.currentEditingElement && this.currentEditingElement !== element) {
            this.saveEdit(this.currentEditingElement);
        }

        this.currentEditingElement = element;
        this.originalValue = element.dataset.originalValue;

        element.classList.add('editing');
        
        // 根据类型创建编辑控件
        const editControl = this.createEditControl(type, this.originalValue);
        
        // 隐藏原始文本内容
        this.hideOriginalContent(element);
        
        // 插入编辑控件到元素开头
        element.insertBefore(editControl, element.firstChild);

        // 聚焦并选中内容
        setTimeout(() => {
            if (editControl.tagName === 'INPUT' || editControl.tagName === 'TEXTAREA') {
                editControl.focus();
                editControl.select();
            } else if (editControl.tagName === 'SELECT') {
                editControl.focus();
            }
        }, 50);

        // 绑定编辑控件事件
        this.bindEditControlEvents(editControl, element, segmentElement);
    }

    /**
     * 创建编辑控件
     */
    createEditControl(type, value) {
        switch (type) {
            case 'time':
                const timeInput = document.createElement('input');
                timeInput.type = 'text';
                timeInput.className = 'inline-edit-input';
                timeInput.value = value;
                timeInput.placeholder = '00:00:00,000';
                return timeInput;

            case 'speaker':
                const speakerInput = document.createElement('input');
                speakerInput.type = 'text';
                speakerInput.className = 'inline-edit-input';
                speakerInput.value = value;
                return speakerInput;

            case 'emotion':
                const emotionSelect = document.createElement('select');
                emotionSelect.className = 'inline-edit-select';
                this.emotionOptions.forEach(option => {
                    const optionEl = document.createElement('option');
                    optionEl.value = option.value;
                    optionEl.textContent = option.text;
                    optionEl.selected = option.value === value || option.text === value;
                    emotionSelect.appendChild(optionEl);
                });
                return emotionSelect;

            case 'speed':
                const speedInput = document.createElement('input');
                speedInput.type = 'number';
                speedInput.className = 'inline-edit-input';
                speedInput.value = value;
                speedInput.min = '1';
                speedInput.max = '2';
                speedInput.step = '0.1';
                return speedInput;

            case 'original-text':
            case 'translated-text':
                const textarea = document.createElement('textarea');
                textarea.className = 'inline-edit-textarea';
                textarea.value = value;
                textarea.rows = Math.min(Math.max(2, Math.ceil(value.length / 50)), 6);
                return textarea;

            default:
                const defaultInput = document.createElement('input');
                defaultInput.type = 'text';
                defaultInput.className = 'inline-edit-input';
                defaultInput.value = value;
                return defaultInput;
        }
    }

    /**
     * 绑定编辑控件事件
     */
    bindEditControlEvents(control, element, segmentElement) {
        // Enter保存，Esc取消
        control.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.saveEdit(element, segmentElement);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.cancelEdit(element);
            }
        });

        // 点击外部保存
        const clickOutside = (e) => {
            if (!element.contains(e.target)) {
                this.saveEdit(element, segmentElement);
                document.removeEventListener('click', clickOutside);
            }
        };
        setTimeout(() => document.addEventListener('click', clickOutside), 100);
    }

    /**
     * 保存编辑
     */
    async saveEdit(element, segmentElement) {
        if (!element.classList.contains('editing')) return;

        const control = element.querySelector('.inline-edit-input, .inline-edit-select, .inline-edit-textarea');
        if (!control) return;

        const newValue = control.value.trim();
        const field = element.dataset.field;
        const segmentId = this.getSegmentId(segmentElement);

        // 验证输入
        if (!this.validateInput(field, newValue)) {
            return;
        }

        // 如果值没有变化，直接取消编辑
        if (newValue === this.originalValue) {
            this.cancelEdit(element);
            return;
        }

        // 显示加载状态
        element.classList.add('inline-edit-loading');

        try {
            // 调用API更新
            const success = await this.updateSegment(segmentId, field, newValue);
            
            if (success) {
                // 更新显示值
                this.updateDisplayValue(element, field, newValue);
                
                // 成功动画
                element.classList.add('save-success');
                setTimeout(() => element.classList.remove('save-success'), 800);
                
                // 更新本地数据
                this.updateLocalSegmentData(segmentId, field, newValue);
                
                this.showToast('保存成功', 'success');
            } else {
                throw new Error('保存失败');
            }
        } catch (error) {
            console.error('保存失败:', error);
            this.showToast('保存失败: ' + error.message, 'error');
        } finally {
            element.classList.remove('inline-edit-loading');
            this.exitEdit(element);
        }
    }

    /**
     * 取消编辑
     */
    cancelEdit(element) {
        this.exitEdit(element);
    }

    /**
     * 隐藏原始内容
     */
    hideOriginalContent(element) {
        // 简单方法：给元素添加一个标记类，用CSS隐藏原始内容
        element.classList.add('editing-content-hidden');
    }

    /**
     * 显示原始内容
     */
    showOriginalContent(element) {
        // 移除隐藏标记类，恢复原始内容显示
        element.classList.remove('editing-content-hidden');
    }

    /**
     * 退出编辑状态
     */
    exitEdit(element) {
        // 移除所有编辑控件
        const controls = element.querySelectorAll('.inline-edit-input, .inline-edit-select, .inline-edit-textarea');
        controls.forEach(control => control.remove());

        // 恢复原始内容显示
        this.showOriginalContent(element);

        element.classList.remove('editing');
        this.currentEditingElement = null;
    }

    /**
     * 更新段落数据
     */
    async updateSegment(segmentId, field, value) {
        try {
            const updates = { [field]: field === 'speed' ? parseFloat(value) : value };
            
            const response = await fetch(`/api/subtitle/${currentSubtitleProject.id}/segment/${segmentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updates)
            });

            return response.ok;
        } catch (error) {
            console.error('API调用失败:', error);
            return false;
        }
    }

    /**
     * 更新显示值
     */
    updateDisplayValue(element, field, newValue) {
        // 更新数据属性
        element.dataset.originalValue = newValue;
        
        // 根据字段类型更新显示文本
        if (field === 'emotion') {
            // 情绪字段保持英文显示
            this.updateElementText(element, newValue);
        } else if (field === 'text' || field === 'translated_text') {
            // 文本字段，找到可编辑的子span
            const editableSpan = element.querySelector('.editable-field');
            if (editableSpan) {
                this.updateElementText(editableSpan, newValue);
                editableSpan.dataset.originalValue = newValue;
            } else {
                this.updateElementText(element, newValue);
            }
        } else {
            // 其他字段直接更新
            this.updateElementText(element, newValue);
        }
    }

    /**
     * 更新元素的文本内容
     */
    updateElementText(element, newText) {
        // 找到第一个文本节点并更新
        for (let i = 0; i < element.childNodes.length; i++) {
            const node = element.childNodes[i];
            if (node.nodeType === Node.TEXT_NODE) {
                node.textContent = newText;
                return;
            }
        }
        // 如果没有文本节点，创建一个
        const textNode = document.createTextNode(newText);
        element.insertBefore(textNode, element.firstChild);
    }

    /**
     * 更新本地段落数据
     */
    updateLocalSegmentData(segmentId, field, value) {
        if (typeof segments !== 'undefined') {
            const segment = segments.find(s => s.id === segmentId);
            if (segment) {
                segment[field] = field === 'speed' ? parseFloat(value) : value;
            }
        }
    }

    /**
     * 获取段落ID
     */
    getSegmentId(segmentElement) {
        const checkbox = segmentElement.querySelector('.segment-checkbox');
        return checkbox ? checkbox.dataset.segmentId : null;
    }

    /**
     * 验证输入
     */
    validateInput(field, value) {
        switch (field) {
            case 'start_time':
            case 'end_time':
                const timeRegex = /^\d{2}:\d{2}:\d{2},\d{3}$/;
                if (!timeRegex.test(value)) {
                    this.showToast('时间格式不正确，应为 HH:MM:SS,mmm', 'error');
                    return false;
                }
                break;

            case 'speed':
                const speed = parseFloat(value);
                if (isNaN(speed) || speed < 1 || speed > 2) {
                    this.showToast('语速应在1.0-2.0之间', 'error');
                    return false;
                }
                break;

            case 'speaker':
            case 'text':
            case 'translated_text':
                if (!value) {
                    this.showToast('内容不能为空', 'error');
                    return false;
                }
                break;
        }
        return true;
    }

    /**
     * 获取字段显示名称
     */
    getFieldDisplayName(field) {
        const names = {
            'start_time': '开始时间',
            'end_time': '结束时间',
            'speaker': '角色',
            'emotion': '情绪',
            'speed': '语速',
            'text': '原文',
            'translated_text': '译文'
        };
        return names[field] || field;
    }

    /**
     * 显示提示消息
     */
    showToast(message, type = 'info') {
        // 使用现有的showToast函数
        if (typeof showToast === 'function') {
            showToast(message);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }

    /**
     * 启用/禁用内联编辑
     */
    toggle(enabled) {
        this.isEnabled = enabled;
        const editableElements = document.querySelectorAll('.editable-field');
        editableElements.forEach(el => {
            el.style.pointerEvents = enabled ? '' : 'none';
            el.style.opacity = enabled ? '' : '0.6';
        });
    }
}

// 创建全局实例
let inlineEditor;

// 页面加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        inlineEditor = new InlineEditor();
    });
} else {
    inlineEditor = new InlineEditor();
}

// 导出给外部使用
window.InlineEditor = InlineEditor;
window.inlineEditor = inlineEditor;