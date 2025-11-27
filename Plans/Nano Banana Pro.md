Yes, you can use **Nano Banana Pro** in your Python app now.

**"Nano Banana Pro"** is the popular community nickname for Google's new **Gemini 3 Pro Image** model (`gemini-3-pro-image-preview`), which was released in late November 2025.

### **Requirements**
To use it, you need the following:
1.  **Billing Enabled:** Unlike the standard "Nano Banana" (Flash) model, the Pro version **does not have a free tier**. You must have a Google Cloud project with billing enabled to pay for usage (approx. $0.13 - $0.24 per image).
2.  **API Key:** You need an API key from [Google AI Studio](https://aistudio.google.com/) or Vertex AI.
3.  **Python Library:** You must install the latest Google Gen AI SDK.
    *   Command: `pip install --upgrade google-genai`
    *   *Note: You generally need version 1.51.0 or higher.*

### **Python Code Example**
Use the specific model ID `gemini-3-pro-image-preview` in your code.

```python
import os
from google import genai
from google.genai import types

# 1. Initialize Client (ensure GOOGLE_API_KEY is set in your environment variables)
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# 2. Configure the generation request
# 'media_resolution' can be set to 'high' for 4K output (costs more)
config = types.GenerateContentConfig(
    temperature=1.0,
    media_resolution="medium" 
)

# 3. Generate the image
try:
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents="A cinematic, photorealistic shot of a futuristic city made of glass, golden hour lighting",
        config=config
    )

    # 4. Save the image (assuming single image response)
    # The SDK returns the image bytes directly in the response structure
    if response.candidates and response.candidates[0].content.parts:
        image_data = response.candidates[0].content.parts[0].inline_data.data
        with open("output_image.png", "wb") as f:
            f.write(image_data)
        print("Image saved to output_image.png")
    else:
        print("No image generated.")

except Exception as e:
    print(f"Error occurred: {e}")
```

### **Hardware Note (Banana Pi)**
If you were actually asking about a single-board computer (like a Raspberry Pi), you are likely conflating names. There is a **Banana Pi BPI-M2 Pro** and a **Nano Pi**, but no board strictly named "Nano Banana Pro."
*   **If this is what you meant:** You can use Python on these boards immediately. You typically need the `RPi.GPIO` (often a fork for Banana Pi) or `wiringpi` Python libraries to control hardware pins.