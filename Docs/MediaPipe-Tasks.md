# MediaPipe Tasks migration

ImageAI now requires MediaPipe 1.0.1 or later within major version 1 for its optional Sprite and Character Animator integrations. This removes the legacy protobuf<5 constraint and permits patched protobuf>=5.29.6,<6. MediaPipe stays optional; base image generation does not require it.

Use Sprite's **Install…** button or Character Animator's **Install AI Components** action to upgrade an existing legacy installation. A legacy installation no longer appears ready merely because the old package is installed. Install or update the base requirements before using the upgraded application, and update MediaPipe in the same environment if it was previously installed. Removing the unused MoviePy package avoids its incompatible Pillow<12 restriction. The active code uses FFmpeg directly.

On first use, the application downloads official Google vision assets into `get_data_paths().model_cache("mediapipe")`, under the user-configured Models storage root. Sprite's landscape selfie model is 250,177 bytes. Character Animator's heavy pose and face models are 30,664,242 and 3,758,596 bytes. Downloads use TLS, an explicit size limit, SHA-256 validation, and temporary files replaced atomically only after verification. A cached model is verified before reuse. No images are sent to a cloud service for these local inferences.

Sprite preserves the floating alpha mask and edge-refinement behavior. Pose detection preserves 33 landmarks with pixel x/y, z, and visibility; face detection preserves 478 landmarks with pixel x/y and z. Result buffers are copied before Tasks resources close.

CPython 3.12 on Windows has an early platform guard before core imports. Native startup failures were reproduced in the WMI/COM path reached by keyring and PortAudio; the guard selects Python's standard Windows fallback. Other operating systems, Python versions, and interpreter implementations are unchanged.

API references: [Image Segmenter](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter/python), [Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python), [Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python). Official model URLs and verified hashes are recorded in `core/mediapipe_tasks.py`.
