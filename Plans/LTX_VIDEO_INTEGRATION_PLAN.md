# LTX Video Integration Plan for ImageAI

**Version**: 1.0  
**Date**: December 2025  
**Status**: Planning Phase  
**Priority**: High

---

## Executive Summary

This plan outlines the integration of LTX Video (Lightricks' text-to-video AI model) into ImageAI, providing both **local inference** via Hugging Face Diffusers and **cloud API access** via Fal.ai/Replicate. This dual approach maximizes flexibility—power users can run locally on capable hardware while others can use affordable cloud APIs.

LTX Video is the first DiT-based video generation model offering real-time generation capabilities, making it an excellent fit for ImageAI's multi-provider architecture.

---

## Table of Contents

1. [Model Overview](#1-model-overview)
2. [Architecture Design](#2-architecture-design)
3. [Phase 1: Core Provider Implementation](#phase-1-core-provider-implementation)
4. [Phase 2: Local Inference Pipeline](#phase-2-local-inference-pipeline)
5. [Phase 3: API Provider Integration](#phase-3-api-provider-integration)
6. [Phase 4: UI Integration](#phase-4-ui-integration)
7. [Phase 5: Advanced Features](#phase-5-advanced-features)
8. [Hardware Requirements](#hardware-requirements)
9. [Dependencies](#dependencies)
10. [Testing Strategy](#testing-strategy)
11. [Risk Assessment](#risk-assessment)

---

## 1. Model Overview

### Available Models

| Model | Parameters | Speed | Quality | VRAM Required | Use Case |
|-------|------------|-------|---------|---------------|----------|
| LTXV-2B-Distilled | 2B | Fastest (8 steps) | Good | ~8GB | Rapid iteration |
| LTXV-2B-0.9.7 | 2B | Fast (20-30 steps) | Better | ~10GB | Standard use |
| LTXV-13B | 13B | Slower (30-40 steps) | Best | ~24GB | High quality |
| LTXV-13B-Distilled | 13B | Fast (8 steps) | Very Good | ~20GB | Quality + speed |
| **LTX-2** (coming) | TBD | Fast | Professional | TBD | Audio+Video sync |

### Key Capabilities

- **Text-to-Video**: Generate video from text prompts
- **Image-to-Video**: Animate a single image
- **Video Extension**: Extend existing videos (forward/backward)
- **Multi-Keyframe Conditioning**: Interpolate between keyframes
- **Video-to-Video**: Transform existing video content
- **LoRA Support**: Custom fine-tuned models
- **Control Models**: Depth, pose, canny edge control

### Technical Specifications

- **Resolution**: Up to 720p (1280×720), 4K with LTX-2
- **Frame Rate**: 24-30 FPS (up to 50 FPS with LTX-2)
- **Duration**: 3-10 seconds per clip, up to 60 seconds with LTXV-13B
- **Real-time Generation**: ~10 seconds for HD video on H100

---

## 2. Architecture Design

### Provider Abstraction

Following ImageAI's existing `BaseProvider` pattern:

```
providers/
├── base.py                    # Existing base provider interface
├── ltx_video/
│   ├── __init__.py
│   ├── base_ltx.py           # LTX-specific base class
│   ├── local_ltx.py          # Local Diffusers implementation
│   ├── fal_ltx.py            # Fal.ai API implementation
│   ├── replicate_ltx.py      # Replicate API implementation
│   └── models.py             # Pydantic models for LTX config
```

### Integration Points

```
┌─────────────────────────────────────────────────────────────┐
│                        ImageAI GUI                          │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────────┐  │
│  │ Image Tab  │  │ Video Tab  │  │  LTX Video Controls   │  │
│  └────────────┘  └─────┬──────┘  └───────────┬───────────┘  │
└────────────────────────┼────────────────────┼───────────────┘
                         │                    │
┌────────────────────────▼────────────────────▼───────────────┐
│                   Video Generation Core                      │
│  ┌──────────────────┐  ┌──────────────────────────────────┐  │
│  │ LLM Integration  │  │      LTX Video Provider          │  │
│  │ (prompt enhance) │  │  ┌───────┐ ┌─────┐ ┌──────────┐  │  │
│  └──────────────────┘  │  │ Local │ │ Fal │ │ Replicate│  │  │
│                        │  └───┬───┘ └──┬──┘ └────┬─────┘  │  │
└────────────────────────┴─────┼────────┼─────────┼─────────┘
                               │        │         │
                    ┌──────────▼────────▼─────────▼──────────┐
                    │         Output Processing               │
                    │  ┌─────────────┐  ┌──────────────────┐  │
                    │  │   FFmpeg    │  │  Metadata/Sidecar│  │
                    │  │  Pipeline   │  │    Generation    │  │
                    │  └─────────────┘  └──────────────────┘  │
                    └────────────────────────────────────────┘
```

---

## Phase 1: Core Provider Implementation

**Duration**: 3-5 days  
**Goal**: Establish provider abstraction for LTX Video

### Checklist

- [ ] **1.1** Create `providers/ltx_video/` directory structure
- [ ] **1.2** Define `LTXVideoConfig` Pydantic model:
  ```python
  class LTXVideoConfig(BaseModel):
      model_id: str = "Lightricks/LTX-Video-0.9.7-distilled"
      resolution: Literal["480p", "720p"] = "720p"
      aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3", "3:4"] = "16:9"
      num_frames: int = 121  # ~5 seconds at 24fps
      num_inference_steps: int = 30
      guidance_scale: float = 3.0
      fps: int = 24
      enable_vae_tiling: bool = True
      use_fp8: bool = True  # Memory optimization
  ```
- [ ] **1.3** Create `BaseLTXProvider` abstract class:
  ```python
  class BaseLTXProvider(ABC):
      @abstractmethod
      async def generate_video(
          self,
          prompt: str,
          config: LTXVideoConfig,
          image: Optional[Image.Image] = None,  # For I2V
          video: Optional[Path] = None,  # For V2V/extend
          **kwargs
      ) -> Path:
          """Generate video, return path to output file."""
          pass
      
      @abstractmethod
      async def validate_credentials(self) -> bool:
          pass
      
      @abstractmethod
      def get_available_models(self) -> List[str]:
          pass
  ```
- [ ] **1.4** Add LTX provider to `core/config.py` registry
- [ ] **1.5** Create unit tests for config validation

### Deliverables
- Provider abstraction layer complete
- Pydantic models for type-safe configuration
- Ready for backend implementations

---

## Phase 2: Local Inference Pipeline

**Duration**: 5-7 days  
**Goal**: Implement local LTX Video generation via Hugging Face Diffusers

### Prerequisites
- NVIDIA GPU with 8GB+ VRAM (16GB+ recommended)
- CUDA 11.8+ / 12.x
- PyTorch 2.0+

### Checklist

- [ ] **2.1** Add dependencies to `requirements-ltx-video.txt`:
  ```
  # LTX Video Local Dependencies
  diffusers>=0.31.0
  transformers>=4.44.0
  accelerate>=0.33.0
  sentencepiece>=0.2.0
  imageio[ffmpeg]>=2.35.0
  imageio-ffmpeg>=0.5.1
  ```

- [ ] **2.2** Implement `LocalLTXProvider` class:
  ```python
  class LocalLTXProvider(BaseLTXProvider):
      def __init__(self, config: LTXVideoConfig):
          self.config = config
          self.pipeline = None
          self._loaded_model_id = None
      
      def _load_pipeline(self, force_reload: bool = False) -> None:
          """Lazy-load pipeline with memory optimization."""
          if self.pipeline and not force_reload:
              if self._loaded_model_id == self.config.model_id:
                  return
          
          # Unload existing pipeline
          self._unload_pipeline()
          
          # Load with optimizations
          self.pipeline = LTXPipeline.from_pretrained(
              self.config.model_id,
              torch_dtype=torch.bfloat16,
          )
          self.pipeline.to("cuda")
          
          if self.config.enable_vae_tiling:
              self.pipeline.vae.enable_tiling()
          
          if self.config.use_fp8:
              self._apply_fp8_quantization()
          
          self._loaded_model_id = self.config.model_id
      
      def _unload_pipeline(self) -> None:
          """Free GPU memory."""
          if self.pipeline:
              del self.pipeline
              self.pipeline = None
              torch.cuda.empty_cache()
              gc.collect()
  ```

- [ ] **2.3** Implement generation modes:
  - [ ] Text-to-Video (`generate_t2v`)
  - [ ] Image-to-Video (`generate_i2v`)
  - [ ] Video Extension (`extend_video`)

- [ ] **2.4** Add progress callback for UI integration:
  ```python
  def generate_video(
      self,
      prompt: str,
      config: LTXVideoConfig,
      progress_callback: Optional[Callable[[int, int, str], None]] = None,
      **kwargs
  ) -> Path:
      def callback_wrapper(pipe, step, timestep, kwargs):
          if progress_callback:
              progress_callback(step, config.num_inference_steps, 
                              f"Step {step}/{config.num_inference_steps}")
          return kwargs
      
      video_frames = self.pipeline(
          prompt=prompt,
          callback_on_step_end=callback_wrapper,
          ...
      )
  ```

- [ ] **2.5** Implement memory management:
  - [ ] Automatic VRAM detection and model selection
  - [ ] VAE tiling for high-resolution
  - [ ] FP8 quantization option
  - [ ] Graceful fallback to smaller model on OOM

- [ ] **2.6** Add prompt enhancement integration:
  ```python
  # Use existing LLM integration from video/llm_integration.py
  if enhance_prompt:
      prompt = await self.llm.enhance_video_prompt(prompt)
  ```

- [ ] **2.7** Export to video file:
  ```python
  from diffusers.utils import export_to_video
  
  video_path = output_dir / f"ltx_{timestamp}.mp4"
  export_to_video(video_frames, str(video_path), fps=config.fps)
  ```

### Deliverables
- Fully functional local LTX Video provider
- Memory-optimized for consumer GPUs
- Progress reporting for UI

---

## Phase 3: API Provider Integration

**Duration**: 3-5 days  
**Goal**: Implement cloud API providers for users without local GPU

### 3.1 Fal.ai Provider

- [ ] **3.1.1** Add `fal` to `requirements.txt`:
  ```
  fal-client>=0.4.0
  ```

- [ ] **3.1.2** Implement `FalLTXProvider`:
  ```python
  import fal_client
  
  class FalLTXProvider(BaseLTXProvider):
      MODELS = {
          "ltx-video-v095": "fal-ai/ltx-video-v095",
          "ltx-video-13b": "fal-ai/ltx-video-13b-dev/image-to-video",
          "ltx-video-13b-distilled": "fal-ai/ltx-video-13b-distilled/image-to-video",
          "ltxv-2-pro": "fal-ai/ltxv-2/image-to-video",  # LTX-2 with audio!
      }
      
      async def generate_video(self, prompt: str, config: LTXVideoConfig, **kwargs) -> Path:
          model_endpoint = self.MODELS.get(config.model_id, self.MODELS["ltx-video-v095"])
          
          result = await fal_client.subscribe_async(
              model_endpoint,
              arguments={
                  "prompt": prompt,
                  "negative_prompt": config.negative_prompt,
                  "resolution": config.resolution,
                  "aspect_ratio": config.aspect_ratio,
                  "num_inference_steps": config.num_inference_steps,
                  "expand_prompt": config.enhance_prompt,
              },
              with_logs=True,
              on_queue_update=self._handle_queue_update,
          )
          
          # Download video
          video_url = result["video"]["url"]
          return await self._download_video(video_url)
  ```

- [ ] **3.1.3** Add API key management to settings dialog
- [ ] **3.1.4** Implement cost estimation display (~$0.02/video)

### 3.2 Replicate Provider

- [ ] **3.2.1** Add `replicate` to `requirements.txt`:
  ```
  replicate>=0.25.0
  ```

- [ ] **3.2.2** Implement `ReplicateLTXProvider`:
  ```python
  import replicate
  
  class ReplicateLTXProvider(BaseLTXProvider):
      async def generate_video(self, prompt: str, config: LTXVideoConfig, **kwargs) -> Path:
          output = await replicate.async_run(
              "lightricks/ltx-video",
              input={
                  "prompt": prompt,
                  "negative_prompt": config.negative_prompt,
                  "width": 768,
                  "height": 512,
                  "num_frames": config.num_frames,
              }
          )
          return await self._download_video(output)
  ```

- [ ] **3.2.3** Add Replicate API key to settings

### 3.3 Provider Factory

- [ ] **3.3.1** Create provider factory:
  ```python
  class LTXVideoProviderFactory:
      @staticmethod
      def create(backend: str, config: LTXVideoConfig) -> BaseLTXProvider:
          providers = {
              "local": LocalLTXProvider,
              "fal": FalLTXProvider,
              "replicate": ReplicateLTXProvider,
          }
          return providers[backend](config)
  ```

### Deliverables
- Fal.ai integration with queue handling
- Replicate integration as alternative
- Unified provider factory

---

## Phase 4: UI Integration

**Duration**: 4-6 days  
**Goal**: Integrate LTX Video into the existing Video Tab

### 4.1 Minimal Video Tab Changes

Following the "minimal UI changes" requirement:

- [ ] **4.1.1** Add LTX Video as generation source in existing dropdown:
  ```python
  # In gui/video_tab.py
  self.source_combo.addItem("LTX Video (Local)", "ltx_local")
  self.source_combo.addItem("LTX Video (Fal.ai)", "ltx_fal")
  self.source_combo.addItem("LTX Video (Replicate)", "ltx_replicate")
  ```

- [ ] **4.1.2** Add collapsible LTX Settings panel:
  ```python
  class LTXSettingsWidget(QWidget):
      def __init__(self):
          super().__init__()
          layout = QFormLayout(self)
          
          self.model_combo = QComboBox()
          self.model_combo.addItems([
              "LTXV-2B-Distilled (Fast)",
              "LTXV-2B (Balanced)",
              "LTXV-13B-Distilled (Quality+Speed)",
              "LTXV-13B (Highest Quality)"
          ])
          layout.addRow("Model:", self.model_combo)
          
          self.resolution_combo = QComboBox()
          self.resolution_combo.addItems(["480p", "720p"])
          layout.addRow("Resolution:", self.resolution_combo)
          
          self.duration_spin = QDoubleSpinBox()
          self.duration_spin.setRange(1.0, 10.0)
          self.duration_spin.setValue(5.0)
          self.duration_spin.setSuffix(" seconds")
          layout.addRow("Duration:", self.duration_spin)
          
          self.enhance_prompt_check = QCheckBox("Enhance prompt with LLM")
          self.enhance_prompt_check.setChecked(True)
          layout.addRow(self.enhance_prompt_check)
  ```

- [ ] **4.1.3** Add I2V mode toggle:
  ```python
  self.i2v_group = QGroupBox("Image-to-Video")
  self.i2v_group.setCheckable(True)
  self.i2v_group.setChecked(False)
  
  self.source_image_btn = QPushButton("Select Source Image...")
  self.source_image_preview = QLabel()
  self.source_image_preview.setFixedSize(160, 90)
  ```

### 4.2 Worker Thread Integration

- [ ] **4.2.1** Create `LTXVideoWorker(QRunnable)`:
  ```python
  class LTXVideoWorker(QRunnable):
      class Signals(QObject):
          progress = Signal(int, int, str)  # current, total, message
          finished = Signal(Path)
          error = Signal(str)
      
      def __init__(self, provider: BaseLTXProvider, prompt: str, config: LTXVideoConfig):
          super().__init__()
          self.signals = self.Signals()
          self.provider = provider
          self.prompt = prompt
          self.config = config
          self._cancelled = False
      
      def run(self):
          try:
              result = asyncio.run(self.provider.generate_video(
                  self.prompt,
                  self.config,
                  progress_callback=self._report_progress
              ))
              if not self._cancelled:
                  self.signals.finished.emit(result)
          except Exception as e:
              self.signals.error.emit(str(e))
      
      def cancel(self):
          self._cancelled = True
  ```

- [ ] **4.2.2** Connect to existing progress bar
- [ ] **4.2.3** Add cancel button handling

### 4.3 Preview Integration

- [ ] **4.3.1** Add video preview player:
  ```python
  from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
  from PySide6.QtMultimediaWidgets import QVideoWidget
  
  self.preview_player = QMediaPlayer()
  self.preview_widget = QVideoWidget()
  self.preview_player.setVideoOutput(self.preview_widget)
  ```

- [ ] **4.3.2** Auto-play generated videos
- [ ] **4.3.3** Add "Save to Project" button

### Deliverables
- LTX Video seamlessly integrated into existing Video Tab
- Worker thread with progress and cancellation
- Video preview capability

---

## Phase 5: Advanced Features

**Duration**: 5-7 days  
**Goal**: Implement advanced LTX Video capabilities

### 5.1 Video Extension

- [ ] **5.1.1** Add "Extend Video" mode:
  ```python
  class VideoExtensionConfig(BaseModel):
      source_video: Path
      extension_direction: Literal["forward", "backward", "both"] = "forward"
      extension_duration: float = 3.0  # seconds
      conditioning_strength: float = 1.0
  ```

- [ ] **5.1.2** Integrate with existing video project system

### 5.2 Multi-Keyframe Animation

- [ ] **5.2.1** Support multiple conditioning images:
  ```python
  class KeyframeConfig(BaseModel):
      image_path: Path
      target_frame: int
      conditioning_strength: float = 1.0
  
  async def generate_with_keyframes(
      self,
      prompt: str,
      keyframes: List[KeyframeConfig],
      config: LTXVideoConfig
  ) -> Path:
      ...
  ```

- [ ] **5.2.2** Add keyframe timeline UI component

### 5.3 LoRA Support

- [ ] **5.3.1** Add LoRA loading capability:
  ```python
  def load_lora(self, lora_path: Path, scale: float = 1.0):
      self.pipeline.load_lora_weights(str(lora_path))
      self.pipeline.fuse_lora(lora_scale=scale)
  ```

- [ ] **5.3.2** Integrate with model browser for LoRA discovery
- [ ] **5.3.3** Add LoRA selection in UI

### 5.4 LTX-2 Audio+Video (Future)

When LTX-2 weights are released:

- [ ] **5.4.1** Add synchronized audio generation support
- [ ] **5.4.2** Update Fal.ai integration for `ltxv-2` endpoints
- [ ] **5.4.3** Add audio preview in video player

### 5.5 Integration with Video Project System

- [ ] **5.5.1** Add LTX clips to existing scene/project model:
  ```python
  # In video/project.py
  class LTXVideoClip(VideoClip):
      prompt: str
      config: LTXVideoConfig
      source_type: Literal["t2v", "i2v", "extend"]
      source_image: Optional[Path] = None
  ```

- [ ] **5.5.2** Enable LTX generation for each scene in a video project
- [ ] **5.5.3** Support prompt enhancement per-scene

### Deliverables
- Video extension capability
- Keyframe-based animation
- LoRA support
- Future-ready for LTX-2

---

## Hardware Requirements

### Minimum (API Mode Only)
- Any modern CPU
- 4GB RAM
- Internet connection
- ~$0.01-0.05 per video

### Recommended (Local Inference - 2B Models)
- NVIDIA GPU with 8GB+ VRAM (RTX 3070, RTX 4060 Ti, etc.)
- 16GB system RAM
- 50GB free disk space for models
- CUDA 11.8+

### Optimal (Local Inference - 13B Models)
- NVIDIA GPU with 24GB+ VRAM (RTX 4090, A100, etc.)
- 32GB system RAM
- 100GB free disk space
- CUDA 12.0+

### Performance Estimates (Local)

| Hardware | Model | Time (5s video) |
|----------|-------|-----------------|
| RTX 4090 | LTXV-13B-Distilled | ~15 seconds |
| RTX 4090 | LTXV-2B-Distilled | ~5 seconds |
| RTX 4070 | LTXV-2B-Distilled | ~12 seconds |
| RTX 3080 | LTXV-2B-Distilled | ~18 seconds |
| H100 | LTXV-13B | ~10 seconds |

---

## Dependencies

### New Dependencies for LTX Video

```txt
# requirements-ltx-video.txt

# Core LTX Video
diffusers>=0.31.0
transformers>=4.44.0
accelerate>=0.33.0
sentencepiece>=0.2.0
imageio[ffmpeg]>=2.35.0
imageio-ffmpeg>=0.5.1

# API Providers
fal-client>=0.4.0
replicate>=0.25.0

# Video playback (Qt)
# Already included with PySide6
```

### Installation Script

```bash
# install_ltx_video.sh

#!/bin/bash
echo "Installing LTX Video dependencies..."

# Check for CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected. Installing with CUDA support..."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
else
    echo "No NVIDIA GPU detected. Installing CPU-only (API mode only)..."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
fi

pip install -r requirements-ltx-video.txt

echo "LTX Video dependencies installed successfully!"
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_ltx_video.py

class TestLTXVideoConfig:
    def test_valid_config(self):
        config = LTXVideoConfig(resolution="720p", num_frames=121)
        assert config.fps == 24
    
    def test_invalid_resolution(self):
        with pytest.raises(ValidationError):
            LTXVideoConfig(resolution="4K")

class TestLTXVideoProvider:
    @pytest.fixture
    def mock_provider(self):
        return MockLTXProvider()
    
    def test_generate_t2v(self, mock_provider):
        result = asyncio.run(mock_provider.generate_video(
            "A cat walking",
            LTXVideoConfig()
        ))
        assert result.exists()
        assert result.suffix == ".mp4"
```

### Integration Tests

```python
# tests/test_ltx_integration.py

@pytest.mark.skipif(not torch.cuda.is_available(), reason="No GPU")
class TestLocalLTXIntegration:
    def test_t2v_generation(self):
        provider = LocalLTXProvider(LTXVideoConfig(
            model_id="Lightricks/LTX-Video-0.9.7-distilled",
            num_frames=25,  # ~1 second, faster for tests
        ))
        result = asyncio.run(provider.generate_video("A simple test"))
        assert result.exists()

@pytest.mark.skipif(not os.getenv("FAL_KEY"), reason="No Fal API key")
class TestFalIntegration:
    def test_api_connection(self):
        provider = FalLTXProvider(LTXVideoConfig())
        assert asyncio.run(provider.validate_credentials())
```

### Manual Test Checklist

- [ ] Text-to-video with short prompt
- [ ] Text-to-video with detailed cinematography prompt
- [ ] Image-to-video with various aspect ratios
- [ ] Video extension (forward)
- [ ] Video extension (backward)
- [ ] Cancel generation mid-process
- [ ] OOM recovery with automatic model downgrade
- [ ] Cross-platform: Windows, macOS, Linux
- [ ] API fallback when local fails

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| GPU OOM on consumer hardware | High | Medium | Auto-fallback to smaller model, VAE tiling |
| API rate limiting | Medium | Low | Queue management, retry with backoff |
| Model download failures | Medium | Medium | Resume support, mirror URLs |
| FFmpeg encoding issues | Low | High | Robust error handling, format detection |
| Cross-platform GPU issues | Medium | Medium | Thorough testing, graceful degradation |

### Dependency Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Diffusers API changes | Medium | Medium | Pin versions, monitor releases |
| LTX-2 delayed release | High | Low | Current models are excellent |
| API provider pricing changes | Low | Low | Multiple providers, local fallback |

### User Experience Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Long generation times | Medium | Medium | Progress indicators, time estimates |
| Confusing model selection | Medium | Low | Smart defaults, tooltips |
| Quality expectations | Medium | Medium | Clear documentation, previews |

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Provider abstraction fully implemented
- [ ] All Pydantic models passing validation
- [ ] Unit tests passing

### Phase 2 Complete When:
- [ ] Local T2V generates valid video
- [ ] Memory management prevents OOM
- [ ] Progress callbacks working

### Phase 3 Complete When:
- [ ] Fal.ai integration functional
- [ ] Replicate integration functional
- [ ] API keys configurable in settings

### Phase 4 Complete When:
- [ ] LTX Video appears in Video Tab
- [ ] Generation completes with progress
- [ ] Video preview plays generated content

### Phase 5 Complete When:
- [ ] Video extension works
- [ ] LoRA loading functional
- [ ] Integration with video projects complete

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1 | 3-5 days | None |
| Phase 2 | 5-7 days | Phase 1 |
| Phase 3 | 3-5 days | Phase 1 |
| Phase 4 | 4-6 days | Phases 2 & 3 |
| Phase 5 | 5-7 days | Phase 4 |

**Total Estimated Duration**: 3-5 weeks

---

## References

- [LTX-Video GitHub](https://github.com/Lightricks/LTX-Video)
- [Hugging Face Diffusers LTX Docs](https://huggingface.co/docs/diffusers/main/en/api/pipelines/ltx_video)
- [Fal.ai LTX Models](https://fal.ai/models/fal-ai/ltx-video)
- [Replicate LTX Video](https://replicate.com/lightricks/ltx-video)
- [LTX-2 Announcement](https://www.prnewswire.com/news-releases/lightricks-releases-ltx-2-the-first-complete-open-source-ai-video-foundation-model-302593012.html)
- [ComfyUI LTX Workflows](https://github.com/Lightricks/ComfyUI-LTXVideo)

---

*Last Updated: December 2025*  
*Maintained by: ImageAI Development Team*
