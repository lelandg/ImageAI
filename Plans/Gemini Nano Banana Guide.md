# Gemini Nano Banana Guide

**Aspect Ratio for Gemini Nano Banana**
Yes, you can create images with a 16:9 aspect ratio using Nano Banana, though it may require specific techniques as direct commands don't always work as expected.

Nano Banana, also known as Gemini 2.5 Flash Image, is a powerful AI image generation tool from Google. While you can include the desired aspect ratio in your text prompt, there is a known issue where the model may default to a square 1:1 aspect ratio.

To ensure you get a 16:9 image, you can use the following methods:

*   **Specify in the prompt:** You can directly ask for a 16:9 aspect ratio in your prompt. For example, "A photorealistic medium shot of a young girl...The image should be in a 16:9 format."
*   **Reference image workaround:** A more reliable method is to upload a blank image that has a 16:9 aspect ratio. Nano Banana will then use this as a reference for the final output dimensions. You can create a blank, transparent PNG file with your desired aspect ratio to use for this purpose.
*   **Outpainting:** If you have an existing image that is not 16:9, you can place it on a blank 16:9 canvas and ask Nano Banana to fill in the surrounding space.

It's important to note that the aspect ratio of any reference images you use will influence the final output. If you use a vertical reference image, the generated image is likely to also be vertical.

**Image Continuity across Images**
### Achieving Image Continuity with Nano Banana: A Guide to Crafting Prompts for Sequential Art

Yes, you can absolutely leverage the power of "Nano Banana," the colloquial name for Google's advanced Gemini 2.5 Flash Image model, to create a series of images with remarkable continuity. This powerful tool excels at maintaining the consistency of characters, styles, and objects across multiple image generations, making it an ideal solution for visual storytelling, creating comic strips, or developing consistent brand assets.

The key to unlocking this capability lies in a technique called "iterative refinement," where you engage in a conversational process with the AI, making incremental changes to build your image series. You can start with an initial image and then provide text prompts to modify it, preserving the elements you want to keep consistent.

#### Crafting Your Prompts for Continuity

To create a series of images with your Python application, you will typically start by generating a base image or using an existing one. Then, in subsequent calls to the API, you will reference the previous image while providing a new prompt that describes the desired change.

Here is a step-by-step guide to structuring your prompts for image continuity:

**1. Establish Your Character and Scene:**

Your first prompt should be descriptive and establish the core elements of your series. Clearly define your character's appearance, clothing, and the initial setting.

**Example Initial Prompt:**
```
"Create a photorealistic image of a young female astronaut with short, curly brown hair and green eyes. She is wearing a sleek, white and orange spacesuit and standing in a minimalist, white spaceship cockpit with a large window showing a view of Earth."
```

**2. Attach the Previous Image:**

For each subsequent image in the series, you must include the previously generated image as a reference. This is the most critical step for maintaining continuity. Your Python application will need to handle the image data from the previous API response and include it in the next request.

**3. Use Clear and Incremental Prompts for Subsequent Images:**

Your follow-up prompts should be concise and focus on the specific changes you want to make. Think of it as giving directions to an artist. Instead of redescribing the entire scene, you can refer to the existing elements.

**Example Follow-up Prompts:**

*   **To change the character's action:** "Make her press a glowing blue button on the control panel."
*   **To alter the environment:** "Through the window, show a nebula with vibrant purple and pink colors instead of Earth."
*   **To change the character's expression:** "Change her expression to one of awe and wonder."

By providing the previous image, Nano Banana understands the context and applies the changes while preserving the astronaut's appearance and the overall style of the scene.

#### Python Implementation Example

Below is a conceptual Python snippet demonstrating how you might structure your code to connect to the Nano Banana API (using the `gemini-2.5-flash-image-preview` model) and generate a sequence of images. Note that you will need to have the appropriate Google AI SDK installed and authenticated in your environment.

```python
import google.generativeai as genai
from PIL import Image
import io

# Configure your API key
genai.configure(api_key="YOUR_API_KEY")

# Initialize the model
model = genai.GenerativeModel('gemini-2.5-flash-image-preview')

# --- Image 1: The Initial Scene ---
initial_prompt = "Create a photorealistic image of a young female astronaut with short, curly brown hair and green eyes. She is wearing a sleek, white and orange spacesuit and standing in a minimalist, white spaceship cockpit with a large window showing a view of Earth."
response = model.generate_content([initial_prompt])

# Assuming the API returns image data directly
initial_image_data = response.candidates[0].content.parts[0].inline_data.data
initial_image = Image.open(io.BytesIO(initial_image_data))
initial_image.save("image_1.png")
print("Generated image_1.png")

# --- Image 2: An Action ---
# In a real application, you would load the image data from the previous step
prompt_2 = "Make her press a glowing blue button on the control panel."
response_2 = model.generate_content([prompt_2, initial_image])

image_2_data = response_2.candidates[0].content.parts[0].inline_data.data
image_2 = Image.open(io.BytesIO(image_2_data))
image_2.save("image_2.png")
print("Generated image_2.png")

# --- Image 3: A Change in Scenery ---
prompt_3 = "Through the window, show a nebula with vibrant purple and pink colors instead of Earth."
response_3 = model.generate_content([prompt_3, image_2])

image_3_data = response_3.candidates[0].content.parts[0].inline_data.data
image_3 = Image.open(io.BytesIO(image_3_data))
image_3.save("image_3.png")
print("Generated image_3.png")

```

**Important Considerations:**

*   **API Documentation:** Always refer to the official Google AI documentation for the most up-to-date information on how to structure your API calls and handle image data.
*   **Model Name:** The specific model name to use is `gemini-2.5-flash-image-preview`.
*   **Multi-Turn Editing:** Nano Banana's strength lies in this "multi-turn" editing capability, where the AI remembers the context from previous interactions.
*   **Combining Images:** You can also provide multiple images to blend elements or transfer styles, offering even more creative control.

By following these guidelines and utilizing the iterative capabilities of Nano Banana, you can successfully create compelling series of images with strong visual continuity directly from your Python application.

### Image size limits of Gemini 2.5 Flash Image

**Understanding the Image Size Limits of Nano Banana:**
Nano Banana, the AI image generation and editing tool officially known as Gemini 2.5 Flash Image, has varying maximum image resolutions depending on whether an image is being created from a text prompt or edited from an existing photo.

For newly generated images, user experiences suggest a resolution of approximately 1024x1024 pixels. This is noted as a decrease from a previous capability that allowed for images as large as 2048x2048 pixels. While some users have been able to generate images with slightly different dimensions, such as 1500x700, the general consensus points to a square aspect ratio with a width and height of around 1000 pixels.

When it comes to editing existing images, the maximum output resolution appears to be lower. According to a Gemini Apps Community response, edited images are limited to a maximum of 928 x 1120 pixels, regardless of the original image's size. Another report indicates that downloaded edited images have a resolution of around 720p.

It is important to distinguish between the capabilities of the underlying AI model and the limitations of the interfaces through which it is accessed. The official documentation for the Gemini 2.5 Flash model specifies a maximum input image size of 7 MB but does not provide specific pixel dimensions for the output. This could imply that the resolution caps are a result of the implementation within the Gemini app and other platforms rather than a hard limit of the model itself.

For those seeking higher-resolution images, a common practice is to use separate upscaling tools after the image has been generated by Nano Banana. This post-processing step can increase the pixel dimensions of the image.