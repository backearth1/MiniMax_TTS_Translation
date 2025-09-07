# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based multi-speaker dubbing generation system that supports subtitle file parsing, character voice assignment, real-time TTS generation, and audio synthesis using the MiniMax API.

## Development Commands

### Start the Application
```bash
# Start the FastAPI server
python3 main.py

# The service will be available at:
# - Main interface: http://localhost:5215
# - API docs: http://localhost:5215/docs
# - Admin panel: http://localhost:5215/admin/dashboard
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Testing
```bash
# Manual testing by starting the service
python3 main.py

# Visit the interface and test:
# - Upload SRT subtitle files
# - Configure voice mapping
# - Generate dubbing
# - Download audio files
```

## Architecture Overview

### Core Components

- **main.py**: FastAPI application with WebSocket support for real-time logging
- **audio_processor.py**: Core audio processing and TTS generation using MiniMax API
- **subtitle_manager.py**: SRT subtitle parsing and management
- **admin.py**: Admin dashboard with system monitoring and user activity tracking
- **config.py**: Centralized configuration including API endpoints, TTS settings, and directory structure

### Key Modules

- **utils/logger.py**: WebSocket-based real-time logging system
- **static/**: Frontend files (HTML, CSS, JS) with modern responsive design
- **uploads/**: User-uploaded subtitle files (auto-created)
- **outputs/**: Generated audio files (auto-created)
- **audio_files/**: TTS audio segments cache (auto-created)
- **temp_audio/**: Temporary audio processing files (auto-created)

### API Configuration

The system uses configurable API endpoints for both domestic and overseas access:
- **TTS API**: MiniMax text-to-speech service
- **Translation API**: MiniMax text translation service
- Default endpoint type can be configured in `config.py`

### Voice Processing Pipeline

1. **Subtitle Upload**: Upload SRT files with automatic encoding detection (UTF-8/GBK)
2. **Character Assignment**: Map different characters to different AI voices
3. **Translation** (optional): Batch translate to target language
4. **TTS Generation**: Convert text to speech using MiniMax API
5. **Audio Assembly**: Merge audio segments with precise timestamp alignment
6. **Output**: Download final dubbed audio file

## Configuration

### MiniMax API Setup
- Group ID and API Key required for TTS services
- Support for 25+ languages including Chinese, English, Japanese, Korean, Arabic, etc.
- Multiple voice models available (speech-01, speech-02-hd)

### Voice Mapping
Configured in `config.py` with default speaker assignments:
```python
VOICE_MAPPING = {
    "SPEAKER_00": "ai_her_04",
    "SPEAKER_01": "wumei_yujie", 
    "SPEAKER_02": "uk_oldwoman4",
    # ... more mappings
}
```

### Directory Structure
All necessary directories are auto-created on startup via `ensure_directories()` function.

## Development Notes

### WebSocket Integration
- Real-time logging via WebSocket connections
- Progress tracking for long-running operations
- Client disconnect handling with automatic cleanup

### Audio Processing
- Uses pydub for audio manipulation
- FFmpeg integration for advanced audio processing
- Batch processing support for large subtitle files
- Automatic file cleanup after user disconnect

### Error Handling
- Comprehensive exception handling throughout the pipeline
- User-friendly error messages via WebSocket logs
- Automatic retry mechanisms for API calls

### Security Features
- File type and size validation
- User session isolation
- Automatic cleanup of temporary files
- Rate limiting via user count controls

## Dependencies

### Core Dependencies
- **FastAPI**: Web framework with async support
- **uvicorn**: ASGI server
- **aiohttp/requests**: HTTP client libraries
- **pydub**: Audio processing
- **psutil**: System monitoring
- **aiofiles**: Async file operations

### Optional Dependencies
- **FFmpeg**: Advanced audio processing (system dependency)
- **librosa**: Advanced audio analysis (commented in requirements.txt)
- **soundfile**: Audio file I/O (commented in requirements.txt)

### Development Tools
Testing is primarily manual through the web interface. For automated testing setup, refer to CONTRIBUTING.md which mentions pytest framework setup.