import time
import requests
import os
import json
import logging
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIMLAPI_KEY = os.getenv("AIMLAPI_KEY")
CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
DALLE_API_URL = "https://api.openai.com/v1/images/generations"
STABLE_AUDIO_GENERATE_URL = "https://api.aimlapi.com/v2/generate/audio"

def generate_music(prompt="gentle and whimsical background music for a children's story", seconds_total=30):
    if not AIMLAPI_KEY:
        logger.error("AIMLAPI_KEY not found in environment variables")
        return None

    headers = {
        "Authorization": f"Bearer {AIMLAPI_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "stable-audio",
        "prompt": prompt,
        "seconds_start": 1,
        "seconds_total": seconds_total,
        "steps": 100
    }

    try:
        # Start audio generation
        response = requests.post(STABLE_AUDIO_GENERATE_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        generation_id = data.get("id")
        status = data.get("status")

        if not generation_id or status != "queued":
            logger.error(f"Failed to start audio generation: {data}")
            return None

        # Poll for completion
        for _ in range(30):  # Try for up to 60 seconds
            fetch_response = requests.get(
                f"{STABLE_AUDIO_GENERATE_URL}?generation_id={generation_id}",
                headers={"Authorization": f"Bearer {AIMLAPI_KEY}", "Accept": "*/*"}
            )
            fetch_response.raise_for_status()
            fetch_data = fetch_response.json()

            if fetch_data.get("status") == "completed" and fetch_data.get("audio_file"):
                audio_url = fetch_data["audio_file"].get("url")
                logger.debug(f"Music generated successfully: {audio_url}")
                return audio_url
            elif fetch_data.get("status") == "error":
                logger.error(f"Audio generation error: {fetch_data.get('error')}")
                return None

            time.sleep(2)  # Wait before polling again

        logger.error("Audio generation timed out")
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating music: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_story', methods=['POST'])
def generate_story():
    data = request.json
    theme = data.get("theme", "").strip()

    if not theme:
        return jsonify({"error": "Story theme is required."}), 400

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    system_prompt = """
    Generate a children's story based on the given theme. 
    The story MUST have EXACTLY 20 scenes - no more, no less.
    Define the main characters with detailed physical descriptions suitable for image generation. 
    Output in JSON format with the following structure: 
    {
      "storyline": "Overall story summary",
      "characters": [
        {"name": "Character Name", "description": "Detailed physical description"}
      ],
      "scenes": [
        {"scene_number": 1, "description": "Scene description", "characters": ["Character Name"]},
        {"scene_number": 2, "description": "Scene description", "characters": ["Character Name"]},
        ...
        {"scene_number": 20, "description": "Scene description", "characters": ["Character Name"]}
      ]
    }
    You MUST include exactly 20 scenes numbered from 1 to 20.
    Ensure character descriptions are consistent and detailed enough for generating consistent images in a Disney-like cartoon style. 
    Your response must be a valid JSON object and nothing else. Do not include any additional text, explanations, or code blocks. Start directly with the '{' and end with '}'.
    """
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": theme}
        ],
        "max_tokens": 3000
    }

    try:
        response = requests.post(CHAT_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        story_json_str = response.json()["choices"][0]["message"]["content"].strip()
        
        start = story_json_str.find('{')
        end = story_json_str.rfind('}') + 1
        if start != -1 and end != -1:
            story_json_str = story_json_str[start:end]
        else:
            raise ValueError("No JSON object found in the response")
        
        story_data = json.loads(story_json_str)
        
        # Validate that there are exactly 20 scenes
        scenes = story_data.get("scenes", [])
        if len(scenes) != 20:
            logger.warning(f"Story does not have exactly 20 scenes (has {len(scenes)}). Adjusting...")
            
            # If too few scenes, add additional scenes
            if len(scenes) < 20:
                last_scene_number = len(scenes)
                for i in range(last_scene_number + 1, 21):
                    # Create a new scene that follows from the last scene
                    new_scene = {
                        "scene_number": i,
                        "description": f"Continuation of the story where the characters conclude their adventure.",
                        "characters": story_data.get("characters", [])[:1] if story_data.get("characters") else []
                    }
                    if new_scene["characters"]:
                        new_scene["characters"] = [char["name"] for char in new_scene["characters"]]
                    scenes.append(new_scene)
            
            # If too many scenes, keep only the first 20
            if len(scenes) > 20:
                scenes = scenes[:20]
                
            # Update scene numbers to ensure they're sequential
            for i, scene in enumerate(scenes, 1):
                scene["scene_number"] = i
                
            story_data["scenes"] = scenes
        
        session["story"] = story_data
        logger.debug(f"Generated story: {story_data}")
        return jsonify(story_data)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {str(e)} - Raw response: {story_json_str}")
        return jsonify({"error": f"Failed to parse JSON: {str(e)}", "response": story_json_str}), 500
    except Exception as e:
        logger.error(f"Error in generate_story: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_music', methods=['POST'])
def generate_music_endpoint():
    try:
        music_url = generate_music()
        if music_url:
            session["music_url"] = music_url
            return jsonify({"music_url": music_url})
        else:
            logger.error("Failed to generate music")
            return jsonify({"error": "Failed to generate music"}), 500
    except Exception as e:
        logger.error(f"Error in generate_music_endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_scene_image', methods=['POST'])
def generate_scene_image():
    data = request.json
    scene_number = data.get("scene_number")

    if "story" not in session:
        logger.error("Story not found in session")
        return jsonify({"error": "Please generate the story first."}), 400

    story = session["story"]
    scenes = story.get("scenes", [])
    if not scenes:
        logger.error("No scenes found in story data")
        return jsonify({"error": "No scenes available in story data."}), 500

    if scene_number < 1 or scene_number > len(scenes):
        logger.error(f"Invalid scene number: {scene_number}, scenes length: {len(scenes)}")
        return jsonify({"error": "Invalid scene number."}), 400

    scene = scenes[scene_number - 1]
    scene_description = scene.get("description")
    characters_involved = scene.get("characters", [])

    if not scene_description:
        logger.error(f"Invalid scene data for scene {scene_number}: {scene}")
        return jsonify({"error": "Scene description is missing."}), 500

    character_descriptions = []
    for char_name in characters_involved:
        char_found = False
        for char in story.get("characters", []):
            if char["name"] == char_name:
                character_descriptions.append(f"{char['name']}, {char['description']}")
                char_found = True
                break
        if not char_found:
            logger.error(f"Character {char_name} not found in story characters")
            return jsonify({"error": f"Character {char_name} not found in story."}), 500

    # Generate prompt even if there are no characters
    if character_descriptions:
        characters_str = " and ".join(character_descriptions)
        full_prompt = (
            f"Create an image in a vibrant Disney-like cartoon style, inspired by Tangled or Frozen, "
            f"featuring {characters_str}. The scene is: {scene_description}. "
            "Ensure consistent character appearances and art style."
        )
    else:
        full_prompt = (
            f"Create an image in a vibrant Disney-like cartoon style, inspired by Tangled or Frozen, "
            f"depicting the scene: {scene_description}."
        )

    logger.debug(f"Generated prompt for scene {scene_number}: {full_prompt}")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-image-1",
        "prompt": full_prompt,
        "n": 1,
        "size": "1024x1024",
        "output_format": "png"
    }

    try:
        response = requests.post(DALLE_API_URL, headers=headers, json=payload)
        
        # Specific handling for rate limits
        if response.status_code == 429:
            logger.warning("Rate limit exceeded with OpenAI API")
            return jsonify({"error": "Rate limit exceeded. Please wait before trying again."}), 429
            
        response.raise_for_status()
        response_json = response.json()
        logger.debug(f"Image API response: {response_json}")

        if "data" not in response_json or not response_json["data"]:
            logger.error(f"No image data in API response: {response_json}")
            return jsonify({
                "error": "No image data returned by API.",
                "api_response": response_json
            }), 500

        if not response_json["data"][0].get("b64_json"):
            logger.error(f"No b64_json in API response data: {response_json}")
            return jsonify({
                "error": "Base64 image data not found in API response.",
                "api_response": response_json
            }), 500

        image_b64 = response_json["data"][0]["b64_json"]
        return jsonify({"image_b64": image_b64})

    except requests.exceptions.HTTPError as e:
        error_message = f"HTTP Error from Image API: {str(e)} - Response: {e.response.text if e.response else 'No response'}"
        logger.error(error_message)
        
        # Handle various HTTP error codes
        if e.response:
            if e.response.status_code == 429:
                return jsonify({
                    "error": "OpenAI API rate limit exceeded. Please try again in a few minutes.",
                }), 429
            elif e.response.status_code == 403:
                error_message = (
                    "Failed to generate image: 403 Forbidden. Check if your API key has access to gpt-image-1, "
                    "verify billing status, or contact OpenAI support."
                )
        
        return jsonify({
            "error": error_message,
            "details": str(e),
            "api_response": e.response.text if e.response else "No response"
        }), e.response.status_code if e.response else 500
        
    except Exception as e:
        logger.error(f"Unexpected error in generate_scene_image: {str(e)}")
        return jsonify({
            "error": f"Failed to generate image: {str(e)}",
            "details": str(e)
        }), 500
    
@app.route('/generate_cover_image', methods=['POST'])
def generate_cover_image():
    data = request.json
    theme = data.get("theme", "").strip()

    if not theme:
        return jsonify({"error": "Theme is required to generate cover image."}), 400

    prompt = (
        f"Create a vibrant Disney-style storybook cover inspired by Tangled or Frozen, "
        f"based on the theme: '{theme}'. Include dreamy background elements, warm lighting, and "
        f"an inviting sense of adventure. No text. Just a magical illustrated cover."
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "output_format": "png"
    }

    try:
        response = requests.post(DALLE_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        response_json = response.json()

        if "data" not in response_json or not response_json["data"]:
            return jsonify({"error": "No image data returned by API."}), 500

        image_b64 = response_json["data"][0].get("b64_json")
        if not image_b64:
            return jsonify({"error": "Base64 image data not found in API response."}), 500

        return jsonify({"image_b64": image_b64})
    except Exception as e:
        return jsonify({"error": f"Failed to generate cover image: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)