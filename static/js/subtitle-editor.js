/**
 * 字幕编辑器 JavaScript 逻辑
 * 处理文件上传、项目管理、段落编辑等功能
 */

class SubtitleEditor {
    constructor() {
        this.currentProject = null;
        this.currentPage = 1;
        this.perPage = 20;
        this.editingSegment = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadProjects();
        
        // 检查URL参数中是否有项目ID
        const urlParams = new URLSearchParams(window.location.search);
        const projectId = urlParams.get('project');
        if (projectId) {
            // 延迟一下确保项目列表已加载
            setTimeout(() => {
                this.selectProject(projectId);
                this.updateStatus('从主页跳转，自动加载项目', 'success');
            }, 500);
        }
    }
    
    bindEvents() {
        // 文件上传相关
        const fileDropZone = document.getElementById('fileDropZone');
        const fileInput = document.getElementById('fileInput');
        
        fileDropZone.addEventListener('click', () => fileInput.click());
        fileDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileDropZone.classList.add('dragover');
        });
        fileDropZone.addEventListener('dragleave', () => {
            fileDropZone.classList.remove('dragover');
        });
        fileDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            fileDropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileUpload(files[0]);
            }
        });
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileUpload(e.target.files[0]);
            }
        });
        
        // 项目管理
        document.getElementById('refreshProjects').addEventListener('click', () => {
            this.loadProjects();
        });
        
        // 编辑器操作
        document.getElementById('addSegment').addEventListener('click', () => {
            this.showSegmentModal();
        });
        
        document.getElementById('saveProject').addEventListener('click', () => {
            this.saveCurrentProject();
        });
        
        document.getElementById('deleteProject').addEventListener('click', () => {
            this.deleteCurrentProject();
        });
        
        // 模态框操作
        document.getElementById('saveSegment').addEventListener('click', () => {
            this.saveSegment();
        });
    }
    
    async handleFileUpload(file) {
        if (!file.name.toLowerCase().endsWith('.srt')) {
            this.showStatus('error', '请选择SRT格式的字幕文件');
            return;
        }
        
        this.showStatus('info', '正在解析字幕文件...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/parse-subtitle', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showStatus('success', result.message);
                this.loadProjects();
                // 自动加载新创建的项目
                setTimeout(() => {
                    this.loadProject(result.project.id);
                }, 500);
            } else {
                this.showStatus('error', result.detail || '解析失败');
            }
        } catch (error) {
            this.showStatus('error', `上传失败: ${error.message}`);
        }
    }
    
    async loadProjects() {
        try {
            const response = await fetch('/api/projects');
            const result = await response.json();
            
            if (result.success) {
                this.renderProjectList(result.projects);
            }
        } catch (error) {
            console.error('加载项目列表失败:', error);
        }
    }
    
    renderProjectList(projects) {
        const projectList = document.getElementById('projectList');
        
        if (projects.length === 0) {
            projectList.innerHTML = '<div class="text-center p-3 text-muted">暂无项目</div>';
            return;
        }
        
        projectList.innerHTML = projects.map(project => `
            <div class="project-item" data-project-id="${project.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${project.filename}</h6>
                        <small class="text-muted">${project.total_segments} 个段落</small>
                    </div>
                    <div class="text-end">
                        <small class="text-muted">${this.formatDate(project.created_at)}</small>
                        <button class="btn btn-sm btn-outline-danger ms-2" 
                                onclick="event.stopPropagation(); editor.deleteProject('${project.id}')">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // 绑定项目点击事件
        projectList.querySelectorAll('.project-item').forEach(item => {
            item.addEventListener('click', () => {
                const projectId = item.dataset.projectId;
                this.loadProject(projectId);
            });
        });
    }
    
    async loadProject(projectId) {
        this.showStatus('info', '加载项目中...');
        
        try {
            const response = await fetch(`/api/subtitle/${projectId}/segments?page=${this.currentPage}&per_page=${this.perPage}`);
            const result = await response.json();
            
            if (result.success) {
                this.currentProject = {
                    id: projectId,
                    info: result.project_info,
                    segments: result.segments,
                    pagination: result.pagination
                };
                
                this.renderEditor();
                this.showStatus('success', '项目加载成功');
            } else {
                this.showStatus('error', '加载项目失败');
            }
        } catch (error) {
            this.showStatus('error', `加载失败: ${error.message}`);
        }
    }
    
    renderEditor() {
        if (!this.currentProject) return;
        
        // 更新标题
        document.getElementById('editorTitle').innerHTML = `
            <i class="bi bi-pencil-square"></i> ${this.currentProject.info.filename}
        `;
        
        // 显示操作按钮
        document.getElementById('editorActions').style.display = 'block';
        
        // 渲染段落列表
        this.renderSegments();
    }
    
    renderSegments() {
        const editorContent = document.getElementById('editorContent');
        const { segments, pagination } = this.currentProject;
        
        if (segments.length === 0) {
            editorContent.innerHTML = `
                <div class="text-center p-5 text-muted">
                    <i class="bi bi-plus-circle fs-1"></i>
                    <p class="mt-2">暂无段落，点击"添加段落"开始编辑</p>
                </div>
            `;
            return;
        }
        
        const segmentsHtml = segments.map(segment => this.renderSegmentItem(segment)).join('');
        const paginationHtml = this.renderPagination(pagination);
        
        editorContent.innerHTML = `
            <div class="segments-list">
                ${segmentsHtml}
            </div>
            ${paginationHtml}
        `;
        
        // 绑定段落操作事件
        this.bindSegmentEvents();
    }
    
    renderSegmentItem(segment) {
        const emotionColor = this.getEmotionColor(segment.emotion);
        const durationMs = this.calculateDuration(segment.start_time, segment.end_time);
        
        return `
            <div class="segment-item" data-segment-id="${segment.id}">
                <div class="segment-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-primary">#${segment.index}</span>
                            <span class="text-muted">${segment.start_time} → ${segment.end_time}</span>
                            <span class="duration-simple">${durationMs}ms</span>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <span class="emotion-badge-simple">${this.getEmotionLabel(segment.emotion)}</span>
                            <span class="speed-badge">×${segment.speed}</span>
                            ${segment.has_audio ? '<i class="bi bi-volume-up text-success" title="已有音频"></i>' : '<i class="bi bi-volume-mute text-muted" title="无音频"></i>'}
                        </div>
                    </div>
                </div>
                <div class="segment-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="mb-2">
                                <strong>${segment.speaker}:</strong>
                                <span class="ms-2">${segment.text}</span>
                            </div>
                            ${segment.has_audio ? `<audio class="audio-player" controls><source src="/api/audio/${segment.id}" type="audio/mpeg"></audio>` : ''}
                        </div>
                        <div class="btn-group ms-3">
                            <button class="btn btn-sm btn-link text-muted edit-segment" 
                                    data-segment-id="${segment.id}">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-link text-danger delete-segment" 
                                    data-segment-id="${segment.id}">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    renderPagination(pagination) {
        if (pagination.pages <= 1) return '';
        
        const pages = [];
        const current = pagination.page;
        const total = pagination.pages;
        
        // 生成页码
        for (let i = Math.max(1, current - 2); i <= Math.min(total, current + 2); i++) {
            pages.push(i);
        }
        
        const pagesHtml = pages.map(page => `
            <button class="btn ${page === current ? 'btn-primary' : 'btn-outline-primary'} btn-sm"
                    onclick="editor.goToPage(${page})" ${page === current ? 'disabled' : ''}>
                ${page}
            </button>
        `).join('');
        
        return `
            <div class="pagination-wrapper">
                <button class="btn btn-outline-secondary btn-sm" 
                        onclick="editor.goToPage(${current - 1})" 
                        ${current <= 1 ? 'disabled' : ''}>
                    <i class="bi bi-chevron-left"></i> 上一页
                </button>
                
                <div class="btn-group">
                    ${pagesHtml}
                </div>
                
                <button class="btn btn-outline-secondary btn-sm" 
                        onclick="editor.goToPage(${current + 1})" 
                        ${current >= total ? 'disabled' : ''}>
                    下一页 <i class="bi bi-chevron-right"></i>
                </button>
                
                <small class="text-muted ms-3">
                    第 ${current} 页，共 ${total} 页 (${pagination.total} 条)
                </small>
            </div>
        `;
    }
    
    bindSegmentEvents() {
        // 编辑段落
        document.querySelectorAll('.edit-segment').forEach(btn => {
            btn.addEventListener('click', () => {
                const segmentId = btn.dataset.segmentId;
                const segment = this.currentProject.segments.find(s => s.id === segmentId);
                this.showSegmentModal(segment);
            });
        });
        
        // 删除段落
        document.querySelectorAll('.delete-segment').forEach(btn => {
            btn.addEventListener('click', () => {
                const segmentId = btn.dataset.segmentId;
                this.deleteSegment(segmentId);
            });
        });
    }
    
    showSegmentModal(segment = null) {
        this.editingSegment = segment;
        const modal = new bootstrap.Modal(document.getElementById('segmentModal'));
        
        if (segment) {
            // 编辑模式
            document.getElementById('startTime').value = segment.start_time;
            document.getElementById('endTime').value = segment.end_time;
            document.getElementById('speaker').value = segment.speaker;
            document.getElementById('textContent').value = segment.text;
            document.getElementById('emotion').value = segment.emotion;
            document.getElementById('speed').value = segment.speed;
            document.querySelector('#segmentModal .modal-title').textContent = `编辑段落 #${segment.index}`;
        } else {
            // 新增模式
            document.getElementById('segmentForm').reset();
            document.getElementById('speed').value = '1.0';
            document.querySelector('#segmentModal .modal-title').textContent = '添加新段落';
        }
        
        modal.show();
    }
    
    async saveSegment() {
        const formData = {
            start_time: document.getElementById('startTime').value,
            end_time: document.getElementById('endTime').value,
            speaker: document.getElementById('speaker').value,
            text: document.getElementById('textContent').value,
            emotion: document.getElementById('emotion').value,
            speed: parseFloat(document.getElementById('speed').value)
        };
        
        // 验证必填字段
        if (!formData.start_time || !formData.end_time || !formData.speaker || !formData.text) {
            this.showStatus('error', '请填写所有必填字段');
            return;
        }
        
        try {
            let response;
            if (this.editingSegment) {
                // 更新段落
                response = await fetch(`/api/subtitle/${this.currentProject.id}/segment/${this.editingSegment.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
            } else {
                // 添加段落
                response = await fetch(`/api/subtitle/${this.currentProject.id}/segment`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.showStatus('success', result.message);
                bootstrap.Modal.getInstance(document.getElementById('segmentModal')).hide();
                this.loadProject(this.currentProject.id); // 重新加载
            } else {
                this.showStatus('error', result.detail || '操作失败');
            }
        } catch (error) {
            this.showStatus('error', `操作失败: ${error.message}`);
        }
    }
    
    async deleteSegment(segmentId) {
        if (!confirm('确定要删除这个段落吗？')) return;
        
        try {
            const response = await fetch(`/api/subtitle/${this.currentProject.id}/segment/${segmentId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showStatus('success', '段落删除成功');
                this.loadProject(this.currentProject.id); // 重新加载
            } else {
                this.showStatus('error', result.detail || '删除失败');
            }
        } catch (error) {
            this.showStatus('error', `删除失败: ${error.message}`);
        }
    }
    
    async deleteProject(projectId) {
        if (!confirm('确定要删除整个项目吗？此操作不可恢复！')) return;
        
        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showStatus('success', '项目删除成功');
                this.loadProjects();
                
                // 如果删除的是当前项目，清空编辑器
                if (this.currentProject && this.currentProject.id === projectId) {
                    this.currentProject = null;
                    this.renderEmptyEditor();
                }
            } else {
                this.showStatus('error', result.detail || '删除失败');
            }
        } catch (error) {
            this.showStatus('error', `删除失败: ${error.message}`);
        }
    }
    
    async deleteCurrentProject() {
        if (this.currentProject) {
            this.deleteProject(this.currentProject.id);
        }
    }
    
    async saveCurrentProject() {
        this.showStatus('success', '项目已自动保存');
    }
    
    async goToPage(page) {
        if (!this.currentProject) return;
        
        this.currentPage = page;
        await this.loadProject(this.currentProject.id);
    }
    
    renderEmptyEditor() {
        document.getElementById('editorTitle').innerHTML = `
            <i class="bi bi-pencil-square"></i> 选择项目开始编辑
        `;
        document.getElementById('editorActions').style.display = 'none';
        document.getElementById('editorContent').innerHTML = `
            <div class="text-center p-5 text-muted">
                <i class="bi bi-arrow-left fs-1"></i>
                <p class="mt-2">请从左侧选择或上传字幕文件</p>
            </div>
        `;
    }
    
    // 工具函数
    showStatus(type, message) {
        const statusAlert = document.getElementById('statusAlert');
        const statusMessage = document.getElementById('statusMessage');
        
        statusAlert.className = `alert alert-${type === 'error' ? 'danger' : type}`;
        statusMessage.textContent = message;
        statusAlert.classList.remove('d-none');
        
        // 3秒后自动隐藏
        setTimeout(() => {
            statusAlert.classList.add('d-none');
        }, 3000);
    }
    
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('zh-CN') + ' ' + date.toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    getEmotionColor(emotion) {
        const colors = {
            'auto': 'bg-secondary',
            'happy': 'bg-warning',
            'sad': 'bg-info',
            'angry': 'bg-danger',
            'fearful': 'bg-dark',
            'disgusted': 'bg-success',
            'surprised': 'bg-primary',
            'calm': 'bg-light text-dark'
        };
        return colors[emotion] || 'bg-secondary';
    }
    
    getEmotionLabel(emotion) {
        const labels = {
            'auto': '自动',
            'happy': '开心',
            'sad': '悲伤',
            'angry': '愤怒',
            'fearful': '恐惧',
            'disgusted': '厌恶',
            'surprised': '惊讶',
            'calm': '平静'
        };
        return labels[emotion] || '未知';
    }
    
    calculateDuration(startTime, endTime) {
        const parseTime = (timeStr) => {
            const [time, ms] = timeStr.split(',');
            const [h, m, s] = time.split(':').map(Number);
            return (h * 3600 + m * 60 + s) * 1000 + Number(ms);
        };
        
        return parseTime(endTime) - parseTime(startTime);
    }
}

// 初始化编辑器
const editor = new SubtitleEditor(); 