async function generateStory() {
  const theme = document.getElementById("theme").value.trim();
  const errorMessage = document.getElementById("errorMessage");
  const storyContainer = document.getElementById("story-container");
  const storyline = document.getElementById("storyline");
  const charactersList = document.getElementById("characters");
  const flipbook = document.getElementById("flipbook");
  const generateBtn = document.querySelector('button[onclick="generateStory()"]');

  if (!theme) {
    errorMessage.innerText = "Please enter a story theme.";
    errorMessage.style.display = 'block';
    return;
  }

  errorMessage.style.display = 'none';
  storyContainer.style.display = 'none';
  generateBtn.disabled = true;
  generateBtn.textContent = "Generating Story...";

  try {
    const res = await fetch("/generate_story", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ theme }),
    });

    const data = await res.json();

    if (res.ok && data.storyline) {
      storyline.innerText = data.storyline;

      charactersList.innerHTML = '';
      data.characters.forEach(char => {
        const li = document.createElement('li');
        li.innerText = `${char.name}: ${char.description}`;
        charactersList.appendChild(li);
      });

      flipbook.innerHTML = '';
      // Add cover page
      const coverDiv = document.createElement('div');
      coverDiv.className = 'page cover-page';
      coverDiv.style.background = 'linear-gradient(to bottom, #f5f5f5, #d3d3d3)';
      coverDiv.style.border = '1px solid #999';
      coverDiv.style.boxShadow = '5px 5px 15px rgba(0,0,0,0.3)';
      coverDiv.innerHTML = `
        <div class="cover-title">${theme || "The Magical Adventure"}</div>
        <p class="cover-subtitle">A Disney-Style Story</p>
      `;
      flipbook.appendChild(coverDiv);

      // Ensure we have exactly 20 scenes
      const scenes = data.scenes || [];
      const sceneCount = scenes.length;
      
      // Add scene pages - should be exactly 20
      for (let i = 0; i < sceneCount; i++) {
        const scene = scenes[i];
        const div = document.createElement('div');
        div.className = 'page';
        div.innerHTML = `
          <img id="scene-image-${scene.scene_number}" style="display:none;" alt="Scene ${scene.scene_number} image" />
          <div class="loading-indicator" id="loading-${scene.scene_number}">
            <div class="spinner"></div>
            <p>Ready for image generation</p>
          </div>
          <p class="scene-text">${scene.description}</p>
        `;
        flipbook.appendChild(div);
      }

      flipbook.style.display = 'block';
      // Initialize flipbook with single page display for the cover
      $(flipbook).turn({
        width: 400, // Single page width for cover
        height: 600,
        autoCenter: true,
        display: 'single' // Start with single page for cover
      });

      // Switch to double page display after the cover page
      $(flipbook).bind('turned', function(event, page, view) {
        if (page > 1 && $(this).turn('display') === 'single') {
          $(this).turn('display', 'double');
          $(this).turn('size', 800, 600); // Double page width
        } else if (page === 1 && $(this).turn('display') === 'double') {
          $(this).turn('display', 'single');
          $(this).turn('size', 400, 600); // Single page width
        }
        updateNavigationButtons(); // Update button states on page turn
      });

      // Ensure the flipbook starts on page 1
      $(flipbook).turn('page', 1);
      updateNavigationButtons(); // Initial button state

      storyContainer.style.display = 'block';
      
      // Update UI elements
      document.getElementById("scene-count-display").textContent = `Story with ${sceneCount} scenes`;
      
    } else {
      throw new Error(data.error || "Unknown error");
    }
  } catch (error) {
    errorMessage.innerText = `Error: ${error.message}`;
    errorMessage.style.display = 'block';
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate Story";
  }
}

async function generateMusic() {
  const audio = document.getElementById("background-music");
  const errorMessage = document.getElementById("errorMessage");

  try {
    const musicRes = await fetch("/generate_music", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const musicData = await musicRes.json();
    if (musicRes.ok && musicData.music_url) {
      audio.src = musicData.music_url;
      audio.play().catch(error => {
        console.warn("Auto-play failed:", error);
        document.getElementById("play-music-btn").style.display = "block";
      });
      return true;
    }
  } catch (error) {
    console.error("Music generation failed:", error);
  }
  return false;
}

async function generateCoverImage() {
  const coverDiv = document.querySelector(".cover-page");
  const errorMessage = document.getElementById("errorMessage");
  const theme = document.getElementById("theme").value.trim();
  
  try {
    const res = await fetch("/generate_cover_image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme }),
    });
    const data = await res.json();
    if (res.ok && data.image_b64) {
      coverDiv.style.backgroundImage = `url(data:image/png;base64,${data.image_b64})`;
      coverDiv.style.backgroundSize = 'cover';
      coverDiv.style.backgroundPosition = 'center';
      return true;
    } else {
      throw new Error(data.error || "Unknown error");
    }
  } catch (error) {
    console.error("Cover generation failed:", error.message);
    errorMessage.innerText = `Failed to generate cover image: ${error.message}`;
    errorMessage.style.display = 'block';
  }
  return false;
}

async function generateSingleSceneImage(sceneNumber, maxRetries = 3) {
  const imgId = `scene-image-${sceneNumber}`;
  const img = document.getElementById(imgId);
  const loadingElement = document.getElementById(`loading-${sceneNumber}`);
  const errorMessage = document.getElementById("errorMessage");
  let retries = maxRetries;

  if (loadingElement) {
    loadingElement.innerHTML = `
      <div class="spinner"></div>
      <p>Generating image ${sceneNumber} of 20...</p>
    `;
    loadingElement.style.display = 'block';
  }

  while (retries > 0) {
    try {
      const res = await fetch("/generate_scene_image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scene_number: sceneNumber }),
      });
      
      // Handle rate limiting with exponential backoff
      if (res.status === 429) {
        const backoffTime = Math.pow(2, maxRetries - retries + 1) * 2000; // Exponential backoff
        console.warn(`Rate limited by OpenAI, backing off for ${backoffTime/1000} seconds...`);
        if (loadingElement) {
          loadingElement.innerHTML = `
            <div class="spinner"></div>
            <p>Rate limited. Retrying in ${backoffTime/1000}s...</p>
          `;
        }
        await new Promise(resolve => setTimeout(resolve, backoffTime));
        retries--;
        continue;
      }
      
      const data = await res.json();
      if (res.ok && data.image_b64) {
        img.src = `data:image/png;base64,${data.image_b64}`;
        img.style.display = 'block';
        if (loadingElement) {
          loadingElement.style.display = 'none';
        }
        return true;
      } else {
        throw new Error(data.error || "Unknown error");
      }
    } catch (error) {
      console.error(`Error for scene ${sceneNumber}: ${error.message}, retries left: ${retries}`);
      retries--;
      if (retries === 0) {
        if (loadingElement) {
          loadingElement.innerHTML = `
            <div style="color: #f44336;">❌ Failed to generate</div>
          `;
        }
        img.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII='; // Empty transparent image
        img.style.display = 'block';
        errorMessage.innerText = `Failed to generate image for scene ${sceneNumber} after multiple attempts: ${error.message}`;
        errorMessage.style.display = 'block';
        return false;
      }
      if (loadingElement) {
        loadingElement.innerHTML = `
          <div class="spinner"></div>
          <p>Error, retrying (${retries} left)...</p>
        `;
      }
      await new Promise(resolve => setTimeout(resolve, 3000)); // wait 3 sec before retry
    }
  }
  return false;
}

async function generateAllImages() {
  const generateBtn = document.querySelector('button[onclick="generateAllImages()"]');
  const errorMessage = document.getElementById("errorMessage");
  const statusElement = document.getElementById("generation-status");
  
  // Disable button to prevent multiple clicks
  generateBtn.disabled = true;
  generateBtn.textContent = "Generating...";
  errorMessage.style.display = 'none';
  
  try {
    // Setup volume control
    const audio = document.getElementById("background-music");
    const volumeSlider = document.getElementById("volume-slider");
    if (volumeSlider) {
      volumeSlider.addEventListener("input", () => {
        audio.volume = parseFloat(volumeSlider.value);
      });
    }
    
    // Show play button for music
    const playMusicBtn = document.getElementById("play-music-btn");
    if (playMusicBtn) {
      playMusicBtn.addEventListener("click", () => {
        audio.play();
        playMusicBtn.style.display = "none";
      });
    }
    
    // Generate music in parallel with cover image
    statusElement.textContent = "Generating cover image and music...";
    const musicPromise = generateMusic();
    const coverPromise = generateCoverImage();
    
    // Wait for cover and music to complete first
    await Promise.all([musicPromise, coverPromise]);
    
    // Generate scene images sequentially with better spacing
    const totalScenes = 20;
    
    for (let i = 1; i <= totalScenes; i++) {
      // Update status
      statusElement.textContent = `Generating image ${i} of ${totalScenes}...`;
      generateBtn.textContent = `Generating ${i}/${totalScenes}`;
      
      await generateSingleSceneImage(i);
      
      // Significant delay between API calls to avoid rate limits
      if (i < totalScenes) {
        statusElement.textContent = `Waiting before generating next image (${i+1})...`;
        await new Promise(resolve => setTimeout(resolve, 8000));
      }
    }
    
    // All done
    statusElement.textContent = "All images generated!";
    generateBtn.textContent = "Images Generated!";
    setTimeout(() => {
      generateBtn.textContent = "Regenerate Images";
      generateBtn.disabled = false;
      statusElement.textContent = "";
    }, 3000);
    
  } catch (error) {
    console.error("Error generating images:", error);
    errorMessage.innerText = `Error: ${error.message}`;
    errorMessage.style.display = 'block';
    generateBtn.textContent = "Try Again";
    generateBtn.disabled = false;
    statusElement.textContent = "Generation failed, please try again.";
  }
}

function playMusic() {
  const audio = document.getElementById("background-music");
  audio.play();
  document.getElementById("play-music-btn").style.display = "none";
}

function toggleFullscreen() {
  const elem = document.getElementById("flipbook");
  if (!document.fullscreenElement) {
    if (elem.requestFullscreen) {
      elem.requestFullscreen();
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }
}

function updateNavigationButtons() {
  const flipbook = $("#flipbook");
  const currentPage = flipbook.turn("page");
  const totalPages = flipbook.turn("pages");
  const prevBtn = document.getElementById("prev-page-btn");
  const nextBtn = document.getElementById("next-page-btn");

  // Disable "Previous" button on the first page
  prevBtn.disabled = currentPage <= 1;
  // Disable "Next" button on the last page
  nextBtn.disabled = currentPage >= totalPages;
}

function prevPage() {
  $("#flipbook").turn("previous");
  updateNavigationButtons();
}

function nextPage() {
  $("#flipbook").turn("next");
  updateNavigationButtons();
}