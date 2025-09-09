/**
 * 音频处理模块
 * 负责音频播放、合并、波形显示等功能
 */

class AudioProcessor {
    constructor() {
        this.currentAudio = null;
        this.waveformUpdateInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // 绑定音频下载按钮
        const downloadAudioBtn = document.getElementById('downloadAudioBtn');
        if (downloadAudioBtn) {
            downloadAudioBtn.addEventListener('click', () => this.downloadCurrentAudio());
        }
    }

    /**
     * 播放单个段落音频
     */
    playAudio(segmentId) {
        const segment = window.segments ? window.segments.find(s => s.id === segmentId) : null;
        if (!segment || !segment.audio_url) {
            if (window.showToast) window.showToast('该段落暂无音频');
            return;
        }

        // 停止当前播放的音频
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }

        try {
            this.currentAudio = new Audio(segment.audio_url);
            this.currentAudio.play();
            
            this.currentAudio.addEventListener('ended', () => {
                this.currentAudio = null;
            });
            
            this.currentAudio.addEventListener('error', (e) => {
                console.error('音频播放失败:', e);
                if (window.showToast) window.showToast('音频播放失败');
                this.currentAudio = null;
            });
            
            if (window.showToast) window.showToast('开始播放音频');
        } catch (error) {
            console.error('音频播放失败:', error);
            if (window.showToast) window.showToast('音频播放失败: ' + error.message);
        }
    }

    /**
     * 合并音频
     */
    async mergeAudio() {
        if (!window.currentSubtitleProject) {
            if (window.showToast) window.showToast('请先上传SRT文件');
            return;
        }

        if (window.addLog) window.addLog('开始合并音频...');
        if (window.showToast) window.showToast('正在合并音频，请稍候...');

        try {
            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/merge-audio`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();

            if (result.success) {
                if (window.addLog) {
                    window.addLog(`音频合并成功！文件大小: ${(result.file_size / 1024 / 1024).toFixed(2)} MB`);
                    window.addLog(`音频时长: ${result.duration} 秒`);
                }
                if (window.showToast) window.showToast('音频合并成功！');
                
                this.showMergeResult(result);
            } else {
                if (window.addLog) window.addLog(`音频合并失败: ${result.message}`);
                if (window.showToast) window.showToast('音频合并失败: ' + result.message);
            }
        } catch (error) {
            console.error('合并音频失败:', error);
            if (window.addLog) window.addLog(`合并音频失败: ${error.message}`);
            if (window.showToast) window.showToast('合并音频失败: ' + error.message);
        }
    }

    /**
     * 显示合并结果
     */
    showMergeResult(result) {
        const mergeResultCard = document.getElementById('mergeResultCard');
        const mergeDownloadBtn = document.getElementById('mergeDownloadBtn');
        const audioStatus = document.getElementById('audioStatus');
        const playBtn = document.getElementById('mergePlayBtn');
        const pauseBtn = document.getElementById('mergePauseBtn');
        
        // 检查必要的DOM元素是否存在
        if (!mergeResultCard) {
            console.error('mergeResultCard not found');
            return;
        }
        
        // 设置下载链接（如果元素存在）
        if (mergeDownloadBtn) {
            mergeDownloadBtn.href = result.audio_url;
            mergeDownloadBtn.download = result.filename || 'merged_audio.wav';
        }
        
        // 显示状态信息
        if (audioStatus) {
            const fileSize = result.file_size ? `${(result.file_size / 1024 / 1024).toFixed(2)} MB` : '未知大小';
            const duration = result.duration ? `${result.duration.toFixed(1)} 秒` : '未知时长';
            
            audioStatus.innerHTML = `
                <div class="alert alert-success small mb-2">
                    <i class="bi bi-check-circle me-2"></i>
                    合并完成！文件大小: ${fileSize}，时长: ${duration}
                </div>
            `;
        }
        
        // 显示整个结果卡片
        mergeResultCard.style.display = 'block';
        
        // 初始化音频播放器
        if (result.audio_url) {
            this.initAudioPlayer(result.audio_url);
        }
    }

    /**
     * 初始化音频播放器
     */
    initAudioPlayer(audioUrl) {
        const playBtn = document.getElementById('mergePlayBtn');
        const pauseBtn = document.getElementById('mergePauseBtn');
        const progressBar = document.getElementById('audioProgress');
        const currentTimeSpan = document.getElementById('currentTime');
        const totalTimeSpan = document.getElementById('totalTime');
        const waveformCanvas = document.getElementById('audioWaveform');
        
        // 检查必要的DOM元素是否存在
        if (!playBtn || !pauseBtn || !progressBar || !currentTimeSpan || !totalTimeSpan || !waveformCanvas) {
            console.error('Some audio player elements not found');
            return;
        }
        
        // 生成波形
        this.generateWaveform(audioUrl, waveformCanvas);
        
        // 停止之前的音频
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        
        // 创建新的音频对象
        this.currentAudio = new Audio(audioUrl);
        
        // 启用播放按钮
        playBtn.disabled = false;
        
        // 播放按钮点击事件
        playBtn.onclick = () => {
            this.currentAudio.play();
            playBtn.style.display = 'none';
            pauseBtn.style.display = 'inline-block';
            pauseBtn.disabled = false;
            this.startWaveformUpdate();
        };
        
        // 暂停按钮点击事件
        pauseBtn.onclick = () => {
            this.currentAudio.pause();
            pauseBtn.style.display = 'none';
            playBtn.style.display = 'inline-block';
            this.stopWaveformUpdate();
        };
        
        // 进度条拖拽事件
        progressBar.addEventListener('input', () => {
            const duration = this.currentAudio.duration;
            if (duration) {
                this.currentAudio.currentTime = (progressBar.value / 100) * duration;
            }
        });
        
        // 音频事件监听
        this.currentAudio.addEventListener('loadedmetadata', () => {
            totalTimeSpan.textContent = this.formatPlaybackTime(this.currentAudio.duration);
        });
        
        this.currentAudio.addEventListener('timeupdate', () => {
            if (this.currentAudio.duration) {
                const progress = (this.currentAudio.currentTime / this.currentAudio.duration) * 100;
                progressBar.value = progress;
                currentTimeSpan.textContent = this.formatPlaybackTime(this.currentAudio.currentTime);
            }
        });
        
        this.currentAudio.addEventListener('ended', () => {
            pauseBtn.style.display = 'none';
            playBtn.style.display = 'inline-block';
            progressBar.value = 0;
            currentTimeSpan.textContent = '00:00';
            this.stopWaveformUpdate();
        });
    }

    /**
     * 生成波形显示
     */
    generateWaveform(audioUrl, canvas) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        // 清除画布
        ctx.clearRect(0, 0, width, height);
        
        // 绘制简单的静态波形（模拟）
        ctx.strokeStyle = '#007bff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let x = 0; x < width; x++) {
            const y = height / 2 + Math.sin(x * 0.02) * (20 + Math.random() * 30);
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        // 添加中心线
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, height / 2);
        ctx.lineTo(width, height / 2);
        ctx.stroke();
    }

    /**
     * 开始波形更新
     */
    startWaveformUpdate() {
        if (this.waveformUpdateInterval) {
            clearInterval(this.waveformUpdateInterval);
        }
        
        this.waveformUpdateInterval = setInterval(() => {
            // 这里可以添加实时波形更新逻辑
        }, 100);
    }

    /**
     * 停止波形更新
     */
    stopWaveformUpdate() {
        if (this.waveformUpdateInterval) {
            clearInterval(this.waveformUpdateInterval);
            this.waveformUpdateInterval = null;
        }
    }

    /**
     * 格式化播放时间
     */
    formatPlaybackTime(seconds) {
        if (!seconds || isNaN(seconds)) return '00:00';
        
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * 初始化音频播放器状态
     */
    initAudioPlayerState() {
        const playBtn = document.getElementById('mergePlayBtn');
        const pauseBtn = document.getElementById('mergePauseBtn');
        const audioStatus = document.getElementById('audioStatus');
        const waveformCanvas = document.getElementById('audioWaveform');
        
        // 检查必要的DOM元素是否存在
        if (!playBtn || !pauseBtn || !audioStatus || !waveformCanvas) {
            console.error('Some audio player state elements not found');
            return;
        }
        
        // 确保播放器默认显示但禁用
        playBtn.disabled = true;
        pauseBtn.disabled = true;
        pauseBtn.style.display = 'none';
        
        // 显示默认状态
        audioStatus.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="bi bi-music-note fs-4"></i>
                <p class="mt-2 mb-0">请先合并音频</p>
            </div>
        `;
        
        // 清空波形画布
        const ctx = waveformCanvas.getContext('2d');
        ctx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
        
        // 绘制占位符
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, waveformCanvas.height / 2);
        ctx.lineTo(waveformCanvas.width, waveformCanvas.height / 2);
        ctx.stroke();
    }

    /**
     * 下载当前音频
     */
    downloadCurrentAudio() {
        const mergeDownloadBtn = document.getElementById('mergeDownloadBtn');
        if (mergeDownloadBtn && mergeDownloadBtn.href && mergeDownloadBtn.href !== '#') {
            mergeDownloadBtn.click();
        } else {
            if (window.showToast) window.showToast('暂无可下载的音频文件');
        }
    }

    /**
     * 清理音频资源
     */
    cleanup() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        this.stopWaveformUpdate();
    }
}

// 创建全局实例
const audioProcessor = new AudioProcessor();

// 导出供外部使用
window.audioProcessor = audioProcessor;

// 兼容性函数，保持向后兼容
window.playAudio = (segmentId) => audioProcessor.playAudio(segmentId);
window.mergeAudio = () => audioProcessor.mergeAudio();
window.showMergeResult = (result) => audioProcessor.showMergeResult(result);
window.initAudioPlayer = (audioUrl) => audioProcessor.initAudioPlayer(audioUrl);
window.initAudioPlayerState = () => audioProcessor.initAudioPlayerState();