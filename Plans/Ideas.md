# Global LLM provider
 - In settings, store the current LLM provider.
 - In Image and Video, add two combos to the top. Let the user choose the provider and model. When the user changes the provider, the model dropdown should be updated.
 - On the video tab, move the current LLM provider to the top.
 - When the user changes projects (opens or closes), update the LLM provider based on the project.
 - If the project name is blank, don't change the LLM provider, but use global setting at startup.
 - Make sure when one combo the combos on the two tabs are in sync. When user changes one, the other should change.

# Settings Tab Update
 - Show all providers in the page. This is a usability enchancement. So I can see all providers and keys and models in one place. 
 - Each one should have a "show API key" button. (Or appropriate for GCloud.)
 - For Google, if I select Gcloud, don't show the API key, and vice-versa.

# LLM Prompt enhancement
 - For the image tab, add a button to "Enhance prompt."
 - When clicked, submit the prompt to the LLM and get the enhanced prompt.
 - When the user clicks "Enhance prompt", shows a dialog with the enhanced prompt.
 - When the user clicks "OK", replace the prompt with the enhanced prompt.
 - When the user clicks "Cancel", do nothing.
 - When the user clicks "OK" or "Cancel", save the enhanced prompt to the project, or settings if no project.
 - Make this change in the video tab as well as for the Input text.

# Starting Image Reference
 - Add a button to the image tab to "Start with reference."
 - For now, this will work with Nano Banana using information in './Plans/GeminiFullFeatures.md' (which was based on https://ai.google.dev/gemini-api/docs/image-generation)
 - Plan to add this to other providers, including ones not yet implemented. 
 - Do in a standardized at a high level. Each LLM provider *may* have variations or be not implemented.
 - When clicked, show a dialog to select an image.
 - When the user clicks "OK", use it as the starting image.
 - Do this with the video tab as well.
 - Then this can work the same at the LLM level on both tabs. But they should be different images.
 - Store these in the settings or project, as appropriate. (Like above.)
 - When selected, show the starting image as a thumbnail. 
 - Add a checkbox next to it to disable using it. 
 - Also, a "clear" button to remove it.
 - When the user clicks "clear", remove it from settings or project, as appropriate.
 - When the user clicks "clear", disable the button until they select a new image.
 - When the user changes the provider, if the new provider does not support starting with a reference image, disable the button.
 - We'll get specs for other providers later.

# Research Midjourney
 - I know Midjourney does not have an API. So we probably need to use REST.
 - Research how to use REST to generate images, use reference images, and everything Midjourney supports.
 - This should be fully featured and as much like the website as possible, but with a UI to match the app.
 - Create a file in ./Plans with the proposed implementation.
 - Change UI as needed for this.

# Bonus Points
 - If you get this far, start implementing the rest of './Plans/GeminiFullFeatures.md' that we've not implemented yet.