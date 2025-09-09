/**
 * 字幕编辑器模块
 * 负责字幕段落的加载、渲染、CRUD操作
 */

class SubtitleEditor {
    constructor() {
        this.currentProject = null;
        this.currentPage = 1;
        this.segments = [];
        this.init();
    }

    init() {
        // 绑定事件监听器
        this.bindEvents();
    }

    bindEvents() {
        // 分页控制
        const prevPageBtn = document.getElementById('prevPage');
        const nextPageBtn = document.getElementById('nextPage');
        
        if (prevPageBtn) {
            prevPageBtn.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.loadSubtitleSegments();
                }
            });
        }
        
        if (nextPageBtn) {
            nextPageBtn.addEventListener('click', () => {
                this.currentPage++;
                this.loadSubtitleSegments();
            });
        }
    }

    /**
     * 设置当前项目
     */
    setCurrentProject(project) {
        this.currentProject = project;
        this.currentPage = 1;
    }

    /**
     * 加载字幕段落
     */
    async loadSubtitleSegments() {
        if (!this.currentProject) return;

        try {
            const response = await fetch(`/api/subtitle/${this.currentProject.id}/segments?page=${this.currentPage}&per_page=20`);
            const result = await response.json();

            if (result.success) {
                this.segments = result.segments;
                this.renderSubtitleSegments();
                this.updatePaginationInfo(result.pagination);
                
                // 显示翻译功能区域
                const translationSection = document.getElementById('translationSection');
                if (translationSection) {
                    translationSection.style.display = 'flex';
                }
                
                // 显示导出SRT按钮
                const exportSrtBtn = document.getElementById('exportSrtBtn');
                if (exportSrtBtn) {
                    exportSrtBtn.style.display = 'inline-block';
                }
                
                // 确保批量操作区域已初始化但隐藏
                const batchOperationSection = document.getElementById('batchOperationSection');
                if (batchOperationSection && this.segments.length > 0) {
                    this.updateSelectedCount();
                }
            }
        } catch (error) {
            console.error('加载段落失败:', error);
        }
    }

    /**
     * 更新分页信息
     */
    updatePaginationInfo(pagination) {
        if (!pagination) return;
        
        const pageInfo = document.getElementById('pageInfo');
        const paginationControls = document.getElementById('paginationControls');
        const prevPage = document.getElementById('prevPage');
        const nextPage = document.getElementById('nextPage');
        
        if (pageInfo) {
            pageInfo.textContent = `第 ${pagination.page} 页，共 ${pagination.pages} 页 (${pagination.total} 条，每页20条)`;
        }
        
        // 显示分页控制
        if (pagination.pages > 1) {
            paginationControls.style.display = 'flex';
            prevPage.disabled = pagination.page <= 1;
            nextPage.disabled = pagination.page >= pagination.pages;
        } else {
            paginationControls.style.display = 'none';
        }
    }

    /**
     * 渲染字幕段落
     */
    renderSubtitleSegments() {
        const container = document.getElementById('subtitleEditor');
        
        if (this.segments.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5" style="color: var(--pink-400);">
                    <i class="bi bi-file-earmark-text fs-1"></i>
                    <p class="mt-2">上传SRT文件开始编辑</p>
                </div>
            `;
            return;
        }

        const segmentsHtml = this.segments.map((segment, index) => `
            <div class="segment-item">
                <div class="d-flex flex-column">
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <input type="checkbox" class="form-check-input segment-checkbox" 
                               data-segment-id="${segment.id}" 
                               onchange="updateSelectedCount()"
                               style="margin-right: 8px;">
                        <span class="badge" style="background: var(--pink-400);">${segment.index}</span>
                        <small style="color: var(--pink-600);">${segment.start_time} → ${segment.end_time}</small>
                        <span class="speaker-simple">${segment.speaker}</span>
                        <span class="emotion-simple">${segment.emotion}</span>
                        <small style="color: var(--pink-600);">×${segment.speed}</small>
                        <div class="btn-group btn-group-sm ms-auto" role="group">
                            <button class="btn btn-outline-primary btn-sm" 
                                    onclick="generateTTS('${segment.id}')" 
                                    title="生成TTS"
                                    style="width: 70px; min-width: 70px; display: flex; align-items: center; justify-content: center; font-size: 0.6rem; white-space: nowrap;">
                                生成
                            </button>
                            <button class="btn btn-outline-success btn-sm" 
                                    onclick="playAudio('${segment.id}')" 
                                    ${segment.audio_url && segment.audio_url !== '' ? '' : 'disabled'}
                                    title="播放音频"
                                    style="width: 40px; display: flex; align-items: center; justify-content: center;">
                                <i class="bi bi-play-circle"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-info insert-segment-btn" 
                                    data-segment-id="${segment.id}"
                                    title="在此段落后插入新段落"
                                    style="width: 40px; display: flex; align-items: center; justify-content: center;">
                                <i class="bi bi-plus"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" 
                                    onclick="subtitleEditor.deleteSegment('${segment.id}')"
                                    title="删除段落"
                                    style="width: 40px; display: flex; align-items: center; justify-content: center;">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                    <div class="d-flex">
                        <div class="flex-grow-1">
                            <div class="mb-1">
                                <small style="color: var(--pink-700); font-weight: 500;">原文: ${segment.text}</small>
                            </div>
                            ${segment.translated_text ? 
                                `<div class="mb-1 d-flex align-items-center">
                                    <small style="color: var(--blue-600); font-weight: 500;" class="translation-text">译文: ${segment.translated_text}</small>
                                    <div class="text-adjustment-buttons d-inline-flex gap-1 ms-2">
                                        <button type="button" class="btn btn-outline-primary btn-sm text-adjust-btn" 
                                                data-segment-id="${segment.id}" 
                                                data-adjustment-type="shorten"
                                                title="缩短译文约20%"
                                                onclick="adjustSegmentText('${segment.id}', 'shorten')">
                                            <i class="bi bi-arrow-down-circle me-1"></i>缩短
                                        </button>
                                        <button type="button" class="btn btn-outline-success btn-sm text-adjust-btn"
                                                data-segment-id="${segment.id}"
                                                data-adjustment-type="lengthen"
                                                title="加长译文约20%"
                                                onclick="adjustSegmentText('${segment.id}', 'lengthen')">
                                            <i class="bi bi-arrow-up-circle me-1"></i>加长
                                        </button>
                                    </div>
                                </div>` : 
                                `<div class="mb-1 d-flex align-items-center">
                                    <small style="color: var(--gray-500); font-style: italic;">译文: 未翻译</small>
                                    <div class="text-adjustment-buttons d-inline-flex gap-1 ms-2">
                                        <button type="button" class="btn btn-outline-secondary btn-sm text-adjust-btn disabled"
                                                disabled
                                                title="请先翻译后再调整">
                                            <i class="bi bi-arrow-down-circle me-1"></i>缩短
                                        </button>
                                        <button type="button" class="btn btn-outline-secondary btn-sm text-adjust-btn disabled"
                                                disabled
                                                title="请先翻译后再调整">
                                            <i class="bi bi-arrow-up-circle me-1"></i>加长
                                        </button>
                                    </div>
                                </div>`
                            }
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = segmentsHtml;
        
        // 重新渲染后，确保内联编辑器重新初始化
        if (window.inlineEditor) {
            setTimeout(() => {
                console.log('🔧 手动重新初始化内联编辑器');
                window.inlineEditor.enhanceAllSegments();
            }, 50);
        }
    }

    /**
     * 添加新段落
     */
    async addNewSegment() {
        if (!this.currentProject) {
            if (window.showToast) showToast('请先上传SRT文件');
            return;
        }

        const startTime = prompt('请输入段落开始时间 (格式: 00:00:01,000):');
        if (!startTime) return;

        const endTime = prompt('请输入段落结束时间 (格式: 00:00:02,000):');
        if (!endTime) return;

        const text = prompt('请输入段落内容:');
        if (!text) return;

        const newSegment = {
            start_time: startTime,
            end_time: endTime,
            text: text,
            speaker: "SPEAKER_00",
            emotion: "auto",
            speed: 1.0
        };

        try {
            const response = await fetch(`/api/subtitle/${this.currentProject.id}/segments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newSegment)
            });

            const result = await response.json();
            if (result.success) {
                if (window.showToast) showToast('段落添加成功');
                await this.loadSubtitleSegments();
            } else {
                if (window.showToast) showToast('添加段落失败: ' + result.message);
            }
        } catch (error) {
            console.error('添加段落失败:', error);
            if (window.showToast) showToast('添加段落失败: ' + error.message);
        }
    }

    /**
     * 在指定段落后插入新段落
     */
    async insertAfterSegment(segmentId) {
        if (!this.currentProject) {
            if (window.showToast) showToast('请先上传SRT文件');
            return;
        }

        const text = prompt('请输入新段落内容:');
        if (!text) return;

        try {
            const response = await fetch(`/api/subtitle/${this.currentProject.id}/segments/${segmentId}/insert-after`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });

            const result = await response.json();
            if (result.success) {
                if (window.showToast) showToast('段落插入成功');
                await this.loadSubtitleSegments();
            } else {
                if (window.showToast) showToast('插入段落失败: ' + result.message);
            }
        } catch (error) {
            console.error('插入段落失败:', error);
            if (window.showToast) showToast('插入段落失败: ' + error.message);
        }
    }

    /**
     * 删除段落
     */
    async deleteSegment(segmentId) {
        if (!this.currentProject) {
            if (window.showToast) showToast('请先上传SRT文件');
            return;
        }

        if (!confirm('确定要删除这个段落吗？')) return;

        try {
            const response = await fetch(`/api/subtitle/${this.currentProject.id}/segments/${segmentId}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            if (result.success) {
                if (window.showToast) showToast('段落删除成功');
                await this.loadSubtitleSegments();
            } else {
                if (window.showToast) showToast('删除段落失败: ' + result.message);
            }
        } catch (error) {
            console.error('删除段落失败:', error);
            if (window.showToast) showToast('删除段落失败: ' + error.message);
        }
    }

    /**
     * 更新段落索引
     */
    updateSegmentIndexes() {
        this.segments.forEach((segment, index) => {
            segment.index = index + 1;
        });
    }

    /**
     * 更新选中数量
     */
    updateSelectedCount() {
        const checkboxes = document.querySelectorAll('.segment-checkbox:checked');
        const count = checkboxes.length;
        const selectedCountEl = document.getElementById('selectedCount');
        if (selectedCountEl) {
            selectedCountEl.textContent = `已选择: ${count}`;
        }
        
        // 更新批量操作按钮状态
        const batchUpdateBtn = document.getElementById('batchUpdateBtn');
        if (batchUpdateBtn) {
            batchUpdateBtn.disabled = count === 0;
        }
    }

    /**
     * 获取当前段落数据
     */
    getSegments() {
        return this.segments;
    }

    /**
     * 获取当前项目
     */
    getCurrentProject() {
        return this.currentProject;
    }
}

// 创建全局实例
const subtitleEditor = new SubtitleEditor();

// 导出供外部使用
window.subtitleEditor = subtitleEditor;